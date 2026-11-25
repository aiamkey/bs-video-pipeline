# -*- coding: utf-8 -*-
"""人像美化（figure）注入器 —— 给明文 draft_content.json 写美颜/美型/美妆/美体素材。

来源：capcut-mate（Hommy-master, Apache-2.0）的 src/pyJianYingDraft/metadata/beauty_meta.py
+ src/service/add_beauty.py。已核对其 FigureEffect.export_json 的字段顺序与语义，这里只做
JSON 层注入，不依赖它 fork 的 pyJianYingDraft。

关键事实（照抄，勿凭感觉改）：
  1. 素材写进 materials.effects，type 为 figure（makeup_root 为 makeup_root），
     并把 id 追加到目标片段的 extra_material_refs。
  2. 强度：剪映滑杆 0~100 → 草稿 0~1；肤色 temperature 0~99 → 0~1（÷99）。
  3. 落点三种：value（顶层 value）/ adjust_param（adjust_params）/ face_adjust（face_adjust_params）。
  4. 只要有一条滑杆生效，同一片段必须补一条 makeup-root（强度固定 0）。
  5. 滑杆为 0 = 不写素材（与剪映"关闭"等价）。
  6. 需要算法产物的素材用 algorithm_artifact_path：
     ##_draftpath_placeholder_{占位ID}##/video/figure_algorithm/{视频素材id}
     同一草稿内占位 ID 必须一致，剪映加载时替换成真实草稿路径。

用法：
  python tools/jy_beauty.py DRAFT_DIR --skin smooth=40,even=30 --shape slim=20 \
      --body slim_body=15 --look 中国妆:80 --tint 暖白:60:20
  python tools/jy_beauty.py --list
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import uuid

HERE = pathlib.Path(__file__).resolve().parent
CATALOG_PATH = HERE.parent / "lbr-promo" / "pipeline" / "jy_beauty_catalog.json"

GROUPS = ("skin", "shape", "makeup", "body")


def load_catalog() -> dict:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def _figure(meta: dict, intensity: float, cold_warm: float, algorithm_path: str) -> dict:
    """按 FigureEffect.export_json 的形状构造一条美颜素材。intensity 0~100，cold_warm 0~99。"""
    value = 0.0
    adjust_params: list = []
    face_adjust_params: list = []

    if meta["intensity_mode"] == "adjust_param":
        adjust_params = [{"default_value": 0.0, "name": meta["adjust_param_name"], "value": intensity / 100.0}]
    elif meta["intensity_mode"] == "face_adjust":
        face_params = []
        if meta["cold_warm_key"]:
            face_params.append({
                "default_value": 0.0,
                "name": meta["cold_warm_key"],
                "value": round(cold_warm / (meta["cold_warm_divisor"] or 100.0), 8),
            })
        if meta["face_adjust_param_name"]:
            face_params.append({
                "default_value": 0.0,
                "name": meta["face_adjust_param_name"],
                "value": intensity / 100.0,
            })
        face_adjust_params = [{
            "adjust_params": face_params,
            "disable_part": [],
            "enable": True,
            "face_id": meta["face_id"],
        }]
    else:  # value
        value = intensity / 100.0

    return {
        "adjust_params": adjust_params,
        "algorithm_artifact_path": algorithm_path if meta["needs_algorithm_path"] else "",
        "apply_target_type": 0,
        "bloom_params": None,
        "category_id": meta["category_id"],
        "category_name": "",
        "color_match_info": {
            "source_feature_path": "",
            "target_feature_path": "",
            "target_image_path": "",
        },
        "effect_id": "",
        "enable_skin_tone_correction": False,
        "exclusion_group": list(meta["exclusion_group"]),
        "face_adjust_params": face_adjust_params,
        "formula_id": "",
        "id": uuid.uuid4().hex,
        "intensity_key": meta["intensity_key"],
        "multi_language_current": "",
        "name": meta["draft_name"],
        "panel_id": "",
        "platform": "all",
        "request_id": "",
        "resource_id": meta["resource_id"],
        "source_platform": 0,
        "sub_type": meta["sub_type"],
        "time_range": None,
        "type": meta["material_type"],
        "value": value,
        "version": "",
    }


def ops_from_spec(cat: dict, cfg: dict) -> tuple[list[dict], str]:
    """spec.beauty 字典 → (ops, target)。滑杆写 {name: 强度0-100}。"""
    ops = []
    for group in ("skin", "shape", "body"):
        for name, val in (cfg.get(group) or {}).items():
            meta = cat[group].get(name)
            if meta is None:
                raise KeyError(f"{group} 组没有滑杆 {name!r}（可用：{', '.join(k for k, v in cat[group].items() if v['supported'])}）")
            if not meta["supported"]:
                raise KeyError(f"{group}.{name} 暂不支持（剪映草稿无对应素材）")
            if not float(val):
                continue
            ops.append({"meta": meta, "intensity": float(val), "cold_warm": 0.0})

    tint = cfg.get("tint")
    if tint:
        preset = tint if isinstance(tint, str) else tint.get("preset", "")
        meta = cat["skin_tone"].get(preset)
        if meta is None:
            raise KeyError(f"肤色预设只有 冷白 / 暖白，收到 {preset!r}")
        intensity = 60.0 if isinstance(tint, str) else float(tint.get("intensity", 60))
        cold = 0.0 if isinstance(tint, str) else float(tint.get("cold", 0))
        ops.append({"meta": meta, "intensity": intensity, "cold_warm": cold})

    look = cfg.get("look")
    if look:
        preset = look if isinstance(look, str) else look.get("preset", "")
        meta = cat["makeup"].get(preset)
        if meta is None:
            raise KeyError(f"没有妆容 {preset!r}（共 {len(cat['makeup'])} 个）")
        intensity = 80.0 if isinstance(look, str) else float(look.get("intensity", 80))
        face_id = meta["face_id"] if isinstance(look, str) else str(look.get("face_id", meta["face_id"]))
        ops.append({"meta": {**meta, "face_id": face_id}, "intensity": intensity, "cold_warm": 0.0})

    return ops, (cfg.get("target") or "video")


def _parse_kv(text: str) -> list[tuple[str, float]]:
    out = []
    for part in (text or "").split(","):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            raise SystemExit(f"参数要写成 name=value：{part!r}")
        name, val = part.split("=", 1)
        out.append((name.strip(), float(val)))
    return out


def collect_ops(cat: dict, args) -> list[dict]:
    """把命令行参数解析成待写入的素材列表（含肤色/美妆预设），滑杆 0 跳过。"""
    ops = []
    for group in ("skin", "shape", "body"):
        for name, val in _parse_kv(getattr(args, group, "")):
            meta = cat[group].get(name)
            if meta is None:
                raise SystemExit(f"{group} 组没有这个滑杆：{name}（可用：{', '.join(k for k, v in cat[group].items() if v['supported'])}）")
            if not meta["supported"]:
                raise SystemExit(f"{group}.{name} 暂不支持（剪映草稿里没有对应素材）")
            if not val:
                continue
            ops.append({"meta": meta, "intensity": val, "cold_warm": 0.0})

    if args.tint:
        bits = args.tint.split(":")
        preset = bits[0].strip()
        meta = cat["skin_tone"].get(preset)
        if meta is None:
            raise SystemExit(f"肤色预设只有 冷白 / 暖白，收到：{preset}")
        intensity = float(bits[1]) if len(bits) > 1 else 60.0
        cold = float(bits[2]) if len(bits) > 2 else 0.0
        ops.append({"meta": meta, "intensity": intensity, "cold_warm": cold})

    if args.look:
        bits = args.look.split(":")
        preset = bits[0].strip()
        meta = cat["makeup"].get(preset)
        if meta is None:
            raise SystemExit(f"没有这个妆容：{preset}（共 {len(cat['makeup'])} 个，用 --list 看）")
        intensity = float(bits[1]) if len(bits) > 1 else 80.0
        face_id = bits[2] if len(bits) > 2 else meta["face_id"]
        ops.append({"meta": {**meta, "face_id": face_id}, "intensity": intensity, "cold_warm": 0.0})

    return ops


def apply_beauty(draft_dir: pathlib.Path, ops: list[dict], target: str = "video") -> dict:
    """把 ops 写进明文 draft_content.json。target: video=所有视频轨片段 / first=每轨首段。"""
    path = draft_dir / "draft_content.json"
    if not path.exists():
        raise SystemExit(f"找不到 {path}")
    raw = path.read_text(encoding="utf-8-sig")
    plan = json.loads(raw)
    if not ops:
        return {"applied": 0, "segments": 0}

    materials = plan.setdefault("materials", {})
    effects = materials.setdefault("effects", [])
    videos = {m["id"]: m for m in materials.get("videos", []) if m.get("id")}
    placeholder = uuid.uuid4().hex.upper()

    done_segments = 0
    done_figures = 0
    for track in plan.get("tracks", []):
        if track.get("type") != "video":
            continue
        segs = track.get("segments") or []
        if target == "first":
            segs = segs[:1]
        for seg in segs:
            vid = seg.get("material_id")
            if not vid:
                continue
            algorithm = f"##_draftpath_placeholder_{placeholder}##/video/figure_algorithm/{vid}"
            refs = seg.setdefault("extra_material_refs", [])
            for op in ops:
                fig = _figure(op["meta"], op["intensity"], op["cold_warm"], algorithm)
                effects.append(fig)
                refs.append(fig["id"])
                done_figures += 1
            root = _figure(cat_makeup_root(), 0.0, 0.0, algorithm)
            effects.append(root)
            refs.append(root["id"])
            done_figures += 1
            done_segments += 1

    path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    return {"applied": done_figures, "segments": done_segments, "placeholder": placeholder}


_ROOT_CACHE: dict = {}


def cat_makeup_root() -> dict:
    if not _ROOT_CACHE:
        _ROOT_CACHE.update(load_catalog()["makeup_root"])
    return _ROOT_CACHE


def main(argv=None):
    ap = argparse.ArgumentParser(description="给剪映草稿注入人像美化素材")
    ap.add_argument("draft_dir", nargs="?", help="草稿目录（含 draft_content.json 明文）")
    ap.add_argument("--skin", default="", help="磨皮/匀肤/美白/亮眼… 例 smooth=40,even=30")
    ap.add_argument("--shape", default="", help="瘦脸/小脸/V脸… 例 slim=20")
    ap.add_argument("--body", default="", help="瘦身/长腿/直角肩… 例 slim_body=15")
    ap.add_argument("--tint", default="", help="肤色预设 冷白|暖白[:强度[:冷暖0-99]]")
    ap.add_argument("--look", default="", help="美妆套装 名字[:强度[:face_id]]")
    ap.add_argument("--target", default="video", choices=["video", "first"], help="作用范围")
    ap.add_argument("--list", action="store_true", help="列出目录")
    args = ap.parse_args(argv)

    cat = load_catalog()
    if args.list:
        for group in GROUPS:
            names = [f"{k}({v['draft_name']})" for k, v in cat[group].items() if v["supported"]]
            print(f"[{group}] {len(names)}: " + "  ".join(names))
        print(f"[skin_tone] " + "  ".join(cat["skin_tone"]))
        return 0

    if not args.draft_dir:
        ap.error("需要 draft_dir（或用 --list）")
    ops = collect_ops(cat, args)
    if not ops:
        print("没有生效的滑杆（全 0 或未指定），未改动草稿")
        return 0
    info = apply_beauty(pathlib.Path(args.draft_dir), ops, target=args.target)
    print(f"美化写入：{info['applied']} 条素材（含 makeup-root）→ {info['segments']} 个视频片段")
    return 0


if __name__ == "__main__":
    sys.exit(main())
