"""声音克隆原子件 · replica.py voice 用它。

链路：extract_ref(从原片挑干净参考段) → create(建音色) → wait(等 OK)
      → speak(按段合成配音) → 由上层 align 对齐到 spec.subs。

两条通道（配置全在 qa2/replica/voice.json，跳过 _ 开头的文档字段）
--------------------------------------------------------------
  dashscope（当前启用）—— 阿里云百炼 voice-enrollment。
    用户已给过 DASHSCOPE_API_KEY（tools/ds_img.py:15 内嵌兜底）。
    ★ 2026-11-28 实测更正：本机预存的 EP01 音色不挂在这把 key 名下
      （voices.list=0 / get=ResourceNotExist），旧的 qwen3-tts-vc-realtime-2025-11-27
      服务端报 Model not exist → 全部废弃。改走官方 SDK 正确路径：
    create: client.audio.voices.create(target_model=clone_model, prefix=prefix,
            audio="data:audio/wav;base64,...")  ← 内联 data URI，不需 HTTPS URL
    wait:   client.audio.voices.get(vid) 轮询到 status=OK
    speak:  client.audio.tts.connect(model=speak_model, voice=voice_id,
            format="pcm", sample_rate=24000) → 线程收 session.events() 的 bytes(PCM)
            → session.send_text / session.stop → 落 WAV
    ★ clone_model == speak_model（复刻音色合成必须用创建时的同一个 model）。
    create 默认只打印计划，加 --yes 才真发（建音色计费、不自动删除）。

  jcaigc（备用）—— 独立语音网关 https://api.jcaigc.cn/v1。
    multipart 建音色 9.9 元/个 + HTTP /audio/speech 合成，支持本地 wav。

  用哪个 clone_model 建，speak_model 必须一致（plus/flash 不能混）。
  按段/章节原生合成，禁止 ffmpeg atempo（金属感）。
  --check 只打印、不联网、不花钱。

用法:
  python tools/replica_voice.py --check
  python tools/replica_voice.py extract-ref  ref.segs.json ref.wav --src 片.mp4
  python tools/replica_voice.py create       ref.wav
  python tools/replica_voice.py wait         <voice_id>
  python tools/replica_voice.py speak        spec.json out_dir/ [--limit 3]
  python tools/replica_voice.py list | get <voice_id> | delete <voice_id> --yes
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import shutil
import subprocess
import sys
import time
import wave
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
VOICE_CFG = ROOT / "qa2" / "replica" / "voice.json"
PYLIBS = ROOT / "tools" / "pylibs"
FALLBACK_FFMPEG = r"E:\miniconda\envs\JupyterProject\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v9.0.2.exe"


def ffmpeg() -> str:
    p = shutil.which("ffmpeg")
    if p:
        return p
    if Path(FALLBACK_FFMPEG).exists():
        return FALLBACK_FFMPEG
    raise SystemExit("找不到 ffmpeg；在 voice.json 同级环境里装一个或写绝对路径。")


def mask(k: str) -> str:
    if not k:
        return "(空)"
    return k[:6] + "…" + k[-4:] if len(k) > 12 else "***"


def load_cfg() -> dict:
    c = {
        "provider": "dashscope",
        "base_url": "https://api.jcaigc.cn/v1",   # 仅 jcaigc 通道用
        "api_key": "", "api_key_env": "DASHSCOPE_API_KEY",
        "clone_model": "qwen-audio-3.0-tts-flash",
        "speak_model": "qwen-audio-3.0-tts-flash",   # ★ 必须与 clone_model 一致
        "voice_id": "", "name": "replica-auto", "prefix": "replica",
        "ref_audio": "auto", "rate": 1.08, "timeout": 180,
        "ws_url": "wss://dashscope.aliyuncs.com/api-ws/v1/realtime",
        "sample_rate": 24000, "region": "", "workspace": "",
    }
    if VOICE_CFG.exists():
        r = json.loads(VOICE_CFG.read_text(encoding="utf-8-sig"))
        for k, v in r.items():
            if k.startswith("_") or k not in c:
                continue
            c[k] = v
    env_key = os.environ.get(c.get("api_key_env") or "", "")
    if env_key:
        c["api_key"] = env_key
    return c


def require_key(c: dict):
    if not (c.get("api_key") or "").strip():
        raise SystemExit(
            f"api_key 为空。先填 {VOICE_CFG} 的 api_key，"
            f"或设环境变量 {c.get('api_key_env')}；若已有音色直接填 voice_id。"
        )
    return c["api_key"]


def endpoint(c: dict, path: str) -> str:
    return c["base_url"].rstrip("/") + "/" + path.lstrip("/")


def auth(c: dict) -> dict:
    return {"Authorization": "Bearer " + require_key(c)}


def dashscope_client(c: dict):
    """百炼官方 SDK：create/list/get 走 client.audio.voices。"""
    if str(PYLIBS) not in sys.path:
        sys.path.insert(0, str(PYLIBS))
    try:
        from dashscope import Client
    except Exception as e:
        raise SystemExit(
            f"百炼 SDK 没装好：{e}\n"
            f"在 {PYLIBS} 下执行 pip install -e . ；或把 provider 切回 jcaigc。"
        )
    key = require_key(c)
    kw = {"api_key": key, "timeout": float(c.get("timeout") or 180), "max_retries": 0}
    if c.get("region"):
        kw["region"] = c["region"]
    if c.get("workspace"):
        kw["workspace"] = c["workspace"]
    return Client(**kw)


# ---------- 参考音频：按 ASR 段挑最干净的一段 ----------

def pick_window(segs: list[dict], lo: float = 10.0, hi: float = 20.0) -> tuple[float, float]:
    """在连续段里找长度落在 [lo,hi] 的窗；优先最长、段间无大空隙的。"""
    if not segs:
        raise SystemExit("segs.json 为空，无法挑参考音频")
    best = None
    n = len(segs)
    for i in range(n):
        acc, gaps = 0.0, 0.0
        for j in range(i, n):
            if j > i:
                gaps += max(0.0, segs[j]["s"] - segs[j - 1]["e"])
            acc = segs[j]["e"] - segs[i]["s"]
            if acc > hi:
                break
            if lo <= acc <= hi:
                score = acc - gaps * 2.0      # 越长越好，空隙越小越好
                if best is None or score > best[0]:
                    best = (score, segs[i]["s"], segs[j]["e"])
    if best is None:
        return segs[0]["s"], min(segs[0]["s"] + hi, segs[-1]["e"])
    return best[1], best[2]


def cmd_extract_ref(segs_path: Path, out_wav: Path, src: Path | None, c: dict):
    segs = json.loads(segs_path.read_text(encoding="utf-8-sig"))
    s, e = pick_window(segs)
    dur = max(3.0, min(30.0, e - s))
    if src is None or not src.exists():
        meta = {"s": s, "e": s + dur, "dur": dur, "src": None, "note": "未给 src，仅输出时间窗"}
        out_wav.with_suffix(".meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"[extract-ref] 参考窗 {s:.2f}–{s + dur:.2f}s（{dur:.2f}s），未切片：{out_wav.with_suffix('.meta.json')}")
        return
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([ffmpeg(), "-y", "-loglevel", "error", "-ss", f"{s:.3f}", "-i", str(src),
                    "-t", f"{dur:.3f}", "-ar", "24000", "-ac", "1", "-b:a", "96k", str(out_wav)],
                   check=True)
    meta = {"s": s, "e": s + dur, "dur": dur, "src": str(src),
            "bytes": out_wav.stat().st_size, "requirement": "单人/无BGM/无混响/3-30s/≤10MB"}
    out_wav.with_suffix(".meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    if meta["bytes"] > 10_000_000:
        print(f"[warn] {meta['bytes']} B 超过 10MB，建议压一下", file=sys.stderr)
    print(f"[extract-ref] {out_wav}  {dur:.2f}s  {meta['bytes']} B  meta={out_wav.with_suffix('.meta.json')}")


# ---------- 网关 / SDK CRUD ----------

def cmd_create(ref_wav: Path, c: dict, yes: bool = False):
    if c.get("voice_id"):
        print(f"[create] 已配置 voice_id={c['voice_id']}，跳过建音色（零复刻费）")
        return
    if c["provider"] == "dashscope":
        # ★ 官方 SDK 正确路径：data URI 内联音频，不需 HTTPS URL
        if not ref_wav.exists():
            raise SystemExit(f"参考音频不存在：{ref_wav}（先跑 extract-ref --src 片.mp4）")
        raw = ref_wav.read_bytes()
        if len(raw) > 10_000_000:
            raise SystemExit(f"[create] {len(raw)} B 超过 10MB，压一下再建音色")
        ext = ref_wav.suffix.lower().lstrip(".") or "wav"
        mime = {"wav": "wav", "mp3": "mpeg", "m4a": "mp4"}.get(ext, ext)
        data_uri = f"data:audio/{mime};base64," + base64.b64encode(raw).decode("ascii")
        print(f"[create] 百炼 voice-enrollment（data URI 内联，无需 HTTPS URL）")
        print(f"        ref={ref_wav}  {len(raw)} B  target_model={c['clone_model']}  prefix={c.get('prefix','replica')}")
        print(f"[create] 计费提示：建音色按百炼计费、创建成功后计入账单、不会自动删除。")
        if not yes:
            print("[create] 这是 dry 计划。真发请加 --yes（会从原片切好干净人声后建音色）。")
            return
        client = dashscope_client(c)
        with client:
            v = client.audio.voices.create(
                target_model=c["clone_model"], prefix=c.get("prefix") or "replica",
                audio=data_uri,
            )
        vid = getattr(v, "voice_id", None)
        print(json.dumps({"voice_id": vid, "status": getattr(v, "status", None)},
                         ensure_ascii=False, indent=2))
        if not vid:
            raise SystemExit("[create] 没拿到 voice_id，先跑 list / get 排查，别重复 create")
        # 写回 voice.json 的 voice_id
        cfg = json.loads(VOICE_CFG.read_text(encoding="utf-8-sig"))
        cfg["voice_id"] = vid
        VOICE_CFG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[create] 已把 voice_id 写回 {VOICE_CFG}；接着跑 wait，再 speak。")
        return
    # ---- jcaigc HTTP multipart ----
    key = require_key(c)
    if not ref_wav.exists():
        raise SystemExit(f"参考音频不存在：{ref_wav}（先跑 extract-ref）")
    print(f"[create] POST {endpoint(c, 'audio/voices')}  model={c['clone_model']}  "
          f"file={ref_wav.name}（{ref_wav.stat().st_size} B）")
    print("[create] 注意：创建成功即扣 9.9 元；UNDEPLOYED 不退款，挑段前确认音频质量。", file=sys.stderr)
    with ref_wav.open("rb") as f:
        r = requests.post(endpoint(c, "audio/voices"), headers={"Authorization": "Bearer " + key},
                          files={"file": (ref_wav.name, f, "audio/wav")},
                          data={"model": c["clone_model"], "name": c.get("name") or "replica-auto"},
                          timeout=c["timeout"])
    try:
        d = r.json()
    except Exception:
        raise SystemExit(f"[create] HTTP {r.status_code} 非 JSON：{r.text[:400]}")
    print(json.dumps(d, ensure_ascii=False, indent=2))
    if r.ok and d.get("voice_id"):
        print(f"\n[create] voice_id={d['voice_id']}  把它填回 voice.json 的 voice_id，再跑 wait。")


def cmd_wait(voice_id: str, c: dict):
    vid = voice_id or c.get("voice_id")
    if not vid:
        raise SystemExit("没给 voice_id，也没在 voice.json 配")
    if c["provider"] == "dashscope":
        # ★ 严格校验：音色不存在就明确报错，不再「视为已部署」放行
        client = dashscope_client(c)
        with client:
            v = client.audio.voices.get(vid)
        print(f"[wait] dashscope voice_id={vid}  status={v.status}")
        if str(v.status) != "OK":
            raise SystemExit(f"[wait] 音色状态 {v.status}，还不能合成（先 create / 换 voice_id）")
        print("[wait] 就绪，可以 speak。")
        return
    for i in range(60):
        r = requests.get(endpoint(c, f"audio/voices/{vid}"), headers=auth(c), timeout=c["timeout"])
        d = r.json() if r.ok else {"status": f"HTTP{r.status_code}", "raw": r.text[:200]}
        st = d.get("status", "?")
        print(f"[wait] {i:02d}  status={st}", flush=True)
        if st == "OK":
            print("[wait] 就绪，可以 speak。")
            return
        if st == "UNDEPLOYED":
            raise SystemExit("[wait] UNDEPLOYED（音频质量/合规未过，不退款）：换参考段重建音色。")
        time.sleep(5)
    raise SystemExit("[wait] 超时仍非 OK")


# ---------- 合成 ----------

def _sdk_speak_one(text: str, c: dict) -> bytes:
    """百炼官方 SDK 合成一段，返回原始 PCM（24kHz/16bit/mono）。

    client.audio.tts.connect(model=speak_model, voice=voice_id, ...)：
    用线程收 session.events() 的 bytes(PCM)，主线程 send_text + stop。
    复刻音色必须用创建时的同一个 model（tts_websocket.py:94）。
    """
    import threading
    client = dashscope_client(c)
    pcm = bytearray()
    errs = []
    with client:
        with client.audio.tts.connect(
            model=c["speak_model"], voice=c["voice_id"],
            format="pcm", sample_rate=int(c.get("sample_rate") or 24000),
            timeout=float(c.get("timeout") or 180),
        ) as session:
            def receiver():
                try:
                    for frame in session.events():
                        if isinstance(frame, bytes):
                            pcm.extend(frame)
                except Exception as e:
                    errs.append(f"{type(e).__name__}: {str(e)[:240]}")
            th = threading.Thread(target=receiver, daemon=True)
            th.start()
            session.send_text(text)
            session.stop()
            th.join(timeout=float(c.get("timeout") or 180))
    if errs:
        raise RuntimeError("; ".join(errs))
    return bytes(pcm)


def _write_wav(out: Path, pcm: bytes, rate: int):
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(int(rate))
        w.writeframes(pcm)


def cmd_speak(spec_path: Path, out_dir: Path, c: dict, limit: int = 0):
    spec = json.loads(spec_path.read_text(encoding="utf-8-sig"))
    segs = spec.get("voice", {}).get("segments") or spec.get("subs") or []
    if not segs:
        raise SystemExit("spec 里没有 voice.segments / subs，没东西可合成")
    if limit:
        segs = segs[:limit]
    out_dir.mkdir(parents=True, exist_ok=True)

    if c["provider"] == "dashscope":
        require_key(c)
        if not c.get("voice_id"):
            raise SystemExit("speak 需要 voice_id：先 extract-ref --src → create --yes → wait")
        print(f"[speak] dashscope 官方 SDK · {len(segs)} 段")
        print(f"        model={c['speak_model']}  voice={c['voice_id']}")
        print(f"        pcm={c['sample_rate']}Hz/16bit/mono  → {out_dir}")
        rate = int(c.get("sample_rate") or 24000)
        ok = 0
        for i, seg in enumerate(segs):
            text = (seg.get("text") or "").strip()
            if not text:
                continue
            out = out_dir / f"{i:04d}.wav"
            try:
                pcm = _sdk_speak_one(text, c)
                if not pcm:
                    print(f"[speak] {i:04d} FAIL 空 PCM", file=sys.stderr)
                    continue
                _write_wav(out, pcm, rate)
                ok += 1
                print(f"[speak] {i:04d} ok {len(pcm)} B ({len(pcm)/2/rate:.2f}s)  {text[:24]}")
            except Exception as e:
                print(f"[speak] {i:04d} FAIL {type(e).__name__}: {str(e)[:240]}", file=sys.stderr)
        print(f"[speak] 完成 {ok}/{len(segs)} 段 → {out_dir}")
        return

    # ---- jcaigc HTTP ----
    if not c.get("voice_id"):
        raise SystemExit("speak 需要 voice_id：先 create + wait，或在 voice.json 填现成音色")
    model = c["speak_model"]
    print(f"[speak] jcaigc HTTP · {len(segs)} 段  model={model}  voice={c['voice_id']}  rate={c.get('rate')}  → {out_dir}")
    for i, seg in enumerate(segs):
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        out = out_dir / f"{i:04d}.mp3"
        r = requests.post(endpoint(c, "audio/speech"), headers=auth(c),
                          json={"model": model, "input": text, "voice": c["voice_id"],
                                "speed": float(c.get("rate") or 1.0)},
                          timeout=c["timeout"])
        ct = r.headers.get("Content-Type", "")
        if r.ok and ("audio" in ct or r.content[:4] in (b"ID3\x03", b"RIFF")):
            out.write_bytes(r.content)
            print(f"[speak] {i:04d} ok {len(r.content)} B  {text[:24]}")
        else:
            print(f"[speak] {i:04d} FAIL HTTP {r.status_code} {ct}: {r.text[:200]}", file=sys.stderr)


def cmd_list(c: dict):
    if c["provider"] == "dashscope":
        require_key(c)
        with dashscope_client(c) as client:
            v = client.audio.voices.list(prefix="", page_index=0, page_size=30)
        print(f"[list] 百炼音色 {len(v.voices)} 个")
        for x in v.voices:
            print(" ", x.get("voice_id"), x.get("status"))
        return
    r = requests.get(endpoint(c, "audio/voices"), headers=auth(c), timeout=c["timeout"])
    print(r.text[:4000] if r.text else f"HTTP {r.status_code}")


def cmd_get(voice_id: str, c: dict):
    vid = voice_id or c.get("voice_id", "")
    if c["provider"] == "dashscope":
        require_key(c)
        with dashscope_client(c) as client:
            v = client.audio.voices.get(vid)
        print(f"[get] voice_id={vid}  status={v.status}")
        return
    r = requests.get(endpoint(c, f"audio/voices/{vid}"), headers=auth(c), timeout=c["timeout"])
    print(r.text[:2000])


def cmd_delete(voice_id: str, yes: bool, c: dict):
    if c["provider"] == "dashscope":
        raise SystemExit(
            "百炼音色删除请走官方 SDK（不可逆）：\n"
            f"  cd {PYLIBS}\n"
            f'  python -m examples.01_atomic_capabilities.audio.voice_clone delete '
            f'--voice-id "{voice_id}" --yes'
        )
    if not yes:
        raise SystemExit("删除音色不退费且不可逆；确认请加 --yes")
    r = requests.delete(endpoint(c, f"audio/voices/{voice_id}"), headers=auth(c), timeout=c["timeout"])
    print(f"HTTP {r.status_code}: {r.text[:400]}")


def cmd_check(c: dict):
    print("voice.json :", VOICE_CFG, "(存在)" if VOICE_CFG.exists() else "(不存在，用默认)")
    print("provider   =", c["provider"])
    if c["provider"] == "dashscope":
        print("  └ 阿里云百炼 voice-enrollment（用户已给过 key，不用再要第二把）")
    else:
        print("base_url   =", c["base_url"])
        print("endpoint   =", endpoint(c, "audio/voices"))
    print("clone_model=", c["clone_model"], " speak_model=", c["speak_model"])
    if c["provider"] == "jcaigc" and c["clone_model"] != c["speak_model"]:
        print("  ⚠ 两个 model 不一致：plus/flash 不能混用，合成会失败")
    print("voice_id   =", c["voice_id"] or "(空 → 用这把 key 现建音色；旧的 EP01 音色不挂在本 key 名下，已弃用)")
    if c["voice_id"]:
        print("  └ 已登记音色，跳过 create")
    print("api_key    =", mask(c["api_key"]), f" env={c['api_key_env']}")
    if c["api_key"]:
        print("  └ 已配置（来自 tools/ds_img.py 内嵌 / 环境变量），无需再填")
    print("ref_audio  =", c["ref_audio"], " rate=", c["rate"])
    if c["provider"] == "dashscope":
        print("路径       = voices.create(audio=dataURI) → voices.get(OK) → audio.tts.connect")
        print("            clone_model 必须 == speak_model：", c["clone_model"], "/", c["speak_model"])
        print("wav        =", f"{c['sample_rate']}Hz / 16bit / mono")
    print("ffmpeg     =", end=" ")
    try:
        print(ffmpeg())
    except SystemExit as ex:
        print(ex)
    print("[check] 未联网、未花钱。流程：extract-ref --src → create --yes → wait → speak。")


def main():
    ap = argparse.ArgumentParser(description="声音克隆原子件")
    ap.add_argument("cmd", nargs="?", default="check",
                    choices=["check", "extract-ref", "create", "wait", "speak",
                             "list", "get", "delete"])
    ap.add_argument("arg", nargs="?", default="")
    ap.add_argument("arg2", nargs="?", default="")
    ap.add_argument("--src", default="")
    ap.add_argument("--limit", type=int, default=0, help="speak 只合成前 N 段（先试 1 段）")
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--check", action="store_true", help="等价于默认命令 check（只打印配置不联网）")
    a = ap.parse_args()
    c = load_cfg()

    if a.check or a.cmd == "check":
        cmd_check(c)
    elif a.cmd == "extract-ref":
        cmd_extract_ref(Path(a.arg), Path(a.arg2 or "qa2/replica/ref.wav"),
                        Path(a.src) if a.src else None, c)
    elif a.cmd == "create":
        cmd_create(Path(a.arg or "qa2/replica/ref.wav"), c, a.yes)
    elif a.cmd == "wait":
        cmd_wait(a.arg, c)
    elif a.cmd == "speak":
        cmd_speak(Path(a.arg), Path(a.arg2 or "qa2/replica/voice"), c, a.limit)
    elif a.cmd == "list":
        cmd_list(c)
    elif a.cmd == "get":
        cmd_get(a.arg, c)
    elif a.cmd == "delete":
        cmd_delete(a.arg, a.yes, c)


if __name__ == "__main__":
    main()
