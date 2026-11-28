# -*- coding: utf-8 -*-
"""把 spec 的每屏抽一张代表帧，填进 scenes[].assets[]，供 jy_from_spec 出图片轨。

这是「低成本复刻」的视觉层：画面 = 原片对应屏的代表帧，**不联网、不花钱**，
结构上与原片逐屏对齐。要出「重画版」时，只把 assets[].file 换成 GPT 生成
的图即可，下游（剪映草稿 / Remotion）完全不用改。

用法：
  python tools\\replica_shots.py --spec qa2\\replica\\out\\q6-extract.spec.json
  python tools\\replica_shots.py --spec X.spec.json --at 0.6 --outdir D:\\tmp\\assets
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
sys.path.insert(0, str(_HERE.parent))
import analyze_ref as ar  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="每屏抽代表帧，填 scenes[].assets[]")
    ap.add_argument("--spec", required=True)
    ap.add_argument("--src", default="", help="源片路径；默认取 spec.meta.source")
    ap.add_argument("--outdir", default="", help="资产目录；默认 spec 同级 assets/")
    ap.add_argument("--at", type=float, default=0.4, help="屏内偏移多少秒取帧（避开转场）")
    a = ap.parse_args()

    sp = Path(a.spec).resolve()
    spec = json.loads(sp.read_text(encoding="utf-8"))
    meta = spec.get("meta") or {}
    src = Path(a.src or meta.get("source") or "").resolve()
    if not src.is_file():
        sys.exit(f"[shots] 找不到源片：{src}")

    # 每片一个资产目录：多片共用 assets/ 会按 pNNN 互相覆盖（踩过，q6 的
    # p000-p037 被后面的片盖掉，导致重导旧草稿时拿到错的图）
    stem = sp.name[: -len(".spec.json")] if sp.name.endswith(".spec.json") else sp.stem
    adir = Path(a.outdir).resolve() if a.outdir else (sp.parent / "assets" / stem)
    adir.mkdir(parents=True, exist_ok=True)

    n_ok = 0
    scenes = spec.get("scenes") or []
    for k, sc in enumerate(scenes):
        s = float(sc.get("s", 0.0))
        e = float(sc.get("e", s))
        idx = int(sc.get("idx", k))
        t = min(s + a.at, max(s, e - 0.12))
        out = adir / f"p{idx:03d}.jpg"
        if ar.grab_frame(src, t, out):
            try:
                rel = out.relative_to(sp.parent).as_posix()
            except ValueError:
                rel = str(out)
            sc["assets"] = [{"slot": "bg", "file": rel, "status": "ready", "t": round(t, 2)}]
            n_ok += 1
        else:
            print(f"[shots] p{idx:03d} 抽帧失败 t={t:.2f}")

    sp.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[shots] {n_ok}/{len(scenes)} 屏抽帧 → {adir}")
    print(f"[shots] spec 已更新 assets[]：{sp}")
    return 0 if n_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
