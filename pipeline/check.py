# -*- coding: utf-8 -*-
"""自动质检：成片时长 / 字数 / 语速 / 单镜时长 / 静止段 / 响度。

用法：python lbr-promo\\pipeline\\check.py ep01
读取 pipeline/config.json 的阈值，输出 PASS / WARN 表；有 FAIL 时退出码 1。
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
PROMO = HERE.parent
ROOT = PROMO.parent
def _load_cfg():
    for name in ("config.local.json", "config.json", "config.example.json"):
        f = HERE / name
        if f.exists():
            return json.loads(f.read_text(encoding="utf-8"))
    raise SystemExit("✗ 找不到 config")


CFG = _load_cfg()
FF = CFG["paths"]["ffmpeg"]
NAME = sys.argv[1] if len(sys.argv) > 1 else CFG["project"]["ep"]

MP4 = Path(sys.argv[2]) if len(sys.argv) > 2 else PROMO / "out" / f"{NAME}-final.mp4"
if not MP4.is_absolute():
    cand = Path.cwd() / MP4
    MP4 = cand if cand.exists() else (PROMO / MP4)
if not MP4.exists():
    MP4 = PROMO / "out" / f"{NAME}.mp4"
TL = PROMO / "src" / "data" / f"{NAME}-timeline.json"
SCRIPT = PROMO / CFG["project"]["script"]

rows = []
fails = 0


def add(item, value, rule, ok, hard=True):
    global fails
    status = "PASS" if ok else ("FAIL" if hard else "WARN")
    rows.append((item, str(value), rule, status))
    if status == "FAIL":
        fails += 1


def probe_duration(p):
    out = subprocess.run([FF, "-hide_banner", "-i", str(p)], capture_output=True, text=True,
                         encoding="utf-8", errors="replace").stderr
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", out)
    if not m:
        return 0.0
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def frame_diffs(p, fps):
    vf = f"fps={fps},scale=160:90"
    raw = subprocess.run([FF, "-v", "error", "-i", str(p), "-vf", vf, "-f", "rawvideo",
                          "-pix_fmt", "gray", "-"], capture_output=True).stdout
    n = len(raw) // (160 * 90)
    if n < 3:
        return np.array([]), n
    arr = np.frombuffer(raw[: n * 160 * 90], dtype=np.uint8).reshape(n, 90, 160).astype(np.float32)
    return np.abs(np.diff(arr, axis=0)).mean(axis=(1, 2)), n


def loudness(p):
    out = subprocess.run([FF, "-hide_banner", "-i", str(p), "-af", "loudnorm=print_format=json",
                          "-f", "null", "-"], capture_output=True, text=True,
                         encoding="utf-8", errors="replace").stderr
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", out, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


# ---- 1 文件与时长 ----
dur = probe_duration(MP4) if MP4.exists() else 0
size_mb = MP4.stat().st_size / 1048576 if MP4.exists() else 0
add("文件大小(MB)", f"{size_mb:.1f}", f"≥{CFG['check']['min_filesize_mb']}",
    size_mb >= CFG["check"]["min_filesize_mb"], hard=(dur >= 30))

dmode = CFG["video"]["duration"]
if dmode["mode"] == "target":
    t = dmode["target_sec"]
    tol = dmode["tolerance_pct"] / 100
    lo, hi = t * (1 - tol), t * (1 + tol)
    add("成片时长(s)", f"{dur:.1f}", f"{lo:.0f}–{hi:.0f}", lo <= dur <= hi)
else:
    lo, hi = dmode.get("auto_bounds", [30, 600])
    add("成片时长(s)", f"{dur:.1f}", f"{lo}–{hi}（auto 不限目标）", lo <= dur <= hi, hard=False)

# ---- 2 字数与语速 ----
FILM = PROMO / "src" / "data" / "film.json"
if FILM.exists():                       # film.json 才是这次真正渲染的内容
    texts = [l["text"] for l in json.loads(FILM.read_text(encoding="utf-8"))["lines"]]
else:
    script = json.loads(SCRIPT.read_text(encoding="utf-8-sig"))
    texts = [l["text"] for ch in script["chapters"] for l in ch["lines"]]
chars = sum(len(re.sub(r"[^\u4e00-\u9fa5A-Za-z0-9]", "", t)) for t in texts)
if CFG["video"]["duration"]["mode"] == "target":
    cps_mid = sum(CFG["voice"]["target_cps"]) / 2
    need = CFG["video"]["duration"]["target_sec"] * cps_mid
    clo, chi = need * 0.9, need * 1.1
    add("总字数", chars, f"{clo:.0f}–{chi:.0f}（按目标时长推算）", clo <= chars <= chi)
else:
    clo, chi = CFG["text"]["auto_bounds"]
    add("总字数", chars, f"{clo}–{chi}（auto 不限）", clo <= chars <= chi, hard=False)
add("句数", len(texts), "—", True)
cps_total = chars / max(1e-6, dur) if dur else 0
vlo, vhi = CFG["voice"]["target_cps"]
add("整体字/秒", f"{cps_total:.2f}", f"{vlo}–{vhi}", vlo <= cps_total <= vhi, hard=(dur >= 30))

# ---- 3 单镜时长 / 单句语速（来自 timeline）----
if TL.exists():
    tl = json.loads(TL.read_text(encoding="utf-8"))
    lines = [l for ch in tl["chapters"] for l in ch["lines"]]
    durs = [l["end"] - l["start"] for l in lines]
    med = float(np.median(durs)) if durs else 0
    smin, smax = CFG["video"]["shot_median_sec"]
    add("单镜中位(s)", f"{med:.2f}", f"{smin}–{smax}", smin <= med <= smax, hard=False)
    mx = max(durs) if durs else 0
    add("最长单镜(s)", f"{mx:.2f}", f"≤{CFG['video']['shot_max_sec']}",
        mx <= CFG["video"]["shot_max_sec"], hard=False)
    bad = []
    for l in lines:
        c = len(re.sub(r"[^\u4e00-\u9fa5A-Za-z0-9]", "", l["text"]))
        r = c / max(0.25, l["end"] - l["start"])
        if not 3.0 <= r <= 9.0:
            bad.append((round(r, 1), l["text"][:14]))
    add("语速异常句", f"{len(bad)}/{len(lines)}", "≤3", len(bad) <= 3)
    for r, t in bad[:5]:
        rows.append(("   · " + t, f"{r}", "3–9", "WARN"))
else:
    add("timeline", "缺失", "存在", False)

# ---- 4 静止段 ----
if MP4.exists():
    fps = CFG["check"]["sample_fps"]
    diffs, nframes = frame_diffs(MP4, fps)
    th = CFG["check"]["still_diff_threshold"]
    limit = CFG["video"]["still_max_sec"]
    runs, cur = [], 0
    for d in diffs:
        if d < th:
            cur += 1
        else:
            if cur:
                runs.append(cur / fps)
            cur = 0
    if cur:
        runs.append(cur / fps)
    worst = max(runs) if runs else 0
    add("最长静止段(s)", f"{worst:.1f}", f"≤{limit}", worst <= limit, hard=False)
    add("静止占比", f"{sum(runs)/max(1e-6,dur)*100:.0f}%", "≤40%", sum(runs)/max(1e-6,dur) <= 0.40, hard=False)

# ---- 5 响度 ----
if MP4.exists():
    ln = loudness(MP4)
    if ln:
        add("响度(LUFS)", ln.get("input_i", "?"), f"≈{CFG['voice']['lufs']}",
            abs(float(ln.get("input_i", -99)) - CFG["voice"]["lufs"]) <= 2.0)
        add("真峰值(dBTP)", ln.get("input_tp", "?"), f"≤{CFG['voice']['true_peak']}",
            float(ln.get("input_tp", 0)) <= CFG["voice"]["true_peak"] + 0.3)
    else:
        add("响度", "解析失败", "—", False)

# ---- 输出 ----
w = max(len(r[0]) for r in rows) + 2
print(f"\n质检 · {MP4.name}\n" + "─" * (w + 30))
for r in rows:
    mark = {"PASS": "✓", "WARN": "·", "FAIL": "✗"}[r[3]]
    print(f"{mark} {r[0].ljust(w)} {r[1]:>12}   {r[2]}")
print("─" * (w + 30))
print("全部通过" if fails == 0 else f"{fails} 项未通过")
sys.exit(1 if fails else 0)

