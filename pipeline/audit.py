"""film.json 层体检——渲染之前先跑这个，别等出片才发现"元素排成一列"。

`check.py` 量的是成片（时长/响度/静止），量不到"排布像不像 PPT"；
这个脚本量的是**构图与节奏**，全部从 `src/data/film.json` 读，不需要渲染。

用法：
  python lbr-promo\\pipeline\\audit.py                  # 默认读 src/data/film.json
  python lbr-promo\\pipeline\\audit.py --json           # 机器可读

判定分三档：FAIL（必须改，否则别渲染）/ WARN（能发，但离凯哥还差）/ OK。
退出码：有 FAIL 返回 1。
"""
import argparse
import io
import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILM = ROOT / "src" / "data" / "film.json"

# 阈值（和 SKILL.md §5.6 / §7.7 保持一致）
ZONE = [(20, 35), (45, 55), (65, 80)]     # 左 / 中 / 右 三个可放区
MIN_X_SPAN_FOR_3 = 25                      # 同屏 ≥3 元素时，x 至少跨 25 个百分点
LABEL_PER_PANEL_MAX = 1
LABEL_RATIO_MAX = 0.30
PANEL_SHOT_MIN = 4.0                       # 一屏至少停这么久才值得拆
CARD_SHOT_MEDIAN_MIN = 2.3                 # 卡片句单镜中位数下限（凯哥 2.75）
Y_LIMIT = 74                               # 超过会撞字幕
EMOJI_RATIO_MAX = 0.25                     # icon 占比（icon 在剪映里会变 emoji）

EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F0FF]"
)

rows = []


def add(item, value, expect, ok, level):
    rows.append((level, item, value, expect, ok))


def zone_of(x):
    for i, (lo, hi) in enumerate(ZONE):
        if lo <= x <= hi:
            return i
    return None


ap = argparse.ArgumentParser()
ap.add_argument("--film", default=str(FILM))
ap.add_argument("--json", action="store_true")
args = ap.parse_args()

film = json.loads(io.open(args.film, encoding="utf-8").read())
lines = film.get("lines") or []
panels = film.get("panels") or []

# ---------- 1 元素排布 ----------
el_total = 0
kind_counter = Counter()
column_panels = []
label_viol = []
y_viol = []
emoji_hits = []

for p in panels:
    els = p.get("elements") or []
    el_total += len(els)
    if not els:
        continue
    xs = [e.get("x", 50) for e in els]
    labels = [e for e in els if e.get("kind") == "label"]
    for e in els:
        kind_counter[e.get("kind")] += 1
        if e.get("y", 50) > Y_LIMIT:
            y_viol.append((p["id"], e.get("text") or e.get("kind"), e.get("y")))
        if e.get("kind") == "icon" and EMOJI_RE.search(str(e.get("name") or "")):
            emoji_hits.append((p["id"], e.get("name")))
    if len(els) >= 3 and (max(xs) - min(xs)) < MIN_X_SPAN_FOR_3:
        column_panels.append((p["id"], len(els), sorted(set(xs))))
    if len(labels) > LABEL_PER_PANEL_MAX:
        label_viol.append((p["id"], len(labels)))

add("元素总数", el_total, "—", True, "OK")
add(
    "同屏元素跨区（≥3 个时 x 跨 ≥25）",
    f"{len(column_panels)} 屏挤成一列",
    "0 屏",
    not column_panels,
    "FAIL" if column_panels else "OK",
)
for pid, n, xs in column_panels[:6]:
    add(f"  └ {pid}", f"{n} 个元素 x∈{xs}", "跨 ≥2 区", False, "FAIL")

add(
    "每屏 label 数",
    f"最多 {max([c for _, c in label_viol], default=LABEL_PER_PANEL_MAX)} 块",
    f"≤{LABEL_PER_PANEL_MAX}",
    not label_viol,
    "FAIL" if label_viol else "OK",
)
for pid, c in label_viol[:6]:
    add(f"  └ {pid}", f"{c} 块 label", f"≤{LABEL_PER_PANEL_MAX}", False, "FAIL")

ratio = kind_counter.get("label", 0) / el_total if el_total else 0
add(
    "label 占比",
    f"{ratio*100:.0f}%",
    f"≤{LABEL_RATIO_MAX*100:.0f}%",
    ratio <= LABEL_RATIO_MAX,
    "WARN" if ratio > LABEL_RATIO_MAX else "OK",
)

emoji_ratio = (kind_counter.get("icon", 0) + kind_counter.get("arrow", 0)) / el_total if el_total else 0
add(
    "icon/arrow 占比",
    f"{emoji_ratio*100:.0f}%（走 PNG 轨，不是 emoji）",
    f"≤{EMOJI_RATIO_MAX*100:.0f}%（超了元素太碎）",
    emoji_ratio <= EMOJI_RATIO_MAX,
    "WARN" if emoji_ratio > EMOJI_RATIO_MAX else "OK",
)

add(
    "元素 y 超过 74（会撞字幕）",
    f"{len(y_viol)} 个",
    "0",
    not y_viol,
    "FAIL" if y_viol else "OK",
)
for pid, txt, y in y_viol[:5]:
    add(f"  └ {pid}", f"{txt} y={y}", f"≤{Y_LIMIT}", False, "FAIL")

# ---------- 2 节奏 ----------
panel_durs = [p["end"] - p["start"] for p in panels]
card_durs = []
for i, ln in enumerate(lines):
    if ln.get("panel"):
        continue
    nxt = lines[i + 1]["start"] if i + 1 < len(lines) else film.get("totalSeconds", ln["end"])
    card_durs.append(max(0.0, nxt - ln["start"]))

if panel_durs:
    add("panel 一屏时长", f"中位 {statistics.median(panel_durs):.1f}s / 最短 {min(panel_durs):.1f}s",
        f"≥{PANEL_SHOT_MIN}s", min(panel_durs) >= PANEL_SHOT_MIN,
        "WARN" if min(panel_durs) < PANEL_SHOT_MIN else "OK")
if card_durs:
    med = statistics.median(card_durs)
    add("卡片句单镜中位", f"{med:.2f}s", f"≥{CARD_SHOT_MEDIAN_MIN}s（凯哥 2.75）",
        med >= CARD_SHOT_MEDIAN_MIN, "WARN" if med < CARD_SHOT_MEDIAN_MIN else "OK")
    tiny = [i for i, d in enumerate(card_durs) if d < 1.5]
    add("卡片句 <1.5s 的短镜", f"{len(tiny)} 句", "0", not tiny, "WARN" if tiny else "OK")

# ---------- 3 素材 ----------
slides = []
for ln in lines:
    c = ln.get("card") or {}
    if c.get("type") == "slides":
        slides += c.get("frames") or []
if slides:
    dup = [k for k, v in Counter(slides).items() if v > 1]
    add("slides 图片复用", f"{len(slides)} 张 / 唯一 {len(set(slides))}",
        "0 张重复", not dup, "WARN" if dup else "OK")
    for k in dup[:5]:
        add(f"  └ {k.split('/')[-1]}", f"用了 {Counter(slides)[k]} 次", "1 次", False, "WARN")

bg = Counter(p.get("bg") for p in panels)
dup_bg = [(k, v) for k, v in bg.items() if v > 1]
add("底板重复使用", f"{len(bg)} 张 / {len(panels)} 屏", "每张只用一次",
    not dup_bg, "WARN" if dup_bg else "OK")
for k, v in dup_bg[:5]:
    add(f"  └ {k.split('/')[-1]}", f"{v} 屏", "1 屏", False, "WARN")

# ---------- 4 字幕与音效 ----------
no_sub = sum(1 for ln in lines if ln.get("sub") is False)
add("不出字幕的句子", f"{no_sub}/{len(lines)}", "卡片大字同句时不出",
    True, "OK")

# 音效来自 pipeline/sfx.py 生成的 src/data/sfx.json（不铺 BGM，只点状音效）
sfx_path = Path(args.film).parent / "sfx.json"
try:
    sfx = json.loads(sfx_path.read_text(encoding="utf-8")) if sfx_path.is_file() else []
except ValueError:
    sfx = []
n_panel = len(film.get("panels") or [])
total_s = float(film.get("totalSeconds") or 0) or 1.0
per_panel = len(sfx) / n_panel if n_panel else 0
density = len(sfx) / total_s * 60
if not sfx:
    add("音效条数", "0（没跑 pipeline/sfx.py）", "每屏 ≥1 条，密度 ≤20 条/分钟",
        False, "WARN")
else:
    add("音效条数", f"{len(sfx)} 条 · {per_panel:.1f} 条/屏 · {density:.1f} 条/分钟",
        "每屏 ≥1 条，密度 ≤20 条/分钟",
        per_panel >= 1.0 and density <= 20, "WARN")
    add("  └ 不铺 BGM", "只有点状音效", "凯哥原片无 BGM", True, "OK")

# ---------- 输出 ----------
if args.json:
    print(json.dumps([{"level": l, "item": i, "value": v, "expect": e, "ok": o}
                      for l, i, v, e, o in rows], ensure_ascii=False, indent=1))
else:
    print(f"\n排布体检 · {Path(args.film).name}")
    print("─" * 62)
    icon = {"OK": "✓", "WARN": "·", "FAIL": "✗"}
    for lv, item, value, expect, _ok in rows:
        print(f"{icon.get(lv,'?')} {item:<34} {value:<26} {expect}")
    fails = sum(1 for r in rows if r[0] == "FAIL")
    warns = sum(1 for r in rows if r[0] == "WARN")
    print("─" * 62)
    print(f"FAIL {fails} · WARN {warns}" + ("" if fails else "  →  可以渲染"))
    sys.exit(1 if fails else 0)
