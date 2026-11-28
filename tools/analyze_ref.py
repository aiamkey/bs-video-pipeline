"""拆解一条参考视频：结构 / 节奏 / 字幕 / 分屏 / 音效 / 卡片。

用法：
  python tools\\analyze_ref.py "qa2\\ref\\v1-shuaishuai.mp4" --start 0 --dur 180
  python tools\\analyze_ref.py REF.mp4                  # 全片
  python tools\\analyze_ref.py REF.mp4 --json out.json

不写任何文件到参考视频目录，产物统一落在 qa2\\refanalysis\\<片名>\\。

输出四张表：
  1) 语流：每句开始/结束、语速、句间停顿
  2) 镜头：切点、每镜时长
  3) 版式：每镜的画面构成（有没有字幕条、字幕在第几行、画面右侧是否留白）
  4) 配料：黑场、静音、音量包络
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

_HERE = Path(__file__).resolve()
for _base in (_HERE.parents[1], _HERE.parents[1] / "lbr-promo", _HERE.parent, _HERE.parent / "lbr-promo"):
    if (_base / "pipeline" / "env.py").is_file():
        sys.path.insert(0, str(_base / "pipeline"))
        break
import env  # noqa: E402

FFMPEG = env.ffmpeg()
OUT_ROOT = _HERE.parents[1] / "qa2" / "refanalysis"


# ---------------------------------------------------------------- probe
def probe(path: Path) -> dict:
    p = subprocess.run([FFMPEG, "-hide_banner", "-i", str(path)], capture_output=True, text=True, errors="replace")
    txt = p.stderr
    dur = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", txt)
    seconds = int(dur.group(1)) * 3600 + int(dur.group(2)) * 60 + float(dur.group(3)) if dur else 0.0
    v = re.search(r"Video:.*?(\d{2,5})x(\d{2,5})", txt)
    fps = re.search(r"(\d+(?:\.\d+)?) fps", txt)
    return {
        "duration": round(seconds, 2),
        "width": int(v.group(1)) if v else 0,
        "height": int(v.group(2)) if v else 0,
        "fps": float(fps.group(1)) if fps else 0.0,
    }


# ---------------------------------------------------------------- audio
def extract_wav(path: Path, start: float, dur: float) -> Path:
    tmp = Path(tempfile.mkdtemp()) / "a.wav"
    cmd = [FFMPEG, "-y", "-loglevel", "error"]
    if start:
        cmd += ["-ss", f"{start:.3f}"]
    cmd += ["-i", str(path)]
    if dur:
        cmd += ["-t", f"{dur:.3f}"]
    cmd += ["-vn", "-ac", "1", "-ar", "16000", str(tmp)]
    subprocess.run(cmd, check=True)
    return tmp


def load_pcm16k(wav: Path) -> np.ndarray:
    """自己读 wav -> float32 mono 16k，绕开 faster-whisper 内部的 av 解码（本机 av 版本过旧）。"""
    import wave

    with wave.open(str(wav), "rb") as w:
        n, ch, sw, sr = w.getnframes(), w.getnchannels(), w.getsampwidth(), w.getframerate()
        raw = w.readframes(n)
    if sw != 2:
        raise ValueError(f"只支持 16bit wav，实际 sampwidth={sw}")
    a = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if ch > 1:
        a = a.reshape(-1, ch).mean(axis=1)
    if sr != 16000:
        # 线性重采样（够用：只喂 ASR）
        idx = np.linspace(0, len(a) - 1, int(len(a) * 16000 / sr))
        a = np.interp(idx, np.arange(len(a)), a).astype(np.float32)
    return a


def transcribe(wav: Path, model_size: str = "small") -> list[dict]:
    from faster_whisper import WhisperModel

    audio = load_pcm16k(wav)
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, info = model.transcribe(
        audio, language="zh", vad_filter=True, beam_size=1,
        word_timestamps=True,
    )
    out = []
    for s in segments:
        words = [{"w": w.word, "s": round(w.start, 3), "e": round(w.end, 3)} for w in (s.words or [])]
        chars = max(1, len(re.sub(r"[^\u4e00-\u9fa5A-Za-z0-9]", "", s.text)))
        out.append({
            "text": s.text.strip(),
            "start": round(s.start, 3),
            "end": round(s.end, 3),
            "dur": round(s.end - s.start, 3),
            "chars": chars,
            "cps": round(chars / max(0.01, s.end - s.start), 2),
            "words": words,
        })
    return out


# ---------------------------------------------------------------- cuts
def detect_cuts(path: Path, start: float, dur: float, threshold: float = 8.0) -> list[float]:
    cmd = [FFMPEG, "-hide_banner", "-nostats"]
    if start:
        cmd += ["-ss", f"{start:.3f}"]
    cmd += ["-i", str(path)]
    if dur:
        cmd += ["-t", f"{dur:.3f}"]
    cmd += ["-vf", f"scdet=threshold={threshold}", "-f", "null", "-"]
    p = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    cuts = [round(float(m), 3) for m in re.findall(r"lavfi\.scd\.time: ([\d.]+)", p.stderr)]
    return sorted(set(cuts))


def detect_changes(path: Path, start: float, dur: float, fps_sample: float = 4.0,
                   thresh: float = 0.055) -> list[dict]:
    """帧差法：按 fps_sample 采样，找画面显著变化。适合「一屏多元素累加」这类没有硬切的视频。"""
    tmpdir = Path(tempfile.mkdtemp())
    cmd = [FFMPEG, "-y", "-loglevel", "error"]
    if start:
        cmd += ["-ss", f"{start:.3f}"]
    cmd += ["-i", str(path)]
    if dur:
        cmd += ["-t", f"{dur:.3f}"]
    cmd += ["-vf", f"fps={fps_sample},scale=160:-2", str(tmpdir / "f%05d.png")]
    subprocess.run(cmd, check=True)

    from PIL import Image

    files = sorted(tmpdir.glob("f*.png"))
    prev = None
    out = []
    step = 1.0 / fps_sample
    for i, f in enumerate(files):
        a = np.asarray(Image.open(f).convert("L").resize((160, 90)), dtype=np.float32) / 255.0
        if prev is not None:
            d = float(np.abs(a - prev).mean())
            if d > thresh:
                out.append({"t": round(i * step, 2), "diff": round(d, 4)})
        prev = a
    return out


def detect_silence(path: Path, start: float, dur: float, db: float = -32.0, min_len: float = 0.18) -> list[dict]:
    cmd = [FFMPEG, "-hide_banner", "-nostats"]
    if start:
        cmd += ["-ss", f"{start:.3f}"]
    cmd += ["-i", str(path)]
    if dur:
        cmd += ["-t", f"{dur:.3f}"]
    cmd += ["-af", f"silencedetect=noise={db}dB:d={min_len}", "-f", "null", "-"]
    p = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.-]+)", p.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.-]+)", p.stderr)]
    out = []
    for i, s in enumerate(starts):
        e = ends[i] if i < len(ends) else None
        if e is None:
            continue
        out.append({"start": round(s, 3), "end": round(e, 3), "dur": round(e - s, 3)})
    return out


# ---------------------------------------------------------------- layout
def grab_frame(path: Path, t: float, out: Path) -> bool:
    p = subprocess.run(
        [FFMPEG, "-y", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", str(path),
         "-frames:v", "1", "-vf", "scale=640:-2", str(out)],
        capture_output=True,
    )
    return p.returncode == 0 and out.is_file()


def frame_profile(img_path: Path) -> dict:
    """用像素统计判断版式：字幕条 / 人物区 / 留白区。"""
    from PIL import Image

    im = Image.open(img_path).convert("L")
    a = np.asarray(im, dtype=np.float32) / 255.0
    h, w = a.shape
    # 竖向分 10 段，看每段里"高对比边缘"密度（文字/图形越多越高）
    rows = []
    for i in range(10):
        band = a[int(h * i / 10):int(h * (i + 1) / 10), :]
        gx = np.abs(np.diff(band, axis=1))
        rows.append(round(float((gx > 0.18).mean()), 4))
    # 横向分 3 段（左/中/右），看边缘密度 = 内容密度
    cols = []
    for i in range(3):
        band = a[:, int(w * i / 3):int(w * (i + 1) / 3)]
        gx = np.abs(np.diff(band, axis=1))
        cols.append(round(float((gx > 0.18).mean()), 4))
    # 底部 20% 是否有强对比（字幕条特征）
    bottom = a[int(h * 0.78):, :]
    gxb = np.abs(np.diff(bottom, axis=1))
    sub_density = round(float((gxb > 0.25).mean()), 4)
    return {
        "rows": rows,
        "cols": cols,
        "sub_density": sub_density,
        "has_subtitle": sub_density > 0.02,
        "bright": round(float(a.mean()), 3),
        "contrast": round(float(a.std()), 3),
    }


# ---------------------------------------------------------------- report
@dataclass
class Report:
    file: str = ""
    probe: dict = field(default_factory=dict)
    window: dict = field(default_factory=dict)
    sentences: list = field(default_factory=list)
    cuts: list = field(default_factory=list)
    shots: list = field(default_factory=list)
    silences: list = field(default_factory=list)
    layouts: list = field(default_factory=list)
    stats: dict = field(default_factory=dict)


def build(path: Path, start: float, dur: float, model: str, sample_layout: bool) -> Report:
    r = Report(file=str(path))
    r.probe = probe(path)
    total = r.probe["duration"]
    dur = dur or max(0.0, total - start)
    r.window = {"start": start, "dur": round(dur, 2)}

    print("[1/4] 抽音轨 + 转写 ...", flush=True)
    wav = extract_wav(path, start, dur)
    r.sentences = transcribe(wav, model)

    print("[2/4] 画面变化 + 聚类成屏 ...", flush=True)
    r.cuts = detect_cuts(path, start, dur)
    changes = detect_changes(path, start, dur, fps_sample=6.0, thresh=0.05)
    # 变化簇合并：间隔 < 0.6s 视为同一次变化（元素连弹）
    clusters: list[dict] = []
    for c in changes:
        if clusters and c["t"] - clusters[-1]["end"] < 0.6:
            clusters[-1]["end"] = c["t"]
            clusters[-1]["peak"] = max(clusters[-1]["peak"], c["diff"])
        else:
            clusters.append({"start": c["t"], "end": c["t"], "peak": c["diff"]})
    bounds = [0.0] + [c["start"] for c in clusters] + [dur]
    r.shots = [
        {"i": i, "start": round(bounds[i], 3), "end": round(bounds[i + 1], 3),
         "dur": round(bounds[i + 1] - bounds[i], 3)}
        for i in range(len(bounds) - 1)
    ]
    r.stats["画面变化簇"] = len(clusters)
    r.stats["硬切镜头"] = len(r.cuts)

    print("[3/4] 静音 + 音量 ...", flush=True)
    r.silences = detect_silence(path, start, dur)

    if sample_layout:
        print("[4/4] 版式抽样 ...", flush=True)
        outdir = OUT_ROOT / re.sub(r"[^\w.-]", "_", path.stem)
        outdir.mkdir(parents=True, exist_ok=True)
        for s in r.shots:
            mid = s["start"] + s["dur"] / 2
            img = outdir / f"shot{s['i']:03d}.jpg"
            if grab_frame(path, start + mid, img):
                prof = frame_profile(img)
                prof.update({"shot": s["i"], "t": round(start + mid, 2)})
                r.layouts.append(prof)

    # 统计
    d = [s["dur"] for s in r.shots] or [0]
    cps = [s["cps"] for s in r.sentences] or [0]
    gaps = []
    for a, b in zip(r.sentences, r.sentences[1:]):
        gaps.append(round(b["start"] - a["end"], 3))
    sub_ratio = (sum(1 for x in r.layouts if x["has_subtitle"]) / len(r.layouts)) if r.layouts else 0.0
    r.stats = {
        "句子数": len(r.sentences),
        "字数": sum(s["chars"] for s in r.sentences),
        "字每秒": round(sum(s["chars"] for s in r.sentences) / max(0.01, dur), 2),
        "镜头数": len(r.shots),
        "单镜中位": round(float(np.median(d)), 2),
        "单镜最短": round(min(d), 2),
        "单镜最长": round(max(d), 2),
        "句间停顿中位": round(float(np.median(gaps)) if gaps else 0.0, 2),
        "静音总时长": round(sum(x["dur"] for x in r.silences), 2),
        "静音占比": round(sum(x["dur"] for x in r.silences) / max(0.01, dur), 3),
        "cps 中位": round(float(np.median(cps)), 2),
        "有字幕镜头占比": round(sub_ratio, 3),
    }
    return r


def print_report(r: Report) -> None:
    p = r.probe
    print()
    print("=" * 78)
    print(f"{Path(r.file).name}   {p['width']}x{p['height']}  {p['fps']}fps  全长 {p['duration']}s"
          f"   分析窗 {r.window['start']}–{r.window['start'] + r.window['dur']:.1f}s")
    print("=" * 78)
    print("\n【统计】")
    for k, v in r.stats.items():
        print(f"  {k:<12} {v}")

    print(f"\n【语流】前 20 句（共 {len(r.sentences)}）")
    print(f"  {'开始':>7} {'时长':>6} {'字数':>4} {'字/秒':>6}  文本")
    for s in r.sentences[:20]:
        print(f"  {s['start']:>7.2f} {s['dur']:>6.2f} {s['chars']:>4} {s['cps']:>6.2f}  {s['text'][:34]}")

    print(f"\n【镜头】前 20 个（共 {len(r.shots)}）")
    for s in r.shots[:20]:
        prof = next((x for x in r.layouts if x["shot"] == s["i"]), None)
        tag = ""
        if prof:
            tag = f"  sub={'Y' if prof['has_subtitle'] else 'n'} cols={prof['cols']} bright={prof['bright']}"
        print(f"  #{s['i']:<3} {s['start']:>7.2f}–{s['end']:>7.2f}  {s['dur']:>5.2f}s{tag}")

    print(f"\n【静音】{len(r.silences)} 处，总 {r.stats['静音总时长']}s")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--dur", type=float, default=0.0)
    ap.add_argument("--model", default="small")
    ap.add_argument("--no-layout", action="store_true")
    ap.add_argument("--json", default="")
    a = ap.parse_args()

    path = Path(a.video)
    if not path.is_file():
        sys.exit(f"找不到 {path}")

    r = build(path, a.start, a.dur, a.model, not a.no_layout)
    print_report(r)

    out = Path(a.json) if a.json else OUT_ROOT / re.sub(r"[^\w.-]", "_", path.stem) / "report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(asdict(r), ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n报告 -> {out}")


if __name__ == "__main__":
    main()
