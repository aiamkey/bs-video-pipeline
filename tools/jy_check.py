"""Summarize a JianYing draft (encrypted or plain) — what actually landed.

  python tools/jy_check.py "E:\\...\\JianyingPro Drafts\\AItest_rich"
  python tools/jy_check.py <dir> --json

Portable: skill path discovered by tools/jy_env.py.
"""
from __future__ import annotations

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    d = pathlib.Path(argv[1])
    if not d.is_dir():
        print(f"不是目录：{d}")
        return 2

    import jy_draft
    jy_draft.load_env()
    from jyai import native_crypto as nc

    raw = nc.read_bytes(d / "draft_content.json")
    doc = json.loads(raw.decode("utf-8", "ignore"))

    if "--json" not in argv:
        print(f"草稿：{d.name}")
        print(f"  version={doc.get('version')}  new_version={doc.get('new_version')}  "
              f"fps={doc.get('fps')}  canvas={doc['canvas_config']['width']}x{doc['canvas_config']['height']}  "
              f"duration={doc.get('duration')/1_000_000:.2f}s")

    ttypes = {1: "video", 2: "audio", 3: "text", 4: "sticker", 5: "effect", 6: "filter"}
    out = []
    for ti, tr in enumerate(doc.get("tracks", [])):
        kind = ttypes.get(tr.get("type"), str(tr.get("type")))
        rows = []
        for seg in tr.get("segments", []):
            kfs = seg.get("common_keyframes") or []
            kf_desc = []
            for block in kfs:
                vals = block.get("keyframe_list") or []
                kf_desc.append(f"{block.get('property_type')}x{len(vals)}")
            rng = seg.get("target_timerange") or {}
            row = {
                "start_s": round((rng.get("start") or 0) / 1_000_000, 2),
                "dur_s": round((rng.get("duration") or 0) / 1_000_000, 2),
                "keyframes": kf_desc,
                "extra": [],
            }
            ids = set()
            for m in (doc.get("materials") or {}).get("texts", []):
                ids.add(m.get("id"))
            for ref in seg.get("extra_material_refs") or []:
                row["extra"].append(ref[:8])
            for m in (doc.get("materials") or {}).get("speeds", []):
                pass
            rows.append(row)
        out.append({"track": ti, "type": kind, "segments": rows})

    if "--json" in argv:
        print(json.dumps({"draft": d.name, "tracks": out}, ensure_ascii=False, indent=2))
        return 0

    for t in out:
        print(f"\n轨 {t['track']} [{t['type']}]  {len(t['segments'])} 段")
        for s in t["segments"]:
            kf = " ".join(s["keyframes"]) or "-"
            print(f"   {s['start_s']:6.2f}s +{s['dur_s']:5.2f}s  kf:{kf}  refs:{len(s['extra'])}")

    # 黑场（视频层覆盖）——"打开就是黑的"比任何关键帧问题都致命
    total = (doc.get("duration") or 0) / 1_000_000
    segs = sorted((s["start_s"], s["start_s"] + s["dur_s"])
                  for t in out if t["type"] == "video" for s in t["segments"])
    gaps, t0 = [], 0.0
    for a, b in segs:
        if a - t0 > 0.06:
            gaps.append((round(t0, 2), round(a, 2), round(a - t0, 2)))
        t0 = max(t0, b)
    if total - t0 > 0.06:
        gaps.append((round(t0, 2), round(total, 2), round(total - t0, 2)))
    gt = sum(g[2] for g in gaps)
    print(f"\n画面覆盖：视频段 {len(segs)} 个 / 全片 {total:.2f}s")
    if gaps:
        print(f"  ⚠ 黑场 {len(gaps)} 处 合计 {gt:.2f}s（{100*gt/max(total,0.01):.1f}%）")
        for g in gaps[:10]:
            print(f"     {g[0]:6.2f}s → {g[1]:6.2f}s  ({g[2]:.2f}s)")
    else:
        print("  ✓ 无黑场（视频层首尾相接）")

    mats = doc.get("materials") or {}
    print("\n素材统计：")
    for k, v in mats.items():
        if isinstance(v, list) and v:
            print(f"   {k:22s} {len(v)}")
    # 关键帧/动画/转场的材料级证据
    for key in ("transitions", "material_animations", "video_effects", "filters",
                "masks", "speeds", "audio_fades"):
        v = mats.get(key)
        if isinstance(v, list) and v:
            print(f"   -> {key}: {len(v)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
