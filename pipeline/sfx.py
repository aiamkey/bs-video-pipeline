# -*- coding: utf-8 -*-
"""音效层：读 film.json，按"元素弹入 / 换屏 / 数字 / 结论"挂音效事件。

规则来自 pipeline/JIANYING.md §13（凯哥原片实测：**全片不铺 BGM**，只有点状音效）：

| 时刻 | 音效 | 音量 |
|---|---|---|
| 换屏（panel 开始，首屏除外） | whoosh-fast | −20 dB |
| panel 元素首现（bubble/label/icon/arrow） | pop | −18 dB |
| 数字元素（num） | sparkle | −16 dB |
| 结论块（box） | impact-cine | −22 dB |
| 章节卡 / 结尾 | transition-snap | −19 dB |

输出 `lbr-promo/src/data/sfx.json`：`[{t, file, gain, why, panel}]`，
由 `tools/jy_from_film.py` 变成剪映的「音效」音频轨（gain dB → 线性 volume）。

    python lbr-promo\\pipeline\\sfx.py            # 读 film.json → 写 sfx.json
    python lbr-promo\\pipeline\\sfx.py --dry-run  # 只打印
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROMO = ROOT / "lbr-promo"
FILM = PROMO / "src" / "data" / "film.json"
OUT = PROMO / "src" / "data" / "sfx.json"
AUDIO_DIR = PROMO / "public" / "audio"

DEBOUNCE = 0.20          # 同 0.2s 内多条只留一条（取更响的）

RULES = {
    "panel_start": ("whoosh-fast.mp3", -20.0, 1.2),
    "element": ("pop.mp3", -18.0, 0.5),
    "num": ("sparkle.mp3", -16.0, 1.2),
    "box": ("impact-cine.mp3", -22.0, 2.0),
    "section": ("transition-snap.mp3", -19.0, 0.6),
    "outro": ("impact-cine.mp3", -22.0, 2.0),
}


def duration_of(path: Path, ffmpeg: str | None) -> float | None:
    """用 ffmpeg 读音频时长（不引 mutagen）。"""
    if not ffmpeg or not path.is_file():
        return None
    try:
        p = subprocess.run([ffmpeg, "-hide_banner", "-i", str(path)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
    except OSError:
        return None
    for line in (p.stderr or "").splitlines():
        line = line.strip()
        if line.startswith("Duration:"):
            raw = line.split("Duration:")[1].split(",")[0].strip()
            try:
                h, m, s = raw.split(":")
                return int(h) * 3600 + int(m) * 60 + float(s)
            except ValueError:
                return None
    return None


def load_ffmpeg() -> str | None:
    try:
        cfg = json.loads((PROMO / "pipeline" / "config.json").read_text(encoding="utf-8-sig"))
        p = (cfg.get("paths") or {}).get("ffmpeg")
        return p if p and Path(p).is_file() else None
    except (OSError, ValueError):
        return None


def build(film: dict) -> list[dict]:
    events: list[dict] = []
    seen_panel: set[str] = set()

    for panel in film.get("panels") or []:
        pid = panel.get("id") or ""
        if pid and pid not in seen_panel:
            if seen_panel:                       # 首屏开场不 whoosh，留白更有力
                events.append({"t": round(float(panel["start"]), 3),
                               "file": RULES["panel_start"][0],
                               "gain": RULES["panel_start"][1],
                               "cap": RULES["panel_start"][2],
                               "why": f"换屏 {pid}", "panel": pid})
            seen_panel.add(pid)
        for el in panel.get("elements") or []:
            kind = el.get("kind")
            if kind == "num":
                key = "num"
            elif kind == "box":
                key = "box"
            else:
                key = "element"
            t = float(panel["start"]) + float(el.get("at") or 0)
            file, gain, cap = RULES[key]
            events.append({"t": round(t, 3), "file": file, "gain": gain, "cap": cap,
                           "why": f"{pid} · {kind}", "panel": pid})

    for line in film.get("lines") or []:
        card = line.get("card") or {}
        ctype = card.get("type")
        if ctype == "section":
            events.append({"t": round(float(line["start"]), 3), "file": RULES["section"][0],
                           "gain": RULES["section"][1], "cap": RULES["section"][2],
                           "why": f"章节 {card.get('label') or card.get('text') or ''}", "panel": None})
        elif ctype == "outro":
            events.append({"t": round(float(line["start"]), 3), "file": RULES["outro"][0],
                           "gain": RULES["outro"][1], "cap": RULES["outro"][2],
                           "why": "结尾", "panel": None})

    if not events:
        return []

    events.sort(key=lambda e: e["t"])
    merged: list[dict] = []
    for ev in events:
        if merged and ev["t"] - merged[-1]["t"] < DEBOUNCE:
            if ev["gain"] > merged[-1]["gain"]:
                merged[-1] = ev
            continue
        merged.append(ev)
    return merged


def main() -> int:
    ap = argparse.ArgumentParser(description="film.json → 音效事件")
    ap.add_argument("--film", default=str(FILM))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    film = json.loads(Path(a.film).read_text(encoding="utf-8-sig"))
    events = build(film)
    if not events:
        print("没有可挂的音效（film.json 里没有 panels / section / outro）")
        return 1

    ffmpeg = load_ffmpeg()
    missing, durations = [], {}
    for name in {e["file"] for e in events}:
        dur = duration_of(AUDIO_DIR / name, ffmpeg)
        if dur is None:
            missing.append(name)
        else:
            durations[name] = round(dur, 3)
    if missing:
        print("缺音效文件（放 lbr-promo/public/audio/）：" + ", ".join(missing))
        return 1

    for ev in events:
        # 只取前 cap 秒：整条音效（sparkle 4.55s / impact 4.06s）会糊住后面的语音
        ev["duration"] = round(min(durations[ev["file"]], float(ev.get("cap") or 2.0)), 3)
        ev.pop("cap", None)
        ev["volume"] = round(10 ** (ev["gain"] / 20.0), 4)

    total = float(film.get("totalSeconds") or 0)
    density = len(events) / total if total else 0
    print(f"音效事件 {len(events)} 条 / {total:.1f}s → 平均 {density*60:.1f} 条每分钟")
    by_file: dict[str, int] = {}
    for ev in events:
        by_file[ev["file"]] = by_file.get(ev["file"], 0) + 1
    for name, n in sorted(by_file.items(), key=lambda kv: -kv[1]):
        print(f"  {name:22s} {n} 次  {durations[name]:.2f}s  "
              f"{next(e['gain'] for e in events if e['file'] == name):+.0f} dB")
    if density > 20/60:
        print(f"! 密度偏高（> {20/60*60:.0f}/分钟），凯哥是点状的，别糊成一层")

    if a.dry_run:
        for ev in events:
            print(f"  {ev['t']:7.2f}s  {ev['file']:22s} {ev['gain']:+.0f}dB  {ev['why']}")
        return 0

    Path(a.out).write_text(json.dumps(events, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"已写 {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
