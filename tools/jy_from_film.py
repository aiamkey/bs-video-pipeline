"""把 lbr-promo 的 film.json 转成剪映工程（可手工精修的版本）。

凯哥式结构在剪映里的对应关系：
  底板（panel.bg 图）        -> 视频轨，每屏一段，1.000→1.035 慢推关键帧，屏间硬切无转场
  元素（label/bubble/num）  -> 文字轨「元素」，色块背景 + 逐句弹入（alpha 0→1 + 缩放回弹）
  字幕（逐句）              -> 文字轨「字幕」，白字黑边，距底固定
  配音                      -> 音频轨，首尾 0.15s 淡入淡出

用法：
  python tools/jy_from_film.py                        # 用 EP02 的 film.json 生成草稿
  python tools/jy_from_film.py --name EP02_jy --no-elements

产物：草稿根下 <name>/，剪映里直接打开即可继续手调。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
VIDEO = HERE.parent
PROMO = VIDEO / "lbr-promo"
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

# 剪映里 text size ≈ 像素 / 4.2（1280x720 实测标定）
PX_TO_SIZE = 4.2
SUB_SIZE = 9
SUB_Y = -0.36

ICON_TEXT = {"cross": "✕", "check": "✓", "phone": "📱", "house": "🏠", "family": "👨‍👩‍👦",
             "clock": "⏰", "money": "💰", "up": "↑", "down": "↓", "arrow": "→"}


def pct(v: float) -> float:
    """百分比坐标 -> 剪映 transform（-1..1）"""
    return round((float(v) - 50.0) / 50.0, 3)


def size_of(px: float) -> float:
    return round(float(px) / PX_TO_SIZE, 1)


def load(film_path: pathlib.Path) -> dict:
    return json.loads(film_path.read_text(encoding="utf-8"))


def build_spec(film: dict, name: str, with_elements: bool = True) -> dict:
    pub = PROMO / "public"
    panels = film.get("panels") or []
    tracks: list[dict] = []

    # 1) 底板
    bg_items = []
    for p in panels:
        bg = p.get("bg")
        if not bg:
            continue
        seg = {
            "path": str((pub / bg).resolve()),
            "start": round(p["start"], 3),
            "duration": round(p["end"] - p["start"], 3),
            "scale": 1.0,
            "keyframes": [
                {"prop": "scale", "t": round(p["start"], 3), "v": 1.0},
                {"prop": "scale", "t": round(p["end"], 3), "v": 1.035},
            ],
        }
        bg_items.append(seg)
    if bg_items:
        tracks.append({"type": "video", "name": "底板", "items": bg_items})

    # 2) 元素（panel 内逐句弹入）
    #    剪映同一轨道不允许片段重叠，而元素要"停留到屏尾"，
    #    所以按 panel 内序号分轨：第 1 个元素进「元素1」，第 2 个进「元素2」……
    #    不同屏时间不重叠，同一条轨可以跨屏复用。
    if with_elements:
        lanes: dict[int, list] = {}
        for p in panels:
            for i, el in enumerate(p.get("elements") or []):
                at = p["start"] + float(el.get("at", 0))
                dur = max(0.4, p["end"] - at)
                kind = el.get("kind")
                text = el.get("text") or ICON_TEXT.get(el.get("name", ""), "")
                if not text:
                    continue
                item = {
                    "text": text,
                    "start": round(at, 3),
                    "duration": round(dur, 3),
                    "size": size_of(el.get("size", 60)),
                    "position": [pct(el.get("x", 70)), pct(el.get("y", 40))],
                    "align": 1,
                    "bold": True,
                    "keyframes": [
                        {"prop": "alpha", "t": round(at, 3), "v": 0.0},
                        {"prop": "alpha", "t": round(at + 0.27, 3), "v": 1.0},
                    ],
                }
                if kind == "label":
                    item.update(color="#FFFFFF",
                                bg={"color": el.get("color", "#C8342B"), "alpha": 1.0,
                                    "style": 1, "round_radius": 0.06},
                                anim_in={"name": "弹入", "duration": 0.35})
                elif kind == "bubble":
                    item.update(color="#17140F",
                                bg={"color": "#FFFFFF", "alpha": 1.0,
                                    "style": 1, "round_radius": 0.10},
                                border={"color": "#17140F", "width": 6, "alpha": 1.0},
                                anim_in={"name": "弹入", "duration": 0.35})
                elif kind == "num":
                    item.update(color=el.get("color", "#C8342B"),
                                anim_in={"name": "放大", "duration": 0.35})
                elif kind == "dot":
                    item.update(color="#17140F", size=size_of(el.get("size", 40)),
                                anim_in={"name": "渐显", "duration": 0.3})
                else:
                    item.update(color=el.get("color", "#17140F"),
                                anim_in={"name": "弹入", "duration": 0.35})
                lanes.setdefault(i, []).append(item)
        for i in sorted(lanes):
            tracks.append({"type": "text", "name": f"元素{i + 1}", "items": lanes[i]})

    # 3) 字幕（逐句，凯哥式白字黑边）
    sub_items = []
    for ln in film.get("lines") or []:
        text = (ln.get("text") or "").strip()
        if not text:
            continue
        sub_items.append({
            "text": text,
            "start": round(ln["start"], 3),
            "duration": round(max(0.4, ln["end"] - ln["start"]), 3),
            "size": SUB_SIZE,
            "bold": True,
            "color": "#FFFFFF",
            "align": 1,
            "position": [0, SUB_Y],
            "border": {"color": "#000000", "width": 42, "alpha": 1.0},
        })
    if sub_items:
        tracks.append({"type": "text", "name": "字幕", "items": sub_items})

    # 4) 配音
    voice = film.get("voice")
    if voice:
        tracks.append({"type": "audio", "name": "配音", "items": [{
            "path": str((pub / voice).resolve()),
            "start": 0.0,
            "duration": round(film.get("totalSeconds") or 0, 3),
            "volume": 1.0,
            "fade": {"in": 0.15, "out": 0.3},
        }]})

    return {
        "name": name,
        "width": 1280,
        "height": 720,
        "fps": int(film.get("fps") or 30),
        "replace": True,
        "tracks": tracks,
    }


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--film", default=str(PROMO / "src/data/film.json"))
    ap.add_argument("--name", default="EP02_剪映工程")
    ap.add_argument("--no-elements", action="store_true", help="只出底板+字幕+配音")
    ap.add_argument("--spec-out", default="", help="把生成的 spec 另存一份便于改")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv[1:])

    film = load(pathlib.Path(a.film))
    spec = build_spec(film, a.name, with_elements=not a.no_elements)

    if a.spec_out:
        pathlib.Path(a.spec_out).write_text(
            json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"spec 已存 {a.spec_out}")

    import jy_draft
    info = jy_draft.load_env()
    spec.setdefault("drafts_root", info["drafts_root"])
    if a.dry_run:
        spec["dry_run"] = True
    print(f"环境：剪映 {info['app_version']} / 草稿根 {spec['drafts_root']}")
    for tr in spec["tracks"]:
        print(f"  {tr['type']:6s} {tr['name']:6s} {len(tr['items'])} 段")
    jy_draft.build(spec)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
