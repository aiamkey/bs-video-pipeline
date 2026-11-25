# -*- coding: utf-8 -*-
"""草稿素材本地化：把素材复制进草稿目录，路径改成剪映的占位符相对形式。

剪映自己保存草稿时不写绝对路径，而是：

    ##_draftpath_placeholder_<固定UUID>_##/assets/<文件名>

固定 UUID 是编译进剪映的常量（已用剪映 11.6.0.14552 实测：占位符相对路径能正常显示）。
好处：整个草稿文件夹可以拷到别的机器/发给别人，素材不丢；绝对路径做不到。

同时把 config.material_save_mode 置 1（= 素材已在草稿目录内），
并把 draft_meta_info.json 里 draft_materials 的 file_Path 写成 ./assets/xxx。
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import shutil

# 剪映编译期固定常量；从版本能力表取，取不到才用这个（见 pipeline/jy_versions.json）
PLACEHOLDER_DEFAULT = "0E685133-18CE-45ED-8CB8-2904A212EC80"
PLACEHOLDER = os.environ.get("JY_PLACEHOLDER") or PLACEHOLDER_DEFAULT
PREFIX = f"##_draftpath_placeholder_{PLACEHOLDER}_##"
MEDIA_DIR = "assets"
LISTS = (("videos", "video"), ("audios", "audio"), ("images", "image"))


def _read(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write(path: pathlib.Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def localize(draft_dir: pathlib.Path, media_dir: str = MEDIA_DIR) -> dict:
    """就地本地化。返回 {copied, skipped, missing, total}。"""
    draft_dir = pathlib.Path(draft_dir)
    plan_path = draft_dir / "draft_content.json"
    if not plan_path.exists():
        raise SystemExit(f"找不到 {plan_path}")

    plan = _read(plan_path)
    materials = plan.get("materials") or {}
    target = draft_dir / media_dir
    copied = skipped = missing = total = 0
    renamed: dict[str, str] = {}

    for key, sub in LISTS:
        for mat in materials.get(key) or []:
            raw = mat.get("path")
            if not raw or not isinstance(raw, str):
                continue
            total += 1
            if raw.startswith("##_draftpath_placeholder_"):
                skipped += 1
                continue
            src = pathlib.Path(raw)
            if not src.is_file():
                missing += 1
                print(f"  ! 素材不在本地，未本地化：{raw}")
                continue

            name = renamed.get(str(src))
            if name is None:
                digest = hashlib.md5(str(src).encode("utf-8")).hexdigest()[:8]
                name = f"{sub}-{digest}{src.suffix.lower() or '.bin'}"
                renamed[str(src)] = name
                target.mkdir(parents=True, exist_ok=True)
                dst = target / name
                if not dst.exists():
                    shutil.copy2(src, dst)
                    copied += 1
                else:
                    skipped += 1
            mat["path"] = f"{PREFIX}/{media_dir}/{name}"

    config = plan.setdefault("config", {})
    config["material_save_mode"] = 1
    _write(plan_path, plan)

    # 时间线副本（11.6 有 Timelines/<id>/draft_content.json，需与根内容一致）
    timelines = draft_dir / "Timelines"
    if timelines.is_dir():
        for child in timelines.iterdir():
            copy = child / "draft_content.json"
            if copy.is_file():
                _write(copy, plan)

    # 素材登记表：file_Path 只保留 ./assets/xxx
    meta_path = draft_dir / "draft_meta_info.json"
    if meta_path.is_file():
        meta = _read(meta_path)
        for group in meta.get("draft_materials") or []:
            for entry in (group or {}).get("value") or []:
                if not isinstance(entry, dict):
                    continue
                path = entry.get("file_Path")
                if isinstance(path, str) and path.startswith(PREFIX):
                    entry["file_Path"] = "./" + path[len(PREFIX):].lstrip("/")
        _write(meta_path, meta)

    return {"copied": copied, "skipped": skipped, "missing": missing, "total": total}
