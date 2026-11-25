"""素材登记与查重：防止"一张图贴半集"。

用法：
  python tools/assets.py list                      # 现有素材
  python tools/assets.py check                     # 读 film.json，统计每张图用了几次
  python tools/assets.py check --film src/data/film.json --max 2
  python tools/assets.py add sofa-03 "客厅沙发" "挠头,焦虑" textures/slides/u16b.jpg

check 规则（来自 CARTOON.md §0.5 复用矩阵）：
  - 一张图一集内 ≤ max（默认 2）次
  - 同一张图两次出现间隔 ≥ 40s
  - 跨章复用禁止（chapter 变而图没变 → 报）
"""
import argparse
import json
import os
import sys

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROMO = os.environ.get("PROMO") or (
    os.path.join(_BASE, "lbr-promo") if os.path.isdir(os.path.join(_BASE, "lbr-promo")) else _BASE
)
REG = os.path.join(PROMO, "pipeline", "assets.json")
FILM = os.path.join(PROMO, "src", "data", "film.json")


def load():
    with open(REG, encoding="utf-8") as f:
        return json.load(f)


def save(d):
    with open(REG, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)


def cmd_list(a):
    d = load()
    for it in d["assets"]:
        print("%-12s %-10s %-28s %s" % (it["id"], it["scene"], "/".join(it["tags"])[:28], it["file"]))
    print("\n共 %d 张" % len(d["assets"]))
    return 0


def cmd_add(a):
    d = load()
    if any(x["id"] == a.id for x in d["assets"]):
        print("id 已存在：%s" % a.id)
        return 1
    d["assets"].append(
        {
            "id": a.id,
            "scene": a.scene,
            "tags": [t.strip() for t in a.tags.split(",") if t.strip()],
            "file": a.file,
            "source": a.source,
            "used_in": [],
        }
    )
    save(d)
    print("已登记 %s" % a.id)
    return 0


def cmd_check(a):
    film_path = a.film if os.path.isabs(a.film) else os.path.join(PROMO, a.film)
    with open(film_path, encoding="utf-8") as f:
        film = json.load(f)

    # film.json: {sections:[{name,start,end}], lines:[{start,text,card}]}
    def chapter_of(t):
        for s in film.get("sections", []):
            if s["start"] <= t < s["end"]:
                return s.get("name") or s.get("label") or "?"
        return "?"

    uses = {}  # file -> [(t, chapter, text)]
    for ln in film.get("lines", []):
        c = ln.get("card") or {}
        frames = []
        if c.get("type") == "slides":
            frames = c.get("frames") or []
        elif c.get("type") == "image" and c.get("src"):
            frames = [c["src"]]
        for fr in frames:
            uses.setdefault(os.path.basename(fr), []).append((ln.get("start", 0), chapter_of(ln.get("start", 0)), ln.get("text", "")[:18]))

    if not uses:
        print("film.json 里没有卡通/图片卡")
        return 0

    bad = 0
    print("%-22s %3s  %s" % ("素材", "次", "位置"))
    for name in sorted(uses, key=lambda k: -len(uses[k])):
        rec = uses[name]
        flag = ""
        if len(rec) > a.max:
            flag = "  ✗ 超次数(%d>%d)" % (len(rec), a.max)
            bad += 1
        gaps = [rec[i + 1][0] - rec[i][0] for i in range(len(rec) - 1)]
        if gaps and min(gaps) < a.gap:
            flag += "  ✗ 间隔过近(%.0fs)" % min(gaps)
            bad += 1
        chapters = {r[1] for r in rec}
        if len(chapters) > 1:
            flag += "  ✗ 跨章(%s)" % ",".join(sorted(chapters))
            bad += 1
        print("%-22s %3d  %s%s" % (name[:22], len(rec), ", ".join("%.0fs" % r[0] for r in rec)[:60], flag))

    unreg = [n for n in uses if not any(os.path.basename(x["file"]) == n for x in load()["assets"])]
    if unreg:
        print("\n未登记的素材：%s" % ", ".join(unreg))
    print("\n%s" % ("发现问题 %d 处" % bad if bad else "复用检查通过"))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("list")
    s.set_defaults(func=cmd_list)

    c = sub.add_parser("check")
    c.add_argument("--film", default="src/data/film.json")
    c.add_argument("--max", type=int, default=2)
    c.add_argument("--gap", type=float, default=40.0)
    c.set_defaults(func=cmd_check)

    d = sub.add_parser("add")
    d.add_argument("id")
    d.add_argument("scene")
    d.add_argument("tags")
    d.add_argument("file")
    d.add_argument("--source", default="ai:wanx seed20261124")
    d.set_defaults(func=cmd_add)

    a = ap.parse_args()
    sys.exit(a.func(a))


if __name__ == "__main__":
    main()
