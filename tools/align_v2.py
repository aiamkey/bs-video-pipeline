"""稳健对齐：用 difflib 把稿子句子映射到 whisper 逐字时间（跳过 ASR 多字/错字）。

用法：
  set HF_ENDPOINT=https://hf-mirror.com
  python tools\\align_v2.py voice-bs-cheng.wav script-bs.json voice-bs-cheng
"""
import difflib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from faster_whisper import WhisperModel

ROOT = Path(r"C:\Users\张宇\OneDrive\Desktop\video\lbr-promo")
WAV_DIR = ROOT / "public" / "audio"
FFMPEG = "E:/miniconda/envs/JupyterProject/Lib/site-packages/imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v9.0.2.exe"


def clean(s: str) -> str:
    return re.sub(r"[^\u4e00-\u9fa5A-Za-z0-9]", "", s)


def load_pcm(path: Path) -> np.ndarray:
    tmp = Path(tempfile.mkdtemp()) / "a.raw"
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", str(path), "-ar", "16000", "-ac", "1", "-f", "s16le", str(tmp)], check=True)
    return np.fromfile(str(tmp), dtype=np.int16).astype(np.float32) / 32768.0


def main() -> None:
    wav_name, script_name, name = sys.argv[1], sys.argv[2], sys.argv[3]
    script = json.loads((ROOT / "scripts" / script_name).read_text(encoding="utf-8-sig"))
    sentences = [line["text"].strip() for ch in script["chapters"] for line in ch["lines"]]

    model = WhisperModel("small", device="cpu", compute_type="int8")
    segs, info = model.transcribe(load_pcm(WAV_DIR / wav_name), language="zh", word_timestamps=True, vad_filter=False)

    chars, asr_text = [], []
    for seg in segs:
        for w in seg.words or []:
            t = clean(w.word)
            if not t:
                continue
            step = (w.end - w.start) / max(1, len(t))
            for k, c in enumerate(t):
                chars.append(w.start + k * step)
                asr_text.append(c)
    asr = "".join(asr_text)
    total = float(info.duration)

    script_text, bounds, pos = "", [], 0
    for s in sentences:
        c = clean(s)
        bounds.append((pos, pos + len(c)))
        script_text += c
        pos += len(c)

    sm = difflib.SequenceMatcher(None, script_text, asr, autojunk=False)
    # script index -> asr index（仅匹配块内映射）
    s2a = {}
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ("equal", "replace"):
            span_s, span_a = i2 - i1, j2 - j1
            if span_s <= 0:
                continue
            for k in range(span_s):
                s2a[i1 + k] = j1 + min(span_a - 1, round(k * (span_a - 1) / max(1, span_s - 1))) if span_a > 0 else j1
    print(f"匹配字符 {len(s2a)}/{len(script_text)}  (ASR {len(asr)} 字)")

    def t_of(si: int) -> float | None:
        if si in s2a and 0 <= s2a[si] < len(chars):
            return chars[s2a[si]]
        # 就近找
        for d in range(1, 400):
            for cand in (si - d, si + d):
                if cand in s2a and 0 <= s2a[cand] < len(chars):
                    return chars[s2a[cand]]
        return None

    line_times = []
    for (a, b) in bounds:
        st = t_of(a)
        en = t_of(max(a, b - 1))
        if st is None:
            st = line_times[-1][1] if line_times else 0.0
        if en is None or en <= st:
            en = st + 1.2
        line_times.append((round(st, 3), round(en, 3)))
    for i in range(len(line_times) - 1):
        if line_times[i][1] > line_times[i + 1][0]:
            line_times[i] = (line_times[i][0], line_times[i + 1][0])

    chapters, li = [], 0
    for ci, ch in enumerate(script["chapters"]):
        lines = []
        for line in ch["lines"]:
            st, en = line_times[li]
            lines.append({"text": line["text"], "start": st, "end": en, "card": line.get("card")})
            li += 1
        chapters.append({"ch": ch.get("ch", ci), "label": ch["label"], "scene": ch.get("scene", ""),
                         "start": lines[0]["start"] if lines else 0,
                         "end": lines[-1]["end"] if lines else 0, "lines": lines})

    out = ROOT / "src" / "data" / f"{name}-timeline.json"
    out.write_text(json.dumps({"fps": 30, "totalSeconds": round(total, 3), "chapters": chapters}, ensure_ascii=False, indent=1), encoding="utf-8")

    rates = [(len(clean(l["text"])) / max(0.25, l["end"] - l["start"]), l["text"][:16]) for c in chapters for l in c["lines"]]
    bad = [r for r in rates if not 3.0 <= r[0] <= 8.5]
    print(f"时长 {total:.1f}s  异常 {len(bad)}/{len(rates)}")
    for b in bad[:6]:
        print("   ", round(b[0], 1), b[1])
    print("->", out.name)


main()
