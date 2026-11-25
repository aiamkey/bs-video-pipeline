"""素材库批量生成器。

用法：
  python tools/build_lib.py --dry-run             # 列缺口（不花钱）
  python tools/build_lib.py --only sofa           # 只补一个场景
  python tools/build_lib.py                       # 补全部 missing
  python tools/build_lib.py --only cafe --force   # 覆盖重生成

读 lbr-promo/pipeline/library.json，跳过 status=have（除非 --force），
调用 tools/img.py 生成到 outdir，然后回写 status/file 并登记 assets.json。
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROMO = ROOT / "lbr-promo"
LIB_JSON = PROMO / "pipeline" / "library.json"
ASSETS_JSON = PROMO / "pipeline" / "assets.json"
IMG = ROOT / "tools" / "img.py"
PY = sys.executable


def load(p, default):
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8-sig"))


def save(p, data):
    p.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def prompt_for(lib, item):
    return lib["skeleton"].format(
        character=lib["character"], shot=item["shot"], action=item["action"]
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", help="只处理某个场景 id，如 sofa")
    ap.add_argument("--force", action="store_true", help="覆盖已存在的图")
    ap.add_argument("--seed", type=int, help="覆盖 library.json 里的 seed")
    args = ap.parse_args()

    lib = load(LIB_JSON, None)
    if not lib:
        sys.exit(f"缺少 {LIB_JSON}")

    outdir = ROOT / lib["outdir"]
    outdir.mkdir(parents=True, exist_ok=True)
    seed = args.seed if args.seed is not None else lib.get("seed")

    todo = []
    for it in lib["items"]:
        if args.only and not it["id"].startswith(args.only):
            continue
        if it.get("status") == "have" and not args.force:
            continue
        todo.append(it)

    have = sum(1 for i in lib["items"] if i.get("status") == "have")
    print(f"素材库：{len(lib['items'])} 条，已有 {have}，缺口 {len(lib['items']) - have}")
    print(f"本次处理 {len(todo)} 条，seed={seed}")

    if args.dry_run:
        for it in todo:
            print(f"  [缺] {it['id']:<16} {it['scene']}/{it['state']}  {it['action']}")
        return

    env = dict(os.environ)
    env.setdefault("NO_PROXY", "dashscope.aliyuncs.com")
    ok = 0
    for n, it in enumerate(todo, 1):
        out = outdir / it["file"]
        print(f"[{n}/{len(todo)}] {it['id']} …", end=" ", flush=True)
        cmd = [PY, str(IMG), prompt_for(lib, it), str(out)]
        if seed is not None:
            cmd += ["--seed", str(seed)]
        r = subprocess.run(cmd, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode == 0 and out.exists():
            it["status"] = "have"
            it["file"] = it["file"]
            it.pop("from", None)
            save(LIB_JSON, lib)
            print("ok")
            ok += 1
        else:
            print("FAIL")
            print((r.stderr or r.stdout or "")[-400:])

    # 同步登记到 assets.json
    assets = load(ASSETS_JSON, {"items": []})
    known = {a.get("file") for a in assets.get("items", [])}
    added = 0
    for it in lib["items"]:
        rel = f"lib/{it['file']}"
        if it.get("status") != "have" or rel in known:
            continue
        assets.setdefault("items", []).append(
            {
                "id": it["id"],
                "scene": it["scene"],
                "state": it["state"],
                "tags": [it["scene"], it["state"]],
                "file": rel,
                "source": "ai:wanx2.1-t2i-turbo",
                "used_in": [],
            }
        )
        added += 1
    if added:
        save(ASSETS_JSON, assets)

    have2 = sum(1 for i in lib["items"] if i.get("status") == "have")
    print(f"\n完成：本次成功 {ok}，库内已有 {have2}/{len(lib['items'])}，新登记 assets {added}")


if __name__ == "__main__":
    main()
