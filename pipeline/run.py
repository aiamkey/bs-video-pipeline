# -*- coding: utf-8 -*-
"""凯哥式视频流水线 —— 从文稿一条命令跑到成片。

用法（在 video\\ 目录下）：
    python lbr-promo\\pipeline\\run.py all   ep02      # 全流程
    python lbr-promo\\pipeline\\run.py plan  ep02      # 只算时长（不配音）
    python lbr-promo\\pipeline\\run.py voice ep02      # 只重配配音
    python lbr-promo\\pipeline\\run.py align ep02      # 只重对齐
    python lbr-promo\\pipeline\\run.py build ep02      # 只重生成 film.json
    python lbr-promo\\pipeline\\run.py render ep02     # 只重渲染
    python lbr-promo\\pipeline\\run.py mix   ep02      # 只重混音响度
    python lbr-promo\\pipeline\\run.py check ep02      # 只质检

时长两种模式（config.json → video.duration.mode）：
    auto    稿子写多长就多长，不设目标（默认）
    target  卡死 target_sec±tolerance_pct；plan 会反推该写多少字 / 语速调多少

所有参数来自 pipeline/config.json。改配置 → 重跑需要的阶段，不要改脚本。
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import env as penv   # 同目录：统一环境发现（路径/ffmpeg/python/tts 配置）

HERE = Path(__file__).resolve().parent
PROMO = penv.promo()
ROOT = penv.root()


def _load_cfg():
    for name in ("config.local.json", "config.json", "config.example.json"):
        f = HERE / name
        if f.exists():
            return json.loads(f.read_text(encoding="utf-8")), name
    raise SystemExit("✗ pipeline/ 下找不到 config.local.json / config.json / config.example.json")


CFG, CFG_NAME = _load_cfg()
PY = penv.python()
FF = penv.ffmpeg()


def run(cmd, cwd=None, env=None, label=""):
    t0 = time.time()
    print(f"\n▶ {label or cmd[0]}")
    print("  " + " ".join(str(c) for c in cmd))
    e = dict(os.environ)
    if env:
        e.update(env)
    p = subprocess.run([str(c) for c in cmd], cwd=str(cwd or ROOT), env=e,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.stdout.strip():
        print(p.stdout.strip())
    if p.returncode != 0:
        if p.stderr.strip():
            print(p.stderr.strip()[-3000:])
        raise SystemExit(f"✗ {label} 失败 (exit {p.returncode})")
    print(f"  ✓ {time.time() - t0:.1f}s")
    return p


def api_key(provider="dashscope"):
    """key 优先级：环境变量 → config.json 的 keys → tts-service 的 config.local.json。"""
    env_name = {"dashscope": "DASHSCOPE_API_KEY", "siliconflow": "SILICONFLOW_API_KEY"}[provider]
    if os.environ.get(env_name):
        return os.environ[env_name]
    if CFG.get("keys", {}).get(provider):
        return CFG["keys"][provider]
    local = penv.tts_config()
    if local and local.is_file():
        try:
            data = json.loads(local.read_text(encoding="utf-8-sig"))
            if isinstance(data.get(provider), str) and data[provider].startswith("sk-"):
                return data[provider]
            for group in ("api_keys", "keys"):
                if isinstance(data.get(group), dict) and data[group].get(provider):
                    return data[group][provider]
        except Exception:
            pass
    return None


def script_path() -> Path:
    """config.project.script 只写文件名，真实目录由 env 发现（scripts/）。"""
    raw = Path(CFG["project"]["script"])
    return raw if raw.is_absolute() else (penv.scripts() / raw.name)


def stage_voice(name):
    v = CFG["voice"]
    key = api_key("dashscope")
    if not key:
        raise SystemExit("✗ 找不到 DASHSCOPE_API_KEY（环境变量 / config.json keys / tts-service 配置都没有）")
    run([PY, penv.tools() / "cosy_chapter.py", script_path(), name,
         v["voice"], v["rate"], v["gap_between_chapters"], v["silence_keep"]],
        env={"DASHSCOPE_API_KEY": key},
        label=f"配音 · {v['voice']} rate={v['rate']}")


def stage_align(name):
    wav = f"{name}.wav"
    run([PY, penv.tools() / "align_v2.py", wav, script_path(), name],
        env={"HF_ENDPOINT": "https://hf-mirror.com"},
        label="对齐 · whisper + difflib")


def stage_build(name):
    run([PY, penv.scripts() / "build_film.py", script_path(), name],
        label="生成 film.json")


def stage_render(name):
    tmp = PROMO / ".tmp-remotion"
    tmp.mkdir(exist_ok=True)
    v = CFG["video"]
    out = PROMO / "out" / f"{name}-raw.mp4"
    out.parent.mkdir(exist_ok=True)
    npx = shutil.which("npx") or shutil.which("npx.cmd") or "npx.cmd"
    run([npx, "remotion", "render", "src/index.ts", CFG["project"]["composition"],
         out, f"--concurrency=4", "--codec=h264", f"--crf={v['crf']}"],
        cwd=PROMO, env={"TEMP": str(tmp), "TMP": str(tmp)}, label="渲染 · Remotion")


def stage_mix(name):
    v = CFG["voice"]
    src = PROMO / "out" / f"{name}-raw.mp4"
    dst = PROMO / "out" / f"{name}-final.mp4"
    run([FF, "-y", "-hide_banner", "-loglevel", "error", "-i", src,
         "-af", f"loudnorm=I={v['lufs']}:TP={v['true_peak']}:LRA={v['lra']},alimiter=limit=0.79:level=disabled:attack=5:release=60",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", dst], label="混音 · loudnorm")
    print(f"  成片 → {dst}")


def stage_check(name):
    run([PY, HERE / "check.py", name], label="质检")


def stage_plan(name):
    """不配音，先算这条稿子会做多长；mode=target 时给出反推建议。"""
    script = json.loads(script_path().read_text(encoding="utf-8-sig"))
    chars = lambda s: len(re.sub(r"[^\u4e00-\u9fa5A-Za-z0-9]", "", s))
    lo, hi = CFG["voice"]["target_cps"]
    cps_mid = (lo + hi) / 2
    d = CFG["video"]["duration"]

    total = 0
    print(f"\n稿件预估 · {CFG['project']['script']}   语速基准 {cps_mid:.2f} 字/秒")
    print("─" * 62)
    print(f"{'章':<10}{'句':>4}{'字':>6}{'预计秒':>9}{'累计':>8}")
    for ch in script["chapters"]:
        c = sum(chars(l["text"]) for l in ch["lines"])
        est = c / cps_mid
        total += est
        print(f"{ch['label']:<10}{len(ch['lines']):>4}{c:>6}{est:>9.1f}{total:>8.1f}")
    n_lines = sum(len(ch["lines"]) for ch in script["chapters"])
    n_chars = sum(chars(l["text"]) for ch in script["chapters"] for l in ch["lines"])
    gap_total = CFG["voice"]["gap_between_chapters"] * len(script["chapters"])
    total += gap_total
    print("─" * 62)
    print(f"{'合计':<10}{n_lines:>4}{n_chars:>6}{total:>9.1f}{'':>8}   （含章节间隔 {gap_total:.1f}s）")

    if d["mode"] == "target":
        t = d["target_sec"]
        tol = d["tolerance_pct"] / 100
        need = t * cps_mid
        print(f"\n目标 {t}s（±{d['tolerance_pct']}% → {t*(1-tol):.0f}–{t*(1+tol):.0f}s）")
        print(f"  需要字数 ≈ {need:.0f}    当前 {n_chars}    差额 {n_chars - need:+.0f} 字")
        if abs(total - t) / t > tol:
            rate = CFG["voice"]["rate"] * (total / t)
            print(f"  两条路：① 改字数到 {need:.0f}  ② 语速 rate {CFG['voice']['rate']} → {rate:.2f}")
        else:
            print("  ✓ 当前稿子就在目标区间内")
    else:
        print(f"\nmode=auto：时长由稿子决定（{total:.0f}s），不限上限。")
        print(f"  想改成固定时长：config.json → video.duration.mode = \"target\"，target_sec = 你要的秒数")


STAGES = {
    "plan": stage_plan,
    "voice": stage_voice,
    "align": stage_align,
    "build": stage_build,
    "render": stage_render,
    "mix": stage_mix,
    "check": stage_check,
}


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(1)
    stage = sys.argv[1]
    name = sys.argv[2] if len(sys.argv) > 2 else CFG["project"]["ep"]
    if len(sys.argv) > 3:
        CFG["project"]["script"] = sys.argv[3]   # 临时换稿：run.py all cardtest scripts/script-cardtest.json
    order = ["voice", "align", "build", "render", "mix", "check"]
    todo = order if stage == "all" else [stage]
    for s in todo:
        if s not in STAGES:
            raise SystemExit(f"未知阶段: {s}（可用: all / {' / '.join(order)}）")
        STAGES[s](name)
    print("\n完成。")


if __name__ == "__main__":
    main()

