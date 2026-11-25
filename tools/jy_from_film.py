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
    """百分比坐标 -> 剪映 transform_x（-1..1，右为正）"""
    return round((float(v) - 50.0) / 50.0, 3)


def pct_y(v: float) -> float:
    """百分比坐标（0=画面顶部）-> 剪映 transform_y（**上为正**，所以符号要翻）

    证据：pyJianYingDraft 的 import_srt 默认 ClipSettings(transform_y=-0.8)，
    剪映导入字幕就落在画面底部 —— 负数在下、正数在上。
    Remotion 里 top:24% 是"靠上"，换到剪映必须是 +0.52，不是 -0.52。
    """
    return round((50.0 - float(v)) / 50.0, 3)


def size_of(px: float) -> float:
    return round(float(px) / PX_TO_SIZE, 1)


def load(film_path: pathlib.Path) -> dict:
    return json.loads(film_path.read_text(encoding="utf-8"))


def _sfx_items(pub: pathlib.Path) -> list[dict]:
    """读 src/data/sfx.json（pipeline/sfx.py 产物）→ 剪映音频片段。

    剪映同一轨道片段不能重叠，这里按 start 顺序排；若前一条尾巴压到后一条，
    就把前一条裁短（音效都是点状的，裁尾巴听不出来）。
    """
    path = PROMO / "src/data/sfx.json"
    if not path.is_file():
        return []
    try:
        events = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return []

    items: list[dict] = []
    for ev in sorted(events, key=lambda e: float(e.get("t") or 0)):
        start = round(float(ev.get("t") or 0), 3)
        dur = round(float(ev.get("duration") or 0.5), 3)
        if items:
            prev = items[-1]
            prev_end = prev["start"] + prev["duration"]
            if start < prev_end:                      # 同轨不能重叠
                prev["duration"] = round(max(0.08, start - prev["start"]), 3)
                prev_end = prev["start"] + prev["duration"]
            if start - prev_end < 0.04:               # 贴太近会让剪映算成重叠
                start = round(prev_end + 0.04, 3)
        items.append({
            "path": str((pub / "audio" / ev["file"]).resolve()),
            "start": start,
            "duration": dur,
            "volume": round(float(ev.get("volume") or 0.1), 4),
        })
    return items


def _fill_gaps(items: list[dict], total: float, max_gap: float = 1.0) -> list[dict]:
    """把相邻视频段之间的小空档吃掉（≤max_gap 秒），避免剪映里出现黑闪。

    film.json 的句子之间有静音间隙（0.15–0.5s），逐段照搬会在时间轴上留黑场。
    凯哥原片是没有黑闪的，所以这里把前一段延长到下一段的起点。
    """
    items.sort(key=lambda x: x["start"])
    for i, it in enumerate(items):
        end = it["start"] + it["duration"]
        nxt = items[i + 1]["start"] if i + 1 < len(items) else total
        if 0 <= nxt - end <= max_gap:
            it["duration"] = round(nxt - it["start"], 3)
            end = nxt
        kfs = it.get("keyframes") or []
        if len(kfs) >= 2:
            kfs[-1]["t"] = round(it["start"] + it["duration"], 3)
    return items


def _fill_across(tracks: list[dict], total: float, max_gap: float = 1.0) -> None:
    """跨轨道吃空档：底板与卡片是两条轨，同一条轨各自补完，交界处仍会留黑。
    这里把两条轨的段按时间排在一起，谁在前面就把谁延长到下一段起点。"""
    merged = []
    for tr in tracks:
        if tr["type"] != "video":
            continue
        for it in tr["items"]:
            merged.append(it)
    merged.sort(key=lambda x: x["start"])
    for i, it in enumerate(merged):
        end = it["start"] + it["duration"]
        nxt = merged[i + 1]["start"] if i + 1 < len(merged) else total
        if 0 <= nxt - end <= max_gap:
            it["duration"] = round(nxt - it["start"], 3)
        kfs = it.get("keyframes") or []
        if len(kfs) >= 2:
            kfs[-1]["t"] = round(it["start"] + it["duration"], 3)


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

    # 1b) 卡片静帧（copy / section / board / stat / slides / outro …）
    #     这些句子在 film.json 里没有底板图，剪映里原本是黑场。
    #     由 tools/jy_cards.py 从「无字幕版成片」按中点抽帧到 public/cards/l{序号}.png。
    card_items = []
    for i, ln in enumerate(film.get("lines") or []):
        if ln.get("panel"):
            continue
        png = pub / "cards" / f"l{i:02d}.png"
        if not png.exists():
            continue
        st, en = round(ln["start"], 3), round(ln["end"], 3)
        card_items.append({
            "path": str(png.resolve()),
            "start": st,
            "duration": round(max(0.2, en - st), 3),
            "scale": 1.0,
            "keyframes": [
                {"prop": "scale", "t": st, "v": 1.0},
                {"prop": "scale", "t": en, "v": 1.02},
            ],
        })
    if card_items:
        tracks.append({"type": "video", "name": "卡片", "items": card_items})

    # 视频层跨轨吃空档，防止剪映里黑闪（底板与卡片交界处最容易漏）
    total = float(film.get("totalSeconds") or 0)
    _fill_across(tracks, total)

    # 2) 元素（panel 内逐句弹入）
    #    剪映同一轨道不允许片段重叠，而元素要"停留到屏尾"，
    #    所以按 panel 内序号分轨：第 1 个元素进「元素1」，第 2 个进「元素2」……
    #    不同屏时间不重叠，同一条轨可以跨屏复用。
    if with_elements:
        lanes: dict[int, list] = {}
        icons: list = []          # icon/arrow/dot 走图片轨（PNG 比 emoji 可控）
        for p in panels:
            for i, el in enumerate(p.get("elements") or []):
                at = p["start"] + float(el.get("at", 0))
                dur = max(0.4, p["end"] - at)
                kind = el.get("kind")

                # ---- 图标类：用 public/textures/icons/<name>.png 当图片贴上去
                if kind in ("icon", "arrow", "dot"):
                    png = pub / "textures" / "icons" / f"{el.get('name') or kind}.png"
                    if png.is_file():
                        px = float(el.get("size") or 84)
                        icons.append({
                            "path": str(png.resolve()),
                            "start": round(at, 3),
                            "duration": round(dur, 3),
                            # 剪映把方形图按高度铺满画布 → 想要 px 像素，scale = px / 720
                            "scale": round(px / 720.0, 4),
                            "position": [pct(el.get("x", 70)), pct_y(el.get("y", 40))],
                            "keyframes": [
                                {"prop": "alpha", "t": round(at, 3), "v": 0.0},
                                {"prop": "alpha", "t": round(at + 0.24, 3), "v": 1.0},
                                {"prop": "scale", "t": round(at, 3), "v": round(px / 720.0 * 1.15, 4)},
                                {"prop": "scale", "t": round(at + 0.26, 3), "v": round(px / 720.0, 4)},
                            ],
                        })
                        continue

                text = el.get("text") or ICON_TEXT.get(el.get("name", ""), "")
                if not text:
                    continue
                # 元素宽度：Remotion 里 bubble 有 w（px），剪映没有"定宽"，只有
                # max_line_width（占屏宽比例）。不设的话默认 0.82，一句话会横贯全屏。
                w_px = float(el.get("w") or 0)
                maxw = round(min(0.46, max(0.16, w_px / 1280.0)), 3) if w_px else 0.24
                item = {
                    "text": text,
                    "start": round(at, 3),
                    "duration": round(dur, 3),
                    "size": size_of(el.get("size", 60)),
                    "position": [pct(el.get("x", 70)), pct_y(el.get("y", 40))],
                    "align": 1,
                    "bold": True,
                    "auto_wrapping": True,
                    "max_line_width": maxw,
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
        # 图标单独一条视频轨（同轨不重叠；跨屏时间不冲突，但要按 start 排序后压尾）
        if icons:
            icons.sort(key=lambda x: x["start"])
            fixed = []
            for ic in icons:
                if fixed:
                    prev = fixed[-1]
                    prev_end = prev["start"] + prev["duration"]
                    if ic["start"] < prev_end:
                        ic["start"] = round(prev_end + 0.04, 3)
                fixed.append(ic)
            tracks.append({"type": "video", "name": "图标", "items": fixed})

    # 3) 字幕（逐句，凯哥式白字黑边）；sub=false 的卡片句不出字幕（卡片大字已等同这句）
    sub_items = []
    for ln in film.get("lines") or []:
        if ln.get("sub") is False:
            continue
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

    # 5) 音效（pipeline/sfx.py 生成；一个音频轨里顺序排，剪映同轨不能重叠）
    sfx_items = _sfx_items(pub)
    if sfx_items:
        tracks.append({"type": "audio", "name": "音效", "items": sfx_items})

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
