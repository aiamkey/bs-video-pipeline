"""把「无字幕成片」按卡片句切出静帧，垫进剪映工程，消掉黑场。

为什么需要：
  film.json 里只有 panel 句有底板图；非 panel 的卡片句（copy / section / board /
  stat / slides / outro…）在剪映工程里原本没有任何视频段 → 时间轴上是黑屏。
  EP02 实测：117.4s 里 66.3s（56%）是黑场。

做法（不改设计、不改版式，最省事）：
  1. Remotion 渲一条「无字幕版」成片（DataFilmNoSub）
  2. 对每一条非 panel 句，按中点取一帧 PNG → lbr-promo/public/cards/l{序号}.png
  3. jy_from_film.py 自动把这些 PNG 当"照片"铺到视频轨，铺满全片

用法：
  python tools/jy_cards.py                 # 抽帧（默认用已有的 out/ep02-nosub.mp4）
  python tools/jy_cards.py --render        # 先渲染无字幕版再抽帧
  python tools/jy_cards.py --list          # 只打印会抽哪些帧
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
VIDEO = HERE.parent
PROMO = VIDEO / "lbr-promo"
FILM = PROMO / "src/data/film.json"
NOSUB = PROMO / "out/ep02-nosub.mp4"
CARDS = PROMO / "public/cards"


def ffmpeg() -> str:
    cfg = PROMO / "pipeline/config.json"
    if cfg.exists():
        p = json.loads(cfg.read_text(encoding="utf-8")).get("paths", {}).get("ffmpeg")
        if p and pathlib.Path(p).exists():
            return p
    return "ffmpeg"


def render_nosub() -> None:
    env = dict(**__import__("os").environ)
    tmp = PROMO / ".tmp-remotion"
    tmp.mkdir(exist_ok=True)
    env["TEMP"] = env["TMP"] = str(tmp)
    cmd = ["npx", "remotion", "render", "src/index.ts", "DataFilmNoSub",
           "out/ep02-nosub.mp4", "--concurrency=4", "--codec=h264", "--crf=20"]
    print("渲染无字幕版：", " ".join(cmd))
    subprocess.run(cmd, cwd=str(PROMO), env=env, check=True)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--film", default=str(FILM))
    ap.add_argument("--render", action="store_true", help="先渲染无字幕版成片")
    ap.add_argument("--list", action="store_true", help="只列出要抽的帧")
    a = ap.parse_args(argv[1:])

    film = json.loads(pathlib.Path(a.film).read_text(encoding="utf-8"))
    lines = film["lines"]
    jobs = []
    for i, ln in enumerate(lines):
        if ln.get("panel"):
            continue                      # panel 句有底板图，不需要静帧
        text = (ln.get("text") or "").strip()
        if not text:
            continue
        mid = (ln["start"] + ln["end"]) / 2
        jobs.append((i, mid, text))

    print(f"卡片句 {len(jobs)} 条（非 panel），总覆盖 "
          f"{sum(1 for _ in jobs)} 段")
    if a.list:
        for i, mid, text in jobs:
            print(f"  l{i:02d}  {mid:7.2f}s  {text[:22]}")
        return 0

    if a.render or not NOSUB.exists():
        render_nosub()
    if not NOSUB.exists():
        print(f"缺少 {NOSUB}，先跑 --render", file=sys.stderr)
        return 1

    CARDS.mkdir(parents=True, exist_ok=True)
    exe = ffmpeg()
    done = 0
    for i, mid, _text in jobs:
        out = CARDS / f"l{i:02d}.png"
        cmd = [exe, "-y", "-hide_banner", "-loglevel", "error",
               "-ss", f"{mid:.3f}", "-i", str(NOSUB),
               "-frames:v", "1", str(out)]
        r = subprocess.run(cmd, capture_output=True)
        if r.returncode != 0:
            print(f"  失败 l{i:02d}: {r.stderr.decode('utf-8', 'ignore')[:120]}")
            continue
        done += 1
    print(f"抽帧完成 {done}/{len(jobs)} → {CARDS}")
    return 0 if done == len(jobs) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
