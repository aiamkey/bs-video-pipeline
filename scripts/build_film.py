"""合并「脚本（含卡片描述）」+「配音时间轴」→ src/data/film.json（渲染引擎读取）。

用法：
  python lbr-promo\\scripts\\build_film.py lbr-promo\\scripts\\script-ep02.json ep02

## 两种排法

1) 一句一镜（老写法）
   {"text": "第一件，头发。", "card": {"type": "copy", "text": "第一件|头发"}}

2) 一屏多句（凯哥做法，推荐）
   {"text": "她回了个「哦」。", "panel": {"id": "p1", "bg": "textures/lib/sofa-wrong.jpg"}}
   {"text": "你就开始想是不是说错了。", "panel": "p1",
    "el": {"kind": "bubble", "text": "她：哦", "x": 58, "y": 40}}
   {"text": "其实她只是没看手机。", "panel": "p1",
    "el": {"kind": "icon", "name": "phone", "x": 30, "y": 62}}

同一 panel 值的**连续句子**合成一屏：底板固定，每句触发一个元素弹入；
字幕仍按句走。屏内 line 不再渲染卡片。

card.type 支持：hook copy section image list no-list cmd stat quote chips brow posture color outro
              teacher board wrong annotate slides
panel 的 el.kind 支持：bubble label num icon arrow dot box
panel 的 el.name（kind=icon/arrow 时）：check cross house family clock phone money arrow up down

## 字幕去重（sub 字段）

卡片本身已经把这句话写成大字的类型，**不再叠一条白色字幕**（否则一句话出现两次，
开头尤其难看）。命中的类型见 NO_SUB；这些句子的 line 会带 `"sub": false`。
panel 句、slides、board、no-list、image 等「卡片文字≠语音」的类型照常出字幕。
"""
import io
import json
import sys
from pathlib import Path

# 卡片大字与语音高度重合的类型 → 不出字幕
NO_SUB = {"hook", "copy", "section", "wrong", "list", "outro", "stat"}

ROOT = Path(__file__).resolve().parents[1]
script_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "scripts" / "script-02.json"
name = sys.argv[2] if len(sys.argv) > 2 else "voice-02"

script = json.loads(script_path.read_text(encoding="utf-8-sig"))
tl = json.loads((ROOT / "src" / "data" / f"{name}-timeline.json").read_text(encoding="utf-8"))


def panel_id(v):
    """panel 字段允许字符串或 {id,bg} 对象。"""
    if v is None:
        return None
    if isinstance(v, str):
        return v
    return v.get("id")


def panel_bg(v):
    if isinstance(v, dict):
        return v.get("bg")
    return None


def panel_photo(v):
    """真人底图路径（可选）。有 photo 就优先用真人，没有就回落卡通 bg。"""
    if isinstance(v, dict):
        return v.get("photo")
    return None


def panel_zone(v):
    """文字放哪侧（right/left），只有 photo 模式才用。"""
    if isinstance(v, dict):
        return v.get("text_zone")
    return None


lines, sections = [], []
panels = []
cur = None


def flush():
    global cur
    if cur and cur["count"] > 0:
        cur["end"] = lines[cur["first"] + cur["count"] - 1]["end"]
        panels.append(cur)
    cur = None


for ci, ch in enumerate(tl["chapters"]):
    sec = script["chapters"][ci]
    sections.append({"label": sec.get("label") or ch["label"], "start": ch["start"], "end": ch["end"]})
    for li, line in enumerate(ch["lines"]):
        src_line = sec["lines"][li] if li < len(sec["lines"]) else {}
        pid = panel_id(src_line.get("panel"))
        entry = {
            "text": line["text"],
            "start": line["start"],
            "end": line["end"],
            "card": None if pid else src_line.get("card"),
            "panel": pid,
        }
        card = entry["card"] or {}
        if not pid and card.get("type") in NO_SUB:
            entry["sub"] = False
        if pid:
            if cur is None or cur["id"] != pid:
                flush()
                cur = {
                    "id": pid,
                    "bg": panel_bg(src_line.get("panel")) or "textures/lib/sofa-wrong.jpg",
                    "photo": panel_photo(src_line.get("panel")),
                    "text_zone": panel_zone(src_line.get("panel")) or "right",
                    "start": line["start"],
                    "end": line["end"],
                    "first": len(lines),
                    "count": 0,
                    "elements": [],
                }
            # 一句可以出多个元素：els=[...]（同一句里错开 0.35s 依次弹入），或单个 el
            els = src_line.get("els")
            if not els and src_line.get("el"):
                els = [src_line["el"]]
            for k, el in enumerate(els or []):
                e = dict(el)
                base = max(0.0, line["start"] - cur["start"])
                e["at"] = round(base + k * 0.35, 3)
                cur["elements"].append(e)
            cur["count"] += 1
        else:
            flush()
        lines.append(entry)
    flush()

flush()

film = {
    "title": script.get("title", name),
    "fps": script.get("fps", 30),
    "watermark": script.get("watermark", ""),
    "voice": f"audio/{name}.wav",
    "totalSeconds": tl["totalSeconds"],
    "sections": sections,
    "lines": lines,
    "panels": panels,
}
out = ROOT / "src" / "data" / "film.json"
io.open(out, "w", encoding="utf-8").write(json.dumps(film, ensure_ascii=False, indent=1))
print(
    f"{len(lines)} lines / {len(sections)} sections / {len(panels)} panels / "
    f"{sum(p['count'] for p in panels)} panel-lines / {film['totalSeconds']}s -> src/data/film.json"
)
for p in panels:
    print(
        f"  panel {p['id']:<4} {p['start']:>6.1f}-{p['end']:>6.1f}s  {p['count']} 句  "
        f"{len(p['elements'])} 元素  {p['bg'].split('/')[-1]}"
    )
