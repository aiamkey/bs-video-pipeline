"""合并「脚本（含卡片描述）」+「配音时间轴」→ src/data/film.json（渲染引擎读取）。

用法：
  python lbr-promo\\scripts\\build_film.py lbr-promo\\scripts\\script-02.json voice-02

script json 的每句可带 card：
  {"text": "第一件，头发。", "gap": 0.45,
   "card": {"type": "section", "no": "01", "title": "头发", "sub": "HAIR"}}
card.type 支持：hook copy section image list no-list cmd stat quote chips brow posture color outro
"""
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
script_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "scripts" / "script-02.json"
name = sys.argv[2] if len(sys.argv) > 2 else "voice-02"

script = json.loads(script_path.read_text(encoding="utf-8-sig"))
tl = json.loads((ROOT / "src" / "data" / f"{name}-timeline.json").read_text(encoding="utf-8"))

lines, sections = [], []
for ci, ch in enumerate(tl["chapters"]):
    sec = script["chapters"][ci]
    sections.append({"label": sec.get("label") or ch["label"], "start": ch["start"], "end": ch["end"]})
    for li, line in enumerate(ch["lines"]):
        src_line = sec["lines"][li] if li < len(sec["lines"]) else {}
        lines.append(
            {
                "text": line["text"],
                "start": line["start"],
                "end": line["end"],
                "card": src_line.get("card"),
            }
        )

film = {
    "title": script.get("title", name),
    "fps": script.get("fps", 30),
    "watermark": script.get("watermark", "52327471915"),
    "voice": f"audio/{name}.wav",
    "totalSeconds": tl["totalSeconds"],
    "sections": sections,
    "lines": lines,
}
out = ROOT / "src" / "data" / "film.json"
io.open(out, "w", encoding="utf-8").write(json.dumps(film, ensure_ascii=False, indent=1))
print(f"{len(lines)} lines / {len(sections)} sections / {film['totalSeconds']}s -> src/data/film.json")
