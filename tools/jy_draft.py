"""Write a JianYing (剪映 11.x) draft from a simple timeline JSON.

Two stages:
  1. author   -> pyJianYingDraft builds draft_content.json (multi-track, keyframes,
                 text styles, animations, transitions, masks, filters)
  2. finalize -> the 11.5 skill's native bridge encrypts the draft, writes
                 Timelines/*, fixes platform/version, registers it on the home page.

Portable: every path is discovered by tools/jy_env.py (no hard-coded install dir).
Run once per machine:  python tools/jy_env.py --write-env

Usage:
  python tools/jy_draft.py spec.json              # build + finalize + register
  python tools/jy_draft.py spec.json --dry-run    # author only
  python tools/jy_draft.py spec.json --list-enums transition

Spec (JSON, UTF-8, no BOM) — time unit SECONDS, keyframes[].t is absolute:
{
  "name": "EP02_剪映工程", "width": 1280, "height": 720, "fps": 30,
  "drafts_root": "(可省，自动探测)", "replace": true,
  "tracks": [
    {"type": "video", "items": [{
       "path": "C:/.../bg.jpg", "start": 0, "duration": 3.0, "source_start": 0,
       "speed": 1.0, "volume": 1.0,
       "scale": 1.0, "position": [0, 0], "alpha": 1.0, "rotation": 0,
       "keyframes": [{"prop":"scale","t":0,"v":1.0},{"prop":"scale","t":3,"v":1.03}],
       "transition": {"name": "叠化", "duration": 0.5},
       "anim_in":  {"name": "动感放大", "duration": 0.4},
       "anim_out": {"name": "渐隐", "duration": 0.3},
       "fade": {"in": 0.2, "out": 0.2},
       "mask": {"type": "线性", "center_x": 0, "size": 0.5},
       "filter": {"name": "亮肤", "intensity": 30},
       "mix_mode": "滤色", "background_fill": {"type": "blur", "blur": 0.0625}
    }]},
    {"type": "text", "items": [{
       "text": "字幕一行", "start": 0.3, "duration": 2.4,
       "size": 9, "color": "#FFFFFF", "bold": true, "align": 1, "position": [0, -0.35],
       "border": {"color": "#000000", "width": 40, "alpha": 1.0},
       "shadow": {"color": "#000000", "alpha": 0.7, "diffuse": 15, "distance": 5, "angle": -45},
       "bg": {"color": "#000000", "alpha": 0.6, "style": 1, "round_radius": 0.04},
       "letter_spacing": 0, "line_spacing": 0, "vertical": false,
       "anim_in": {"name": "右下擦开", "duration": 0.3},
       "anim_out": {"name": "渐隐", "duration": 0.2},
       "loop_anim": {"name": "发光模糊多行"}
    }]},
    {"type": "audio", "items": [{
       "path": "C:/.../voice.wav", "start": 0, "duration": 3.0,
       "volume": 1.0, "fade": {"in": 0.15, "out": 0.3}
    }]},
    {"type": "sticker", "items": [
       {"resource_id": "7010150000000000000", "start": 1, "duration": 2,
        "scale": 0.4, "position": [0.6, 0.2]}
    ]}
  ]
}

prop: scale | scale_x | scale_y | position_x | position_y | rotation | alpha | volume
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

US = 1_000_000
KP_MAP = {
    "scale": "uniform_scale", "scale_x": "scale_x", "scale_y": "scale_y",
    "position_x": "position_x", "position_y": "position_y",
    "rotation": "rotation", "alpha": "alpha", "volume": "volume",
}


# ------------------------------------------------------------------ portable env

def load_env() -> dict:
    """Discover JianYing env; export JY_* so the native bridge works anywhere.

    剪映 skill（jyai）是**可选**的：没有它也能写明文草稿（剪映自己就能读明文），
    只是少了自动加密与首页登记。所以这里不再因为它缺失就退出。
    """
    import jy_env

    info = jy_env.discover()
    if not info.get("drafts_root"):
        raise SystemExit("找不到剪映草稿目录：先在剪映里随便建一个草稿，或设 JY_DRAFTS_ROOT")

    scripts = info.get("skill_scripts")
    info["have_bridge"] = bool(scripts)
    if scripts:
        os.environ.setdefault("JY_SKILL_SCRIPTS", scripts)
        if info.get("app_version"):
            os.environ.setdefault("JY_APP_VERSION", info["app_version"])
        os.environ.setdefault("JY_DRAFT_NEW_VERSION", info.get("new_version") or "110.0.0")
        if info.get("placeholder"):
            os.environ.setdefault("JY_PLACEHOLDER", info["placeholder"])
        scripts = pathlib.Path(scripts)
        if str(scripts) not in sys.path:
            sys.path.insert(0, str(scripts))
    else:
        print("· 没找到剪映 skill（jyai）：将写明文草稿，剪映照样能打开。")
        print("  想要自动加密 + 首页登记：把 jianying-editor-11-5 放进 ~/.dsh/skills/，"
              "或设 JY_SKILL_SCRIPTS 指向它的 scripts 目录。")
    return info


def hex_rgb(s: str):
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) / 255 for i in (0, 2, 4))


def us(seconds: float) -> int:
    return int(round(float(seconds) * US))


def _enum(enum_cls, name, what: str):
    """Resolve a Chinese/English member name on a metadata enum with a helpful error."""
    if name is None:
        return None
    if not isinstance(name, str):
        return name
    member = getattr(enum_cls, name, None)
    if member is None:
        sample = [x for x in vars(enum_cls) if not x.startswith("_")][:20]
        raise SystemExit(f"未知的{what}名称 {name!r}；可用示例：{sample}")
    return member


_TEXT_EFFECTS: list | None = None


def text_effect_id(name_or_id: str) -> str:
    """花字：接受 resource_id（纯数字）或中文名，查 pipeline/jy_text_effects.json。"""
    global _TEXT_EFFECTS
    if str(name_or_id).isdigit():
        return str(name_or_id)
    if _TEXT_EFFECTS is None:
        path = pathlib.Path(__file__).resolve().parent.parent / "lbr-promo" / "pipeline" / "jy_text_effects.json"
        _TEXT_EFFECTS = json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else []
    for row in _TEXT_EFFECTS:
        if row.get("title") == name_or_id:
            return str(row["id"])
    pool = [r["title"] for r in _TEXT_EFFECTS][:12]
    raise SystemExit(f"未知花字 {name_or_id!r}；共 {len(_TEXT_EFFECTS)} 条，示例：{pool}")


# ------------------------------------------------------------------ author

TRACK_TYPES = {"video", "text", "audio", "sticker", "effect", "filter"}
KEYFRAME_PROPS = {"scale", "scale_x", "scale_y", "position_x", "position_y",
                  "rotation", "alpha", "volume"}


def validate_spec(spec: dict) -> list[str]:
    """轻量契约校验（不引 jsonschema，避免多一个依赖）。返回错误列表，空 = 通过。"""
    errs = []
    if not isinstance(spec, dict):
        return ["spec 必须是 JSON 对象"]
    for key in ("name", "drafts_root"):
        if not spec.get(key):
            errs.append(f"缺必填字段 {key}")
    if errs:
        return errs

    tracks = spec.get("tracks")
    if not isinstance(tracks, list) or not tracks:
        return ["tracks 必须是非空数组"]

    for ti, tr in enumerate(tracks):
        where = f"tracks[{ti}]"
        if not isinstance(tr, dict):
            errs.append(f"{where} 必须是对象")
            continue
        ttype = tr.get("type")
        if ttype not in TRACK_TYPES:
            errs.append(f"{where}.type={ttype!r} 不在 {sorted(TRACK_TYPES)}")
        items = tr.get("items")
        if not isinstance(items, list) or not items:
            errs.append(f"{where}.items 必须是非空数组")
            continue
        for ii, it in enumerate(items):
            at = f"{where}.items[{ii}]"
            dur = it.get("duration")
            if not isinstance(dur, (int, float)) or dur <= 0:
                errs.append(f"{at}.duration 必须是正数（秒）")
            if float(it.get("start", 0)) < 0:
                errs.append(f"{at}.start 不能为负")
            if ttype == "text" and not it.get("text"):
                errs.append(f"{at} 是文字段但没有 text")
            if ttype in ("video", "audio", "sticker", "effect", "filter") and not it.get("path"):
                errs.append(f"{at} 缺 path")
            for ki, kf in enumerate(it.get("keyframes") or []):
                if kf.get("prop") not in KEYFRAME_PROPS:
                    errs.append(f"{at}.keyframes[{ki}].prop={kf.get('prop')!r} 不在 {sorted(KEYFRAME_PROPS)}")
            if it.get("text_effect") and ttype != "text":
                errs.append(f"{at}.text_effect 只能用在文字段")

    if spec.get("beauty") and not isinstance(spec["beauty"], dict):
        errs.append("beauty 必须是对象")
    return errs


def build(spec: dict) -> pathlib.Path:
    errs = validate_spec(spec)
    if errs:
        raise SystemExit("spec 校验失败：\n  - " + "\n  - ".join(errs))

    import pyJianYingDraft as d
    from pyJianYingDraft import KeyframeProperty as KP

    root = spec["drafts_root"]
    folder = d.DraftFolder(root)
    script = folder.create_draft(
        spec["name"], spec.get("width", 1280), spec.get("height", 720),
        fps=spec.get("fps", 30), allow_replace=bool(spec.get("replace", True)),
    )

    made = []
    for tr in spec.get("tracks", []):
        ttype = tr["type"]
        kind = {"video": d.TrackType.video, "audio": d.TrackType.audio,
                "text": d.TrackType.text, "sticker": d.TrackType.sticker,
                "effect": d.TrackType.effect, "filter": d.TrackType.filter}[ttype]
        ref = script.append_track(d.TrackSpec(kind, name=tr.get("name")))

        for it in tr.get("items", []):
            rng = d.Timerange(us(it.get("start", 0)), us(it["duration"]))
            seg = _make_segment(d, ttype, it, rng)
            # 装饰必须在 add_segment 之前：素材收集发生在 add_segment 里
            _decorate(seg, it)
            for kf in it.get("keyframes", []):
                prop = KP_MAP.get(kf["prop"], kf["prop"])
                seg.add_keyframe(getattr(KP, prop), us(kf["t"]), float(kf["v"]))

            script.add_segment(seg, ref)

            made.append((ttype, it.get("text") or pathlib.Path(it.get("path", "")).name,
                         it.get("start", 0), it["duration"], len(it.get("keyframes", []))))

    script.save()
    print(f"作者完成：{len(made)} 个片段 / {len(spec.get('tracks', []))} 条轨")
    for t, label, st, du, nkf in made:
        print(f"  {t:6s} {st:7.2f}s +{du:5.2f}s  kf={nkf}  {label}")

    out = pathlib.Path(root) / spec["name"]

    # 素材本地化：复制进草稿 assets/ 并改写成剪映占位符相对路径（草稿可整目录搬走）
    if spec.get("localize", True) and not spec.get("dry_run"):
        import jy_localize

        li = jy_localize.localize(out)
        print(f"素材本地化：{li['copied']} 个复制进 assets/ · {li['total']} 个素材已改相对路径"
              + (f" · {li['missing']} 个不在本地" if li["missing"] else ""))

    # 美颜/美型/美妆：库不支持的素材，直接写进明文 draft_content.json，再交给 finalize 加密
    if spec.get("beauty") and not spec.get("dry_run"):
        import jy_beauty

        cat = jy_beauty.load_catalog()
        ops, target = jy_beauty.ops_from_spec(cat, spec["beauty"])
        if ops:
            info = jy_beauty.apply_beauty(out, ops, target=target)
            print(f"美化写入：{info['applied']} 条素材 → {info['segments']} 个视频片段"
                  f"（占位 {info['placeholder'][:8]}）")

    if spec.get("dry_run"):
        return out
    return finalize(out, plain=bool(spec.get("plain")))


def _make_segment(d, ttype, it, rng):
    if ttype == "text":
        style = d.TextStyle(
            size=float(it.get("size", 9)),
            bold=bool(it.get("bold", False)),
            italic=bool(it.get("italic", False)),
            underline=bool(it.get("underline", False)),
            color=hex_rgb(it.get("color", "#FFFFFF")),
            alpha=float(it.get("alpha", 1.0)),
            align=int(it.get("align", 1)),
            vertical=bool(it.get("vertical", False)),
            letter_spacing=int(it.get("letter_spacing", 0)),
            line_spacing=int(it.get("line_spacing", 0)),
            auto_wrapping=bool(it.get("auto_wrapping", True)),
            max_line_width=float(it.get("max_line_width", 0.82)),
        )
        border = shadow = bg = None
        if it.get("border"):
            b = it["border"]
            border = d.TextBorder(alpha=float(b.get("alpha", 1.0)),
                                  color=hex_rgb(b.get("color", "#000000")),
                                  width=float(b.get("width", 40)))
        if it.get("shadow"):
            s = it["shadow"]
            shadow = d.TextShadow(alpha=float(s.get("alpha", 0.7)),
                                  color=hex_rgb(s.get("color", "#000000")),
                                  diffuse=float(s.get("diffuse", 15)),
                                  distance=float(s.get("distance", 5)),
                                  angle=float(s.get("angle", -45)))
        if it.get("bg"):
            g = it["bg"]
            bg = d.TextBackground(color=g.get("color", "#000000"),
                                  style=int(g.get("style", 1)),
                                  alpha=float(g.get("alpha", 0.6)),
                                  round_radius=float(g.get("round_radius", 0.0)))
        seg = d.TextSegment(it["text"], rng, style=style, border=border,
                            shadow=shadow, background=bg,
                            clip_settings=_clip(d, it))
        # pyJianYingDraft 的 Segment 基类给每个片段都塞了 speed 素材引用，
        # 但 ScriptFile.add_segment 只把 video/audio 的 speed 登记进 materials.speeds，
        # 文字段就留下 1 条悬空 ref。这里直接摘掉，避免 finalize 事后去剥。
        speed_id = getattr(getattr(seg, "speed", None), "global_id", None)
        if speed_id:
            seg.extra_material_refs = [r for r in seg.extra_material_refs if r != speed_id]
        return seg

    if ttype == "audio":
        return d.AudioSegment(it["path"], rng,
                              speed=it.get("speed"),
                              volume=float(it.get("volume", 1.0)))

    if ttype == "sticker":
        return d.StickerSegment(it["resource_id"], rng, clip_settings=_clip(d, it))

    if ttype == "filter":
        return d.FilterSegment(_enum(d.FilterType, it["name"], "滤镜"), rng,
                               intensity=float(it.get("intensity", 100)))

    if ttype == "effect":
        return d.EffectSegment(_enum(d.VideoSceneEffectType, it["name"], "特效"), rng,
                               params=it.get("params"))

    # video (packed image works the same way)
    src = None
    if it.get("source_start") is not None or it.get("speed"):
        dur = it["duration"] * float(it.get("speed") or 1.0)
        src = d.Timerange(us(it.get("source_start", 0)), us(dur))
    return d.VideoSegment(it["path"], rng, source_timerange=src,
                          speed=it.get("speed"), volume=float(it.get("volume", 1.0)),
                          clip_settings=_clip(d, it))


def _decorate(seg, it):
    """Optional decorations; silently skipped when the segment type lacks them."""
    if it.get("transition") and hasattr(seg, "add_transition"):
        t = it["transition"]
        seg.add_transition(_enum(_tj().TransitionType, t["name"], "转场"),
                           duration=us(t["duration"]) if t.get("duration") else None)
    if it.get("fade"):
        f = it["fade"]
        if hasattr(seg, "add_fade"):
            seg.add_fade(int(float(f.get("in", 0)) * US), int(float(f.get("out", 0)) * US))
    if it.get("anim_in") or it.get("anim_out") or it.get("loop_anim"):
        _add_animation(seg, it)
    if it.get("mask") and hasattr(seg, "add_mask"):
        m = it["mask"]
        seg.add_mask(_enum(_tj().MaskType, m.get("type", "线性"), "蒙版"),
                     center_x=float(m.get("center_x", 0)), center_y=float(m.get("center_y", 0)),
                     size=float(m.get("size", 0.5)), rotation=float(m.get("rotation", 0)),
                     feather=float(m.get("feather", 0)), invert=bool(m.get("invert", False)))
    if it.get("filter") and hasattr(seg, "add_filter"):
        seg.add_filter(_enum(_tj().FilterType, it["filter"]["name"], "滤镜"),
                       intensity=float(it["filter"].get("intensity", 100)))
    if it.get("mix_mode") and hasattr(seg, "set_mix_mode"):
        seg.set_mix_mode(_enum(_tj().MixModeType, it["mix_mode"], "混合模式"))
    if it.get("background_fill") and hasattr(seg, "add_background_filling"):
        b = it["background_fill"]
        seg.add_background_filling(b.get("type", "blur"), blur=float(b.get("blur", 0.0625)),
                                   color=b.get("color", "#00000000"))
    if it.get("text_effect") and hasattr(seg, "add_effect"):
        # 花字：effect_id 与 resource_id 同值，名字查 jy_text_effects.json
        seg.add_effect(text_effect_id(it["text_effect"]))


def _add_animation(seg, it):
    """Video/Text segments expose different animation enums — pick by type."""
    import pyJianYingDraft as d
    is_text = type(seg).__name__.startswith("Text")
    pairs = []
    if it.get("anim_in"):
        cls = d.TextIntro if is_text else d.IntroType
        pairs.append((_enum(cls, it["anim_in"]["name"], "入场动画"),
                      it["anim_in"].get("duration")))
    if it.get("anim_out"):
        cls = d.TextOutro if is_text else d.OutroType
        pairs.append((_enum(cls, it["anim_out"]["name"], "出场动画"),
                      it["anim_out"].get("duration")))
    if it.get("loop_anim") and is_text:
        pairs.append((_enum(d.TextLoopAnim, it["loop_anim"]["name"], "循环动画"), None))
    for meta, dur in pairs:
        micro = us(dur) if dur else None
        try:
            seg.add_animation(meta, duration=micro)
        except TypeError:
            seg.add_animation(meta)


def _clip(d, it):
    pos = it.get("position") or [0, 0]
    return d.ClipSettings(
        alpha=float(it.get("alpha", 1.0)),
        rotation=float(it.get("rotation", 0.0)),
        scale_x=float(it.get("scale", 1.0)),
        scale_y=float(it.get("scale", 1.0)),
        transform_x=float(pos[0]),
        transform_y=float(pos[1]),
    )


def _tj():
    import pyJianYingDraft as d
    return d


# ------------------------------------------------------------------ finalize

def finalize(draft_dir: pathlib.Path, plain: bool = False) -> pathlib.Path:
    """Normalize dangling refs; then encrypt + write timelines + register.

    plain=True（或找不到 jyai）时只写明文 `draft_content.json` + `draft_meta_info.json`，
    剪映 11.x 能直接打开；差别是没有加密、可能不出现在首页（用「导入草稿」/最近项目打开）。
    """
    content = draft_dir / "draft_content.json"

    nc = None
    if not plain:
        try:
            from jyai import native_crypto as nc_mod
            nc = nc_mod
        except Exception:
            print("· jyai 不可用 → 走明文模式")
            plain = True

    if content.read_bytes()[:1] == b"{":
        doc = json.loads(content.read_text(encoding="utf-8"))
    elif nc is not None:
        doc = json.loads(nc.read_bytes(content).decode("utf-8", "ignore"))
    else:
        raise SystemExit(f"✗ {content} 是加密的，但没有 jyai 解不开；请用 --plain 重新生成")

    ids = {m["id"] for k, v in doc["materials"].items() if isinstance(v, list)
           for m in v if isinstance(m, dict) and "id" in m}
    stripped = 0
    for tr in doc["tracks"]:
        for seg in tr["segments"]:
            for field in ("extra_material_refs", "keyframe_refs"):
                refs = seg.get(field)
                if isinstance(refs, list):
                    kept = [x for x in refs if x in ids]
                    stripped += len(refs) - len(kept)
                    seg[field] = kept
    if stripped:
        print(f"清理悬空引用：{stripped} 条")
    content.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")

    if plain:
        # 明文模式：补素材保存方式 + 时间线副本，剪映就能读
        doc.setdefault("config", {})["material_save_mode"] = 1
        content.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        tl = draft_dir / "Timelines" / str(doc.get("id") or "timeline")
        tl.mkdir(parents=True, exist_ok=True)
        (tl / "draft_content.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        meta = draft_dir / "draft_meta_info.json"
        if meta.is_file():
            try:
                m = json.loads(meta.read_text(encoding="utf-8-sig"))
                m["draft_fold_path"] = str(draft_dir)
                m["draft_root_path"] = str(draft_dir.parent)
                meta.write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
            except ValueError:
                pass
        print("明文草稿：完成（剪映里用「导入草稿」或最近项目打开）")
        print(f"草稿目录：{draft_dir}")
        return draft_dir

    import native_compat
    result = native_compat.finalize(str(draft_dir), register=True)
    ok = result.get("static_valid")
    print(f"加密+登记：{'成功' if ok else '有问题'}  issues={result.get('issues')}")
    if not ok:
        print("  提示：加 --plain 可跳过加密，直接出明文草稿")
    print(f"草稿目录：{draft_dir}")
    return draft_dir


# ------------------------------------------------------------------ cli

def list_enums(which: str):
    import pyJianYingDraft as d
    table = {
        "transition": d.TransitionType, "intro": d.IntroType, "outro": d.OutroType,
        "group": d.GroupAnimationType, "text_intro": d.TextIntro,
        "text_outro": d.TextOutro, "loop": d.TextLoopAnim, "filter": d.FilterType,
        "mask": d.MaskType, "mix": d.MixModeType, "effect": d.VideoSceneEffectType,
    }
    if which not in table:
        print("可选：" + ", ".join(table))
        return 0
    names = [x for x in vars(table[which]) if not x.startswith("_")]
    print(f"{which}（{len(names)} 个）：")
    for i in range(0, len(names), 8):
        print("  " + "  ".join(names[i:i + 8]))
    return 0


def main(argv):
    if "--list-enums" in argv:
        i = argv.index("--list-enums")
        return list_enums(argv[i + 1] if len(argv) > i + 1 else "")
    if len(argv) < 2:
        print(__doc__)
        return 2

    spec_path = pathlib.Path(argv[1])
    spec = json.loads(spec_path.read_text(encoding="utf-8-sig"))
    if "--dry-run" in argv:
        spec["dry_run"] = True
    if "--plain" in argv:                      # 不加密，只写明文草稿
        spec["plain"] = True

    info = load_env()
    spec.setdefault("drafts_root", info["drafts_root"])

    if "--validate" in argv:
        errs = validate_spec(spec)
        if errs:
            print("spec 校验失败：")
            for e in errs:
                print("  - " + e)
            return 1
        n_tracks = len(spec.get("tracks") or [])
        n_items = sum(len(t.get("items") or []) for t in spec.get("tracks") or [])
        print(f"spec 校验通过：{n_tracks} 条轨 / {n_items} 个片段")
        return 0

    ver = info.get("app_version") or "未知"
    bridge = "jyai（加密+登记）" if info.get("have_bridge") else "无（明文草稿）"
    print(f"环境：剪映 {ver} / 草稿根 {spec['drafts_root']} / 桥接 {bridge}")

    t0 = time.time()
    out = build(spec)
    print(f"完成，用时 {time.time() - t0:.1f}s → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
