"""通用 spec.json → 剪映可编辑工程（P0）。

与 jy_from_film.py 的区别：后者只认 film.json（凯哥式 panels/lines），
本脚本吃的是定稿 §4 的通用 spec（meta/voice/subs/sections/scenes），
MP4 渲染与剪映共用这一份时间轴 —— 这就是 P0「合流」的核心。

轨道映射（对应定稿 §0 交付口径「画面轨 + 字幕轨 + 配音轨」）：
  scenes[].assets[].file   -> video 轨「底板<slot>」，按 s/e 铺满 + 1.0→1.035 慢推
  scenes[].head/bullets/msgs -> text 轨「元素N」，逐句弹入（同轨不重叠，按序号分轨）
  subs[]                   -> text 轨「字幕」，白字黑边贴底
  voice.wav                -> audio 轨「配音」，首尾淡入淡出

复用 jy_from_film.py 的纯函数（pct/pct_y/size_of/_fill_gaps/_fill_across），
不复制、不改写，保证两套版式的坐标换算一致。

用法：
  python tools/jy_from_spec.py --spec qa2/replica/out/q6.spec.json --dry-run
  python tools/jy_from_spec.py --spec deliver/<片名>/spec.json --name <片名>   # 真建草稿
  python tools/jy_from_spec.py --spec ... --spec-out jy_spec.json              # 只导出 jy spec

产物：草稿根下 <name>/，剪映里直接打开继续手调；素材本地化进 assets/。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
VIDEO = HERE.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import jy_from_film as JF  # noqa: E402  —— 复用纯函数与常量

PX_TO_SIZE = JF.PX_TO_SIZE
SUB_SIZE = JF.SUB_SIZE
SUB_Y = JF.SUB_Y


def _resolve(spec: dict, rel: str) -> str:
    """把 spec 里相对 deliver_dir / spec 所在目录的素材路径转成绝对路径字符串。

    剪映 validate_spec 只要求 path 非空，不检查存在；dry-run 时允许素材还没生成。
    """
    if not rel:
        return ""
    p = pathlib.Path(rel)
    if p.is_absolute():
        return str(p)
    base = spec.get("_base_dir") or VIDEO
    return str((pathlib.Path(base) / p).resolve())


def _text_item(text: str, s: float, e: float, *, size: float = SUB_SIZE,
               bold: bool = True, color: str = "#FFFFFF", position=(0, SUB_Y),
               border=None, bg=None, anim_in=None, max_line_width=0.82) -> dict:
    it = {
        "text": text,
        "start": round(s, 3),
        "duration": round(max(0.2, e - s), 3),
        "size": size,
        "bold": bold,
        "color": color,
        "align": 1,
        "position": list(position),
        "auto_wrapping": True,
        "max_line_width": max_line_width,
    }
    if border is not None:
        it["border"] = border
    if bg is not None:
        it["bg"] = bg
    keyframes = []
    if anim_in:
        it["anim_in"] = anim_in
    # 逐句弹入：alpha 0→1
    keyframes.append({"prop": "alpha", "t": round(s, 3), "v": 0.0})
    keyframes.append({"prop": "alpha", "t": round(s + 0.27, 3), "v": 1.0})
    if keyframes:
        it["keyframes"] = keyframes
    return it


def build_jy_spec(spec: dict, name: str, with_elements: bool = True) -> dict:
    """通用 spec → jy_draft.build() 的输入 dict。"""
    meta = spec.get("meta") or {}
    total = float(meta.get("target_duration") or meta.get("src_duration") or 0)
    sub_y_raw = None
    tracks: list[dict] = []

    # ---- 1) 画面轨：scenes[].assets[] 按 slot 分轨，同轨不重叠 ----
    lanes: dict[str, list] = {}
    for sc in spec.get("scenes") or []:
        s, e = float(sc["s"]), float(sc["e"])
        for a in sc.get("assets") or []:
            slot = a.get("slot") or "bg"
            f = a.get("file")
            if not f:
                continue
            lanes.setdefault(slot, []).append({
                "path": _resolve(spec, f),
                "start": round(s, 3),
                "duration": round(max(0.2, e - s), 3),
                "scale": 1.0,
                "keyframes": [
                    {"prop": "scale", "t": round(s, 3), "v": 1.0},
                    {"prop": "scale", "t": round(e, 3), "v": 1.035},
                ],
            })
    for slot in sorted(lanes):
        items = lanes[slot]
        JF._fill_gaps(items, total)                       # 单轨吃小空档防黑闪
        tracks.append({"type": "video", "name": f"底板_{slot}", "items": items})
    if tracks:
        JF._fill_across(tracks, total)                    # 跨轨交界补完

    # ---- 2) 元素轨：head / bullets / msgs 逐句弹入，按屏内序号分轨 ----
    if with_elements:
        el_lanes: dict[int, list] = {}
        for sc in spec.get("scenes") or []:
            s, e = float(sc["s"]), float(sc["e"])
            chunks: list[str] = []
            if sc.get("kicker"):
                chunks.append(str(sc["kicker"]))
            if sc.get("head"):
                chunks.append(str(sc["head"]))
            for b in sc.get("bullets") or []:
                chunks.append(str(b))
            for m in sc.get("msgs") or []:
                t = m.get("text") if isinstance(m, dict) else str(m)
                if t:
                    chunks.append(t)
            for i, text in enumerate(chunks):
                # 同屏多句按 0.9s 间隔起，不越过屏尾
                at = s + i * 0.9
                if at >= e:
                    break
                el_lanes.setdefault(i, []).append(
                    _text_item(text, at, e, size=JF.size_of(60),
                               color="#17140F",
                               position=(JF.pct(70), JF.pct_y(40)),
                               bg={"color": "#FFFFFF", "alpha": 1.0,
                                   "style": 1, "round_radius": 0.10},
                               border={"color": "#17140F", "width": 6, "alpha": 1.0},
                               anim_in={"name": "弹入", "duration": 0.35},
                               max_line_width=0.46))
        for i in sorted(el_lanes):
            tracks.append({"type": "text", "name": f"元素{i + 1}", "items": el_lanes[i]})

    # ---- 3) 字幕轨：subs[] 白字黑边，sub=false 跳过 ----
    layout_sub_y = None
    for sc in spec.get("scenes") or []:
        ly = (sc.get("layout") or {}).get("sub_y")
        if ly is not None:
            layout_sub_y = float(ly)
            break
    sub_items = []
    for ln in spec.get("subs") or []:
        if ln.get("sub") is False:
            continue
        text = (ln.get("text") or "").strip()
        if not text:
            continue
        # 若 layout 给了像素 y（如 640/720），换算成剪映 transform_y
        if layout_sub_y is not None and meta.get("h"):
            y_pct = 100.0 * layout_sub_y / float(meta["h"])
            pos = (0, JF.pct_y(y_pct))
        else:
            pos = (0, SUB_Y)
        sub_items.append(_text_item(
            text, float(ln["s"]), float(ln["e"]),
            border={"color": "#000000", "width": 42, "alpha": 1.0},
            position=pos))
    if sub_items:
        tracks.append({"type": "text", "name": "字幕", "items": sub_items})

    # ---- 4) 配音轨：voice.wav（克隆产物）；没有就留空并提示 ----
    voice = spec.get("voice") or {}
    wav = voice.get("wav")
    if wav:
        tracks.append({"type": "audio", "name": "配音", "items": [{
            "path": _resolve(spec, wav),
            "start": 0.0,
            "duration": round(total, 3),
            "volume": 1.0,
            "fade": {"in": 0.15, "out": 0.3},
        }]})

    jy = spec.get("jianying") or {}
    return {
        "name": name,
        "width": int(meta.get("w") or 1280),
        "height": int(meta.get("h") or 720),
        "fps": int(meta.get("fps") or 30),
        "replace": True,
        "localize": bool(jy.get("localize", True)),
        "tracks": tracks,
    }


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True, help="通用 spec.json 路径")
    ap.add_argument("--name", default="", help="剪映草稿名（默认取 spec.meta.name / 文件名）")
    ap.add_argument("--no-elements", action="store_true", help="只出底板+字幕+配音")
    ap.add_argument("--spec-out", default="", help="把 jy spec 另存一份便于改")
    ap.add_argument("--dry-run", action="store_true", help="不建草稿、不依赖剪映目录、不联网")
    a = ap.parse_args(argv[1:])

    spec_path = pathlib.Path(a.spec).resolve()
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    spec["_base_dir"] = str(spec_path.parent)
    meta = spec.get("meta") or {}
    name = a.name or meta.get("name") or spec_path.stem.replace(".spec", "")

    jy_spec = build_jy_spec(spec, name, with_elements=not a.no_elements)

    if a.spec_out:
        out = pathlib.Path(a.spec_out)
        # _base_dir 是内部字段，不落盘
        out.write_text(json.dumps(jy_spec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"jy spec 已存 {out}")

    import jy_draft
    errs = jy_draft.validate_spec({**jy_spec, "drafts_root": "DRY" if a.dry_run else ""})
    # validate_spec 需要 drafts_root 非空；dry 用占位过校验，真跑下面覆盖
    if a.dry_run:
        print(f"[dry-run] 不联网、不建草稿、不花钱。片名={name}  "
              f"时长={meta.get('target_duration')}s  {meta.get('w')}x{meta.get('h')}@{meta.get('fps')}fps")
        for tr in jy_spec["tracks"]:
            print(f"  {tr['type']:6s} {tr['name']:12s} {len(tr['items']):4d} 段")
        print(f"[dry-run] 轨数={len(jy_spec['tracks'])} · "
              f"配音轨={'有' if any(t['name']=='配音' for t in jy_spec['tracks']) else '缺（voice.wav 未填，P0 正常）'}")
        if errs:
            print("  [dry-run] 契约校验提示（占位 drafts_root 引起的可忽略）：")
            for e in errs:
                print("   -", e)
        return 0

    info = jy_draft.load_env()
    jy_spec["drafts_root"] = info["drafts_root"]
    print(f"环境：剪映 {info['app_version']} / 草稿根 {jy_spec['drafts_root']}")
    for tr in jy_spec["tracks"]:
        print(f"  {tr['type']:6s} {tr['name']:12s} {len(tr['items']):4d} 段")
    jy_draft.build(jy_spec)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
