# -*- coding: utf-8 -*-
"""素材体检：稿子/清单里引用的图片，仓库里到底有没有。

**为什么有这个文件**：仓库不含 AI 生成的成图（`public/textures/slides/*.jpg` 等，约 11 MB），
但 `scripts/script-*.json`、`pipeline/library.json`、`pipeline/assets.json` 里引用着它们。
不体检就会出现"渲染出来一片空白，不知道缺哪张"。

用法：
    python tools/check_assets.py                 # 列缺口 + 生成命令
    python tools/check_assets.py --json          # 机器可读
    python tools/check_assets.py --ep ep02       # 只看某一集引用的
    python tools/check_assets.py --soft          # 缺了也返回 0（给 selftest 用）

退出码：0 = 齐了 / 1 = 有缺口（--soft 时恒 0）
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
for _base in (_HERE.parents[1], _HERE.parents[1] / "lbr-promo", _HERE.parent, _HERE.parent / "lbr-promo"):
    if (_base / "pipeline" / "env.py").is_file():
        sys.path.insert(0, str(_base / "pipeline"))
        break
import env  # noqa: E402  统一环境发现（路径/ffmpeg/python 都从这来）


def _rel(p: str) -> str:
    p = p.replace("\\", "/").lstrip("/")
    return p[len("textures/"):] if p.startswith("textures/") else p


def collect() -> dict[str, list[str]]:
    """{素材文件名: [谁引用]}"""
    need: dict[str, list[str]] = {}

    def add(name: str, who: str):
        n = _rel(str(name))
        if not n or n.startswith(("http", "data:")):
            return
        need.setdefault(n, [])
        if who not in need[n]:
            need[n].append(who)

    # 1) 稿子：cards[].img / frames[] / panel.bg
    for script in sorted(env.scripts().glob("script-*.json")):
        try:
            doc = json.loads(script.read_text(encoding="utf-8-sig"))
        except ValueError:
            continue
        who = script.name
        if isinstance(doc, dict) and "chapters" in doc:
            for ch in doc.get("chapters") or []:
                for ln in ch.get("lines") or []:
                    card = ln.get("card") or {}
                    if isinstance(card.get("img"), str):
                        add(card["img"], who)
                    for f in card.get("frames") or []:
                        add(f, who)
                    panel = ln.get("panel")
                    if isinstance(panel, dict) and panel.get("bg"):
                        add(panel["bg"], who)
                    elif isinstance(panel, str) and ln.get("panel_bg"):
                        add(ln["panel_bg"], who)
        elif isinstance(doc, list):
            for ln in doc:
                card = ln.get("card") or {}
                if isinstance(card.get("img"), str):
                    add(card["img"], who)
                for f in card.get("frames") or []:
                    add(f, who)

    # 2) 素材清单
    for name in ("library.json", "assets.json"):
        f = env.root() / "pipeline" / name
        if not f.is_file():
            continue
        try:
            doc = json.loads(f.read_text(encoding="utf-8-sig"))
        except ValueError:
            continue
        rows = doc if isinstance(doc, list) else (doc.get("items") or doc.get("library") or [])
        for it in rows:
            if not isinstance(it, dict) or not isinstance(it.get("file"), str):
                continue
            # library.json 里 status=missing 的是"待生成清单"，不算缺口
            if it.get("status") == "missing":
                continue
            add(it.get("from") or it["file"], name)

    return need


def main() -> int:
    ap = argparse.ArgumentParser(description="素材体检")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--ep", default="", help="只看某一集（匹配 script-<ep>.json）")
    ap.add_argument("--soft", action="store_true", help="缺了也返回 0")
    a = ap.parse_args()

    need = collect()
    pub = env.public("textures")
    missing, have = {}, 0
    for rel, who in sorted(need.items()):
        if a.ep and not any(a.ep in w for w in who):
            continue
        p = pub / rel
        if p.is_file():
            have += 1
        else:
            missing[rel] = who

    if a.json:
        print(json.dumps({"ok": not missing, "have": have, "missing": missing},
                         ensure_ascii=False, indent=1))
    else:
        total = have + len(missing)
        print(f"素材体检：{have}/{total} 就位 · 缺 {len(missing)}")
        if missing:
            by_dir: dict[str, list[str]] = {}
            for rel in missing:
                by_dir.setdefault(str(Path(rel).parent), []).append(Path(rel).name)
            for d, names in sorted(by_dir.items()):
                print(f"\n  ✗ {d}/  缺 {len(names)} 个")
                print("    " + " ".join(sorted(names)))
            print("\n怎么补（任选一种）：")
            print("  1) 生成：python tools/img.py \"<场景提示词>\" lbr-promo/public/textures/slides/u3b.jpg --seed 20261124")
            print("     —— 提示词模板见 pipeline/CARTOON.md，逐张按 library.json 的 scene/tags 写")
            print("  2) 已有图：直接拷进对应目录，文件名与稿子里写的一致即可")
            print("  3) 只出结构：先跑 pipeline/run.py build <ep>，缺图的地方会是底色块，不影响先看节奏")
            print("\n注意：这些成图不进 git（AI 生成、体积大），只进 library.json 的清单。")

    if not missing:
        return 0
    return 0 if a.soft else 1


if __name__ == "__main__":
    raise SystemExit(main())
