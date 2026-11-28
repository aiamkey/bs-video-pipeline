#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""replica_assemble.py —— 把分段克隆配音按 spec 时间轴装成整条 voice.wav。

复刻链路里「声音」这一步的收尾件：
  replica_voice.py speak → voice-out/0000.wav …（每句一段 24kHz/16bit/mono）
  本脚本把这些段按 subs 的时间轴铺回原片节奏，产出可给剪映/Remotion 用的 voice.wav。

为什么要铺而不是顺序拼：
  复刻要求「时长对准原片」。逐句合成的总长和原片不一样，句间停顿也不一样；
  只有按 subs.s 定位、把段塞回原来的时间格子里，字幕轴和画面轴才对得上。

三种落位策略（--fit）：
  raw    不压缩，段从 s 起铺；超出格子就压到下一段上面（下一段后写、优先）。
         最保真，但长段会盖住后面那句的开头 → 只适合先听个整体。
  tempo  超格子的段用 ffmpeg atempo 等比压到格子内（保音高、上限 --max-tempo）。
         默认。句子被压 5%–20% 基本听不出来，压过头会变快 —— 报告里会列出来。
  trim   超格子直接硬切（丢尾字），只在 --max-tempo 也救不回来时用。

用法：
  python tools/replica_assemble.py --spec qa2/replica/out/xxx.spec.json \
      --voice-dir qa2/replica/voice-out -o qa2/replica/voice.wav
  python tools/replica_assemble.py ... --fit raw --dry     # 只看统计，不落盘

产出：
  voice.wav                      整条配音（--dry 时不写）
  <voice-dir>/assemble-report.json  每段的窗长/段长/处理方式/是否失败
"""
from __future__ import annotations

import argparse
import array
import json
import shutil
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

RATE = 24000
MAX_TEMPO_DEFAULT = 1.6      # 实测：1.6 能修掉 94% 的超格段（36→2），再往上压缩听感变差


def ffmpeg() -> str:
    """优先 imageio-ffmpeg 自带二进制（本机已装），其次 PATH，最后 tools/ff.cmd。"""
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    here = Path(__file__).resolve().parent
    ff = here / "ff.cmd"
    if ff.exists():
        return str(ff)
    raise SystemExit("找不到 ffmpeg：pip install imageio-ffmpeg，或把 ffmpeg 加进 PATH")


def read_pcm(path: Path) -> array.array:
    with wave.open(str(path), "rb") as w:
        if w.getnchannels() != 1 or w.getsampwidth() != 2 or w.getframerate() != RATE:
            raise SystemExit(f"{path.name} 不是 {RATE}Hz/16bit/mono（{w.getframerate()}/{w.getsampwidth()*8}bit/{w.getnchannels()}ch）")
        data = array.array("h")
        data.frombytes(w.readframes(w.getnframes()))
        return data


def tempo_pcm(path: Path, factor: float) -> array.array:
    """用 ffmpeg atempo 压一段，返回 PCM（保音高）。"""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / "o.wav"
        r = subprocess.run(
            [ffmpeg(), "-y", "-loglevel", "error", "-i", str(path),
             "-filter:a", f"atempo={factor:.6f}", "-ar", str(RATE), "-ac", "1", "-f", "wav", str(tmp)],
            capture_output=True, text=True)
        if r.returncode != 0 or not tmp.exists():
            raise RuntimeError(f"atempo 失败：{(r.stderr or '')[:200]}")
        return read_pcm(tmp)


def assemble(spec: dict, voice_dir: Path, fit: str, max_tempo: float, dry: bool, out: Path) -> int:
    subs = spec.get("subs") or []
    if not subs:
        raise SystemExit("spec 里没有 subs")
    meta = spec.get("meta") or {}
    total = float(meta.get("target_duration") or meta.get("src_duration") or meta.get("duration") or 0)
    if total <= 0:
        raise SystemExit("spec.meta 里没有 target_duration/src_duration")

    frames = int(round(total * RATE))
    buf = array.array("h", bytes(2 * frames))       # 全零 = 静音底

    rows, n_ok, n_miss, n_fit, n_trim, n_over = [], 0, 0, 0, 0, 0
    for i, seg in enumerate(subs):
        s = float(seg.get("s") or 0.0)
        wav = voice_dir / f"{i:04d}.wav"
        win_end = float(subs[i + 1]["s"]) if i + 1 < len(subs) else total
        win = max(0.05, win_end - s)
        row = {"i": i, "s": round(s, 3), "win": round(win, 3), "text": (seg.get("text") or "")[:24]}

        if not wav.exists():
            n_miss += 1
            row.update(state="missing")
            rows.append(row)
            continue
        try:
            pcm = read_pcm(wav)
        except SystemExit as e:
            n_miss += 1
            row.update(state="bad", note=str(e))
            rows.append(row)
            continue

        dur = len(pcm) / RATE
        row["dur"] = round(dur, 3)
        over = dur - win
        if over > 0.02:                       # 超格
            n_over += 1
            if fit == "tempo":
                factor = dur / win
                if factor <= max_tempo:
                    try:
                        pcm = tempo_pcm(wav, factor)
                        dur = len(pcm) / RATE
                        n_fit += 1
                        row.update(state="tempo", factor=round(factor, 3), dur=round(dur, 3))
                    except Exception as e:
                        pcm = pcm[: int(win * RATE)]
                        n_trim += 1
                        row.update(state="trim", note=str(e)[:120])
                else:
                    pcm = pcm[: int(win * RATE)]
                    n_trim += 1
                    row.update(state="trim", note=f"需要 {factor:.2f}x > 上限 {max_tempo}")
            elif fit == "trim":
                pcm = pcm[: int(win * RATE)]
                n_trim += 1
                row.update(state="trim")
            else:                              # raw：照铺，允许盖住下一段
                row.update(state="raw", over=round(over, 3))
        else:
            row.update(state="ok")
        n_ok += 1

        start = int(round(s * RATE))
        if start >= frames:
            row["state"] = "past-end"
            rows.append(row)
            continue
        end = min(start + len(pcm), frames)
        buf[start:end] = pcm[: end - start]
        rows.append(row)

    # 统计：有声占比
    nz = sum(1 for x in buf if x)
    speech_ratio = nz / max(1, len(buf))
    report = {
        "spec": str(out),
        "fit": fit,
        "max_tempo": max_tempo,
        "total_dur": round(total, 3),
        "subs": len(subs),
        "placed": n_ok,
        "missing": n_miss,
        "over_window": n_over,
        "tempo_fixed": n_fit,
        "trimmed": n_trim,
        "speech_ratio": round(speech_ratio, 4),
        "rows": rows,
    }
    rep_path = voice_dir / "assemble-report.json"
    rep_path.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"[assemble] {len(subs)} 段  时长 {total:.2f}s  策略 {fit}")
    print(f"           落位 {n_ok}  缺段 {n_miss}  超格 {n_over}（tempo 修 {n_fit} / 截断 {n_trim}）")
    print(f"           有声占比 {speech_ratio:.1%}   报告 {rep_path}")
    if n_miss:
        miss = [r["i"] for r in rows if r.get("state") in ("missing", "bad")][:20]
        print(f"[warn] 缺 {n_miss} 段，前 20 个编号：{miss}")
    if n_trim:
        bad = [(r["i"], r.get("note", "")) for r in rows if r.get("state") == "trim"][:8]
        print(f"[warn] 有段被截断 {n_trim} 处：{bad}")

    if dry:
        print("[assemble] --dry：不写 voice.wav")
        return 0

    out.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(buf.tobytes())
    print(f"[assemble] → {out}  {out.stat().st_size} B")
    return 0


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="把分段配音按 spec 时间轴装成整条 voice.wav")
    ap.add_argument("--spec", required=True, help="replica spec.json")
    ap.add_argument("--voice-dir", required=True, help="replica_voice.py speak 的输出目录")
    ap.add_argument("-o", "--out", default="qa2/replica/voice.wav", help="输出 voice.wav")
    ap.add_argument("--fit", choices=["raw", "tempo", "trim"], default="tempo")
    ap.add_argument("--max-tempo", type=float, default=MAX_TEMPO_DEFAULT)
    ap.add_argument("--dry", action="store_true", help="只统计不写盘")
    a = ap.parse_args()
    spec = json.loads(Path(a.spec).read_text(encoding="utf-8-sig"))
    return assemble(spec, Path(a.voice_dir), a.fit, a.max_tempo, a.dry, Path(a.out))


if __name__ == "__main__":
    raise SystemExit(main())
