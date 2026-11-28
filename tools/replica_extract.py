# -*- coding: utf-8 -*-
"""任意动画式参考片 → spec.json（结构事实层）。

设计目标：**换片不用改代码**。输入一个本地 mp4，输出符合
qa2/replica/spec.schema.json 的 spec.json，供 replica.py validate /
jianying 以及后续 GPT 重画、克隆配音、Remotion 渲染使用。

用法：
  python tools\\replica_extract.py REF.mp4
  python tools\\replica_extract.py REF.mp4 -o qa2\\replica\\out\\ref.spec.json
  python tools\\replica_extract.py REF.mp4 --segs qa2\\ref\\q6.segs.json   # 复用已有 ASR，跳过转写
  python tools\\replica_extract.py REF.mp4 --model small --no-layout

三层：
  1. 事实层（本文件）：ffmpeg 探针 + faster-whisper 转写 + 帧差切点 +
     逐像素版式量测。全部本地、不联网、不花钱。
  2. 归类层（本文件，规则）：把碎镜头按版式指纹合并成「屏」，再判
     chat / title / doc / scene。
  3. 语义层（外部 hook）：素材 prompt、声音克隆、画面重画。本文件只写
     占位 prompt 与克隆参考段，不联网。

产物落 qa2\\refanalysis\\<片名>\\（帧图、extract.log、spec.json）。
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import os
import re
import sys
import time
import traceback
from pathlib import Path

import numpy as np

_HERE = Path(__file__).resolve()
sys.path.insert(0, str(_HERE.parent))
import analyze_ref as ar  # noqa: E402

VERSION = "1.0"
MODES = ("scene", "chat", "title", "doc")

# 版式指纹合并阈值：rows/cols/sub_density/bright/contrast 归一化后的欧氏距离
SCREEN_MERGE_THR = 0.42
# 两屏最短间隔（秒），小于此视为同一次变化的抖动
SCREEN_MIN_GAP = 0.55
# 章节切分：句间停顿阈值（秒）
SECTION_PAUSE = 1.15
# 章节标题最长字数
SECTION_TITLE_MAX = 18


# ---------------------------------------------------------------- 小工具
def _f(d, *keys, default=None):
    """按多个候选键取第一个非空值；dict 取键、对象取属性。

    analyze_ref 的 Report 是 dataclass，所以这里不能只查 dict。
    """
    if d is None:
        return default
    if isinstance(d, dict):
        for k in keys:
            if k in d and d[k] is not None:
                return d[k]
        return default
    for k in keys:
        if hasattr(d, k):
            v = getattr(d, k)
            if v is not None:
                return v
    return default


def _r(x, n=2):
    try:
        return round(float(x), n)
    except (TypeError, ValueError):
        return x


def _safe_name(p: Path) -> str:
    name = p.stem
    name = re.sub(r"[^\w\u4e00-\u9fff.-]+", "_", name)
    return name[:60] or "ref"


# ---------------------------------------------------------------- 事实层
def collect_facts(video: Path, start: float, dur: float, model: str,
                  sample_layout: bool, need_asr: bool):
    """跑一遍 analyze_ref.build，拿到事实层 Report。

    need_asr=False（给了 --segs）时用空转写桩跳过 ASR，省时且不要求
    faster_whisper 环境；当前环境没有 faster_whisper 时同样自动降级，
    改由 --segs 或 sf_asr 补字幕。返回 (report, asr_note)。
    """
    orig = ar.transcribe
    stub = lambda wav, model_size="small": []  # noqa: E731

    def run(use_stub: bool):
        ar.transcribe = stub if use_stub else orig
        try:
            return ar.build(video, start, dur, model, sample_layout)
        finally:
            ar.transcribe = orig

    if not need_asr:
        return run(True), "skipped:--segs"
    try:
        return run(False), f"faster-whisper/{model}"
    except ModuleNotFoundError as exc:
        print(f"[extract] ASR 不可用（{exc}）→ 无转写模式，字幕请用 --segs 补")
        return run(True), f"unavailable:{exc}"


def norm_sentences(raw) -> list[dict]:
    """把 ASR 结果规范成 [{s, e, text}]，丢掉空句与零长句。"""
    out = []
    for it in raw or []:
        s = _f(it, "start", "s", "begin")
        e = _f(it, "end", "e", "stop")
        t = (_f(it, "text", "t", "sentence", default="") or "").strip()
        if s is None or e is None or not t:
            continue
        s, e = float(s), float(e)
        if e - s < 0.08:
            continue
        out.append({"s": _r(s), "e": _r(e), "text": t})
    out.sort(key=lambda x: x["s"])
    return out


def load_segs(path: Path) -> list[dict]:
    """复用已有 q6.segs.json（[{s,e,text}] 或 {segments:[...]}]）。"""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("segments") or data.get("segs") or data.get("sentences") or []
    return norm_sentences(data)


def layout_vec(lay: dict) -> np.ndarray:
    """版式指纹：把 frame_profile 压成数值向量。

    注意 frame_profile 的 bright / contrast 是 **0–1 量纲**（不是 0–255），
    rows / cols 是边缘密度。两侧差一个数量级，所以给 bright/contrast 加权，
    再用 sqrt(维度) 归一化距离，避免它们被边缘密度淹没。
    """
    rows = (list(_f(lay, "rows", default=[]) or []) + [0.0] * 10)[:10]
    cols = (list(_f(lay, "cols", default=[]) or []) + [0.0] * 3)[:3]
    bright = float(_f(lay, "bright", default=0.5))
    contrast = float(_f(lay, "contrast", default=0.2))
    sub = float(_f(lay, "sub_density", default=0.0))
    v = [float(x) for x in rows] + [float(x) for x in cols] + [bright * 3.0, contrast * 3.0, sub]
    return np.array(v, dtype=float)


def classify_mode(lay: dict) -> str:
    """规则判版式类型（阈值按 frame_profile 的 0–1 量纲校准）。

    title : 极亮/极暗底 + 边缘稀少（大字标题卡、封面）
    doc   : 横纹均匀铺满、底部几乎无字幕条（文档页、长文卡）
    chat  : 浅底、中央成块、左右不平衡（聊天气泡、信息卡）
    scene : 其余图文卡 / 卡通场景
    """
    rows = np.array((list(_f(lay, "rows", default=[]) or []) + [0.0] * 10)[:10], dtype=float)
    cols = np.array((list(_f(lay, "cols", default=[]) or []) + [0.0] * 3)[:3], dtype=float)
    bright = float(_f(lay, "bright", default=0.5))
    contrast = float(_f(lay, "contrast", default=0.2))
    sub = float(_f(lay, "sub_density", default=0.0))

    row_sum = float(rows.sum())
    row_active = float((rows > 0.04).mean())
    col_mid, col_left, col_right = float(cols[1]), float(cols[0]), float(cols[2])
    imbalance = abs(col_left - col_right)

    if row_sum >= 0.60 and row_active >= 0.7 and sub < 0.03:
        return "doc"
    if (bright >= 0.86 or bright <= 0.16) and row_sum <= 0.34:
        return "title"
    if bright >= 0.58 and contrast <= 0.30 and col_mid >= max(col_left, col_right) and imbalance >= 0.012:
        return "chat"
    return "scene"


def merge_shots(shots: list[dict], layouts: list[dict], min_dur: float = 0.8) -> list[dict]:
    """把 shot 整理成「屏」。

    实测（q6 原片 547s → 61 镜 / 手工标注 58 屏）：这类「一屏多元素累加」
    的视频，整片版式指纹几乎不变（相邻距离中位 0.028），屏的边界来自
    **画面内容变化**，而 analyze_ref 的 shots 已经按这些变化切好。所以
    默认 1 shot = 1 屏，只做两件清理：
      · <0.3s 的抖动并进上一屏
      · 过短且同 mode 的相邻屏合并
    版式向量留给 mode 分类与后续调参，不再用来切屏。
    """
    if not shots:
        return []
    lay_by_shot = {}
    for lay in layouts or []:
        idx = _f(lay, "shot", "index")
        if idx is not None:
            lay_by_shot[int(idx)] = lay

    screens: list[dict] = []
    for k, sh in enumerate(shots):
        i = int(_f(sh, "i", "index", default=k))
        s = float(_f(sh, "start", "s", default=0.0))
        e = float(_f(sh, "end", "e", default=s))
        lay = lay_by_shot.get(i) or {}
        mode = classify_mode(lay)
        if screens and (e - s) < 0.3:
            screens[-1]["e"] = max(screens[-1]["e"], e)
            screens[-1]["shots"].append(i)
            continue
        screens.append({"s": s, "e": e, "mode": mode, "shots": [i], "lay": lay})

    screens = _coalesce(screens, min_dur=min_dur)
    for k2, sc in enumerate(screens):
        sc["idx"] = k2
        sc.pop("lay", None)
    return screens


def _coalesce(screens: list[dict], min_dur: float = 0.8) -> list[dict]:
    """把过短的屏并进前一个同 mode 的屏。"""
    out: list[dict] = []
    for sc in screens:
        if out and (sc["e"] - sc["s"]) < min_dur and out[-1]["mode"] == sc["mode"]:
            out[-1]["e"] = max(out[-1]["e"], sc["e"])
            out[-1]["shots"].extend(sc["shots"])
        else:
            out.append(dict(sc))
    return out


def infer_sections(subs: list[dict], total: float) -> list[dict]:
    """切章。先按长停顿切；切不出足够章数时按句数等分。

    实测：快节奏口播（q6 cps 6.72）句间几乎无停顿，整片只有 1–2 个
    ≥1.15s 的空档，纯停顿法会得到「全片一章」。复刻要的是可看的章节
    骨架，所以退化为按目标章数等分（每章约 60–120s）。
    """
    if not subs:
        return []
    target = 3 if total < 150 else max(3, min(8, int(round(total / 90.0))))
    secs = _sections_by_pause(subs)
    if len(secs) < target:
        secs = _sections_by_count(subs, target)
    return secs


def _sections_by_pause(subs: list[dict]) -> list[dict]:
    """按 ≥SECTION_PAUSE 的句间停顿切章。"""
    marks = [0]
    for i in range(1, len(subs)):
        if subs[i]["s"] - subs[i - 1]["e"] >= SECTION_PAUSE:
            marks.append(i)
    marks.append(len(subs))
    out = []
    for k in range(len(marks) - 1):
        a, b = marks[k], marks[k + 1] - 1
        if b < a:
            continue
        out.append(
            {
                "label": f"{k + 1:02d}",
                "start": subs[a]["s"],
                "end": subs[b]["e"],
                "title": subs[a]["text"][:SECTION_TITLE_MAX],
                "first": subs[a]["text"],
                "lines": b - a + 1,
            }
        )
    return out


def _sections_by_count(subs: list[dict], target: int) -> list[dict]:
    """把句子按目标章数等分，边界落在句子起点。"""
    n = len(subs)
    target = max(1, min(target, n))
    out = []
    for k in range(target):
        a = round(k * n / target)
        b = round((k + 1) * n / target) - 1
        if b < a:
            continue
        out.append(
            {
                "label": f"{k + 1:02d}",
                "start": subs[a]["s"],
                "end": subs[b]["e"],
                "title": subs[a]["text"][:SECTION_TITLE_MAX],
                "first": subs[a]["text"],
                "lines": b - a + 1,
            }
        )
    return out


def pick_voice_ref(subs: list[dict], silences: list[dict], total: float,
                   lo: float = 10.0, hi: float = 20.0) -> dict:
    """从原片挑一段 10–20s 的干净人声（无静音穿插）做克隆参考。

    返回 {start, dur, note}；挑不到就给 0 时长并说明。
    """
    if not subs:
        return {"start": 0.0, "dur": 0.0, "note": "无转写结果，无法挑参考段"}
    sil = [(float(_f(x, "start", "s", default=0)), float(_f(x, "end", "e", default=0))) for x in (silences or [])]

    def clean_in(a: float, b: float) -> bool:
        return all(b <= s0 or a >= e0 for s0, e0 in sil if e0 > s0)

    best = None
    n = len(subs)
    for i in range(n):
        a = subs[i]["s"]
        for j in range(i, n):
            b = subs[j]["e"]
            dur = b - a
            if dur < lo:
                continue
            if dur > hi:
                break
            if clean_in(a, b):
                score = abs(dur - 14.0)
                if best is None or score < best[0]:
                    best = (score, a, dur)
                break
    if best is None:
        # 放宽：允许有短停顿，取最长连续段
        a = subs[0]["s"]
        b = subs[min(n - 1, 12)]["e"]
        return {"start": _r(a), "dur": _r(max(0.0, b - a)), "note": "未找到完全干净段，取片头连续句（含停顿）"}
    return {"start": _r(best[1]), "dur": _r(best[2]), "note": "本地规则挑选：连续句、无静音穿插"}


def scene_prompt(mode: str, lay: dict, idx: int) -> str:
    """给每屏一个占位画面 prompt（语义层可覆盖；此处只用版式事实描述）。"""
    bright = float(_f(lay, "bright", default=128.0))
    tone = "浅色底" if bright >= 140 else ("深色底" if bright <= 96 else "中性底")
    base = {
        "chat": "手机聊天界面截图风格，浅灰底，圆角气泡左问右答，无头像照片",
        "title": "大字标题卡，纯色底，一到两行粗体中文标题居中偏上",
        "doc": "文档页风格，白纸质感，多行正文与标题层级，简洁排版",
        "scene": "扁平卡通插画卡，简洁图形与色块，留出文字区",
    }[mode]
    return f"[P{idx:02d}][{mode}][{tone}] {base}"


# ---------------------------------------------------------------- 组装
def build_spec(video: Path, report, args, asr_note: str = "") -> dict:
    probe = _f(report, "probe", default={}) or {}
    total = float(_f(probe, "duration", "dur", default=0.0) or 0.0)
    window = _f(report, "window", default={}) or {}
    w_start = float(_f(window, "start", default=0.0) or 0.0)
    w_dur = float(_f(window, "dur", default=0.0) or 0.0)
    # 只分析片段时（--dur），时长取窗口终点，别把整片时长套到局部结果上
    if w_dur > 0 and (w_start + w_dur) < total:
        total = w_start + w_dur
    if total <= 0:
        total = w_dur
    width = int(_f(probe, "width", "w", default=1280) or 1280)
    height = int(_f(probe, "height", "h", default=720) or 720)
    fps = float(_f(probe, "fps", "r_frame_rate", default=30.0) or 30.0)

    raw_sent = _f(report, "sentences", default=[]) or []
    if args.segs:
        subs = load_segs(Path(args.segs))
    else:
        subs = norm_sentences(raw_sent)
    subs = [s for s in subs if s["e"] <= total + 0.5] or subs

    shots = _f(report, "shots", default=[]) or []
    layouts = _f(report, "layouts", default=[]) or []
    screens = merge_shots(shots, layouts)

    # 屏补齐：首屏从 0 开始，末屏到片尾
    if screens:
        screens[0]["s"] = 0.0
        for k in range(len(screens) - 1):
            screens[k]["e"] = min(max(screens[k]["e"], screens[k]["s"] + 0.3), screens[k + 1]["s"])
            screens[k + 1]["s"] = screens[k]["e"]
        screens[-1]["e"] = total
    else:
        screens = [{"idx": 0, "s": 0.0, "e": total, "mode": "scene", "shots": []}]

    lay_by_screen = {}
    for lay in layouts or []:
        lay_by_screen[int(_f(lay, "shot", "index", default=-1))] = lay

    scenes = []
    for sc in screens:
        lay = lay_by_screen.get(sc["shots"][0] if sc["shots"] else -1) or {}
        scenes.append(
            {
                "idx": sc["idx"],
                "s": _r(sc["s"]),
                "e": _r(sc["e"]),
                "dur": _r(max(0.0, sc["e"] - sc["s"])),
                "mode": sc["mode"],
                "shots": sc["shots"],
                "prompt": scene_prompt(sc["mode"], lay, sc["idx"]),
                "layout": {
                    "bright": _r(_f(lay, "bright", default=0.0), 1),
                    "contrast": _r(_f(lay, "contrast", default=0.0), 1),
                    "has_subtitle": bool(_f(lay, "has_subtitle", default=False)),
                    "sub_density": _r(_f(lay, "sub_density", default=0.0), 4),
                },
                # jy_from_spec 契约：assets[].{slot,file}；画面层后续填充
                "assets": [],
            }
        )

    # 字幕：句 → 字幕段，超长句按标点/字数二次切
    srt = []
    for s in subs:
        srt.extend(_split_sub(s, width_chars=args.sub_chars))

    chars = sum(len(s["text"]) for s in srt)
    speech = sum(s["e"] - s["s"] for s in srt) or 1.0
    voice_ref = pick_voice_ref(subs, _f(report, "silences", default=[]) or [], total)

    mode_count = {}
    for sc in scenes:
        mode_count[sc["mode"]] = mode_count.get(sc["mode"], 0) + 1

    return {
        "meta": {
            "schema": "replica.spec/1",
            "source": str(video),
            "name": video.stem,
            "duration": _r(total),
            "src_duration": _r(total),
            "target_duration": _r(total),
            "width": width,
            "height": height,
            "w": width,
            "h": height,
            "fps": _r(fps),
            "lang": "zh",
            "extractor": {"tool": "tools/replica_extract.py", "version": VERSION},
            "counts": {
                "subs": len(srt),
                "scenes": len(scenes),
                "shots": len(shots),
                "sections": 0,
                "chars": chars,
            },
            "speech": {
                "chars": chars,
                "speech_sec": _r(speech),
                "cps": _r(chars / speech if speech else 0.0),
                "chars_per_total_sec": _r(chars / total if total else 0.0),
            },
            "modes": mode_count,
        },
        "voice": {
            "provider": "dashscope",
            "mode": "clone",
            "ref_audio": "auto",
            "ref_window": voice_ref,
            "rate": 1.0,
            "sample_rate": 24000,
            "status": "pending",
        },
        "subs": srt,
        "sections": infer_sections(srt, total),
        "scenes": scenes,
        "jianying": {"status": "pending", "draft": ""},
        "acceptance": {
            "duration_tol": 0.02,
            "subtitle_cover": 1.0,
            "layout_align": 0.80,
            "audio_sync": True,
        },
        "provenance": {
            "extractor": f"replica_extract {VERSION}",
            "built_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "asr": asr_note or ("reused:--segs" if args.segs else f"faster-whisper/{args.model}"),
            "layout_sampled": not args.no_layout,
            "note": "事实层自动生成；prompt 为占位，需语义层覆盖",
        },
    }


def _split_sub(seg: dict, width_chars: int = 18) -> list[dict]:
    """长句按标点切成字幕段，时间按字数比例分配。"""
    text = seg["text"]
    if len(text) <= width_chars:
        return [{"s": seg["s"], "e": seg["e"], "text": text}]
    parts = re.split(r"(?<=[，。！？、；,.!?;])", text)
    parts = [p for p in (x.strip() for x in parts) if p]
    if len(parts) <= 1:
        parts = [text[i:i + width_chars] for i in range(0, len(text), width_chars)]
    total_chars = sum(len(p) for p in parts) or 1
    span = seg["e"] - seg["s"]
    out, t = [], seg["s"]
    for p in parts:
        d = span * len(p) / total_chars
        out.append({"s": _r(t), "e": _r(min(seg["e"], t + d)), "text": p})
        t += d
    return out


# ---------------------------------------------------------------- 主流程
def main() -> None:
    ap = argparse.ArgumentParser(description="任意动画式参考片 → spec.json")
    ap.add_argument("video")
    ap.add_argument("-o", "--out", default="")
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--dur", type=float, default=0.0)
    ap.add_argument("--model", default="small")
    ap.add_argument("--segs", default="", help="复用已有 ASR segs.json")
    ap.add_argument("--no-layout", action="store_true")
    ap.add_argument("--sub-chars", type=int, default=24, help="单条字幕最长字数，超过才二次切")
    ap.add_argument("--refresh", action="store_true", help="忽略 facts.json 缓存，重跑事实层")
    args = ap.parse_args()

    video = Path(args.video).expanduser().resolve()
    if not video.is_file():
        sys.exit(f"[extract] 找不到视频：{video}")

    name = _safe_name(video)
    outdir = _HERE.parent.parent / "qa2" / "refanalysis" / name
    outdir.mkdir(parents=True, exist_ok=True)
    out = Path(args.out).expanduser() if args.out else (outdir / f"{name}.spec.json")

    t0 = time.time()
    print(f"[extract] {video.name} → {out}")
    cache = outdir / "facts.json"
    if cache.is_file() and not args.refresh:
        print(f"[extract] 复用事实缓存 {cache.name}（--refresh 可重跑）")
        report = json.loads(cache.read_text(encoding="utf-8"))
        asr_note = "cached"
    else:
        report, asr_note = collect_facts(
            video, args.start, args.dur, args.model, not args.no_layout, not bool(args.segs)
        )
        try:
            cache.write_text(
                json.dumps(dataclasses.asdict(report), ensure_ascii=False), encoding="utf-8"
            )
        except Exception as exc:  # 缓存失败不影响主流程
            print(f"[extract] 事实缓存未写：{exc}")
    spec = build_spec(video, report, args, asr_note)
    spec["meta"]["elapsed_sec"] = _r(time.time() - t0, 1)

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")

    m = spec["meta"]
    c = m["counts"]
    print(f"[extract] 时长 {m['duration']}s / {m['width']}x{m['height']} / 字幕 {c['subs']} 段 / "
          f"屏 {c['scenes']} / 章 {len(spec['sections'])} / cps {m['speech']['cps']}")
    print(f"[extract] 版式分布 {m['modes']}")
    print(f"[extract] 克隆参考段 {spec['voice']['ref_window']}")
    print(f"[extract] 写出 {out}（{out.stat().st_size} 字节）")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception:
        traceback.print_exc()
        sys.exit(1)
