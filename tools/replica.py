"""replica 编排器（P0 骨架）——「给一个动画式视频 → 交付 MP4 + 剪映可编辑工程」。

定稿见 qa2/replica/需求规格-定稿.md。P0 只做**不联网、不花钱**的合流部分：
把已有的三种输入统一成唯一一份 spec.json，校验，再转成剪映轨道 spec。

  normalize  q6.json / film.json / 手工 spec → 通用 spec.json（MP4 与剪映共用）
  validate   按 80% 验收口径体检 spec（时长/字幕覆盖/分段/scene 连续性）
  jianying   spec → 剪映草稿（转调 jy_from_spec.py，--dry 不建草稿）
  verify     交付目录体检（MP4 / 草稿 / assets / REPORT 是否齐）
  all        normalize → validate → jianying（默认 dry，纯本地）

联网/花钱段（GPT image 生成、声音克隆、Remotion 渲 MP4）是 P1/P2，
按定稿 §5 增量后接入；本骨架把它们留成明确的 stub，不假装跑过。

用法：
  python tools/replica.py normalize --in lbr-promo/src/data/q6.json --out qa2/replica/out/q6.spec.json
  python tools/replica.py all --in lbr-promo/src/data/q6.json --out qa2/replica/out/q6.spec.json
  python tools/replica.py validate --spec qa2/replica/out/q6.spec.json
  python tools/replica.py jianying --spec qa2/replica/out/q6.spec.json --dry
  python tools/replica.py verify --dir deliver/六问复刻版
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
VIDEO = HERE.parent
REPLICA = VIDEO / "qa2" / "replica"
SCHEMA = REPLICA / "spec.schema.json"
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

PY = sys.executable

# 六问片实测版式几何（qa2/ref/ANALYSIS.md），normalize 时作 layout 默认值
Q6_LAYOUT = {"col": [365, 917], "nav_y": 676, "sub_y": 640,
             "badge": [4, 4, 349, 119], "bg": "rgb(213,213,213)"}


def f(v, default=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _sections_q6(rows, total):
    out = []
    for i, r in enumerate(rows or []):
        s = f(r.get("start"))
        e = f(rows[i + 1].get("start")) if i + 1 < len(rows) else total
        out.append({"id": f"s{i}", "label": r.get("label") or f"段{i}",
                    "s": s, "e": e, "role": r.get("label") or ""})
    return out


def _sections_film(rows, total):
    out = []
    for i, r in enumerate(rows or []):
        s = f(r.get("start"))
        e = f(r.get("end")) or (f(rows[i + 1].get("start")) if i + 1 < len(rows) else total)
        out.append({"id": f"s{i}", "label": r.get("label") or f"段{i}",
                    "s": s, "e": e, "role": r.get("label") or ""})
    return out


def _asset(slot, prompt, idx, ext="png"):
    return {"slot": slot, "prompt": prompt, "provider": "gpt-image",
            "file": f"assets/{idx:03d}_{slot}.{ext}"}


def _fill_scene_gaps(scenes: list, total: float, max_gap: float = 1.0):
    """让 scenes 连续铺满 [0,total]：裁重叠、吃 <=max_gap 小缝、首尾对齐。

    film.json 的 panels 只覆盖有底板的屏，卡片静帧句（copy/section/board）不进
    panels —— normalize 会把它们补成 mode=card 的 scene，再由这里压平边界。
    对齐 jy_from_film._fill_gaps 的语义，避免剪映里黑闪。
    """
    if not scenes:
        return scenes
    scenes.sort(key=lambda x: f(x.get("s")))
    for i, sc in enumerate(scenes[:-1]):
        e1, s2 = f(sc["e"]), f(scenes[i + 1]["s"])
        if s2 < e1:                       # 重叠：裁前屏
            sc["e"] = round(s2, 3)
        elif s2 - e1 <= max_gap:          # 小空档：前屏延长
            sc["e"] = round(s2, 3)
    scenes[0]["s"] = 0.0
    scenes[-1]["e"] = round(total, 3)
    return scenes


def from_q6(d: dict, src: pathlib.Path) -> dict:
    """q6.json（total/sections/scenes/subs）→ 通用 spec。"""
    total = f(d.get("total"))
    scenes = []
    for i, sc in enumerate(d.get("scenes") or []):
        mode = sc.get("mode") or "scene"
        assets = []
        bg = sc.get("bg")
        if bg:
            assets.append(_asset("bg", f"扁平矢量卡通插画，场景：{bg}；角色：{sc.get('chars') or '无'}；"
                                       f"画面右侧留白，低饱和暖色调，无文字", i))
        scenes.append({
            "s": f(sc.get("s")), "e": f(sc.get("e")),
            "mode": mode,
            "layout": dict(Q6_LAYOUT),
            "assets": assets,
            "graphics": ["badge", "nav", "sub"],
            "head": sc.get("head") or "", "kicker": sc.get("kicker") or "",
            "bullets": sc.get("bullets") or [], "msgs": sc.get("msgs") or [],
        })
    subs = [{"s": f(x.get("s")), "e": f(x.get("e")), "text": x.get("text") or "",
             "style": "white-black-stroke"} for x in d.get("subs") or []]
    return {
        "meta": {"src": str(src), "name": "六问复刻版",
                 "src_duration": total, "target_duration": total,
                 "tolerance": "max(2%, 5s)", "fps": 30, "w": 1280, "h": 720,
                 "kind": "animated", "deliver_dir": "deliver/六问复刻版",
                 "bg": "rgb(213,213,213)"},
        "voice": {"provider": "jcaigc", "clone_model": "cosyvoice-v3.5-plus",
                  "speak_model": "cosyvoice-v3.5-plus", "voice_id": "",
                  "ref_audio": "auto", "rate": 1.08, "segments": []},
        "subs": subs, "sections": _sections_q6(d.get("sections"), total),
        "scenes": scenes,
        "jianying": {"tracks": ["video", "text", "audio", "sticker"],
                     "draft_root": "auto", "localize": True},
        "acceptance": {"duration_diff": "<=2%", "sub_cover": "100%",
                       "layout_align": ">=80%", "sections_align": True,
                       "audio_align": True},
        "provenance": {"from": "q6.json", "source_file": str(src),
                       "notes": "normalize 自动合流；assets 为 GPT image 占位，未生成"},
    }


def from_film(d: dict, src: pathlib.Path) -> dict:
    """film.json（title/fps/voice/totalSeconds/sections/lines/panels）→ 通用 spec。"""
    total = f(d.get("totalSeconds"))
    scenes = []
    for i, p in enumerate(d.get("panels") or []):
        assets = []
        if p.get("bg"):
            assets.append(_asset("bg", f"扁平矢量卡通插画，场景底板：{p.get('bg')}；"
                                       f"右侧留白供后期叠字，无文字", i, "jpg"))
        if p.get("photo"):
            assets.append(_asset("photo", f"真人底图/卡通人物：{p.get('photo')}；"
                                          f"text_zone={p.get('text_zone') or 'right'}", i, "jpg"))
        els = p.get("elements") or []
        bullets = [str(e.get("text")) for e in els if e.get("text")]
        scenes.append({
            "s": f(p.get("start")), "e": f(p.get("end")), "mode": "panel",
            "layout": {"bg": "#F6F4EF"},
            "assets": assets, "graphics": ["label", "bubble", "num"],
            "head": "", "kicker": "", "bullets": bullets, "msgs": [],
        })
    # 卡片静帧句：film.json 里 panel=None 的 line 不进 panels，却占着时间轴。
    # jy_from_film.py 用 tools/jy_cards.py 抽成静帧；这里补成 mode=card 的 scene，
    # 让 scenes 覆盖全片（通用 spec 要求连续铺满，不再有「只认 panel」的黑场段）。
    for i, ln in enumerate(d.get("lines") or []):
        if ln.get("panel"):
            continue
        card = ln.get("card") or {}
        scenes.append({
            "s": f(ln.get("start")), "e": f(ln.get("end")), "mode": "card",
            "layout": {"bg": "#F6F4EF"},
            "assets": [_asset("card", f"大字卡静帧：{card.get('text') or ln.get('text') or ''}；"
                                       f"扁平矢量，低饱和暖色，文字后期代码层叠", i, "png")],
            "graphics": ["card", "sub"],
            "head": str(card.get("text") or ln.get("text") or ""),
            "kicker": "", "bullets": [], "msgs": [],
        })
    _fill_scene_gaps(scenes, total)

    subs = []
    for ln in d.get("lines") or []:
        subs.append({"s": f(ln.get("start")), "e": f(ln.get("end")),
                     "text": ln.get("text") or "", "style": "white-black-stroke",
                     "sub": ln.get("sub") is not False})
    voice_file = d.get("voice") or ""
    return {
        "meta": {"src": str(src), "name": d.get("title") or "EP02",
                 "src_duration": total, "target_duration": total,
                 "tolerance": "max(2%, 5s)", "fps": int(d.get("fps") or 30),
                 "w": 1280, "h": 720, "kind": "animated",
                 "deliver_dir": f"deliver/{d.get('title') or 'EP02'}", "bg": "#F6F4EF"},
        "voice": {"provider": "jcaigc", "clone_model": "cosyvoice-v3.5-plus",
                  "speak_model": "cosyvoice-v3.5-plus", "voice_id": "",
                  "ref_audio": "auto", "rate": 1.08,
                  "wav": voice_file, "segments": []},
        "subs": subs, "sections": _sections_film(d.get("sections"), total),
        "scenes": scenes,
        "jianying": {"tracks": ["video", "text", "audio", "sticker"],
                     "draft_root": "auto", "localize": True},
        "acceptance": {"duration_diff": "<=2%", "sub_cover": "100%",
                       "layout_align": ">=80%", "sections_align": True,
                       "audio_align": True},
        "provenance": {"from": "film.json", "source_file": str(src),
                       "notes": "normalize 自动合流；voice.wav 沿用原 film.json，克隆产物待替换"},
    }


def detect(d: dict) -> str:
    keys = set(d.keys())
    if {"meta", "scenes", "subs"} <= keys:
        return "spec"
    if {"total", "scenes", "subs"} <= keys:
        return "q6"
    if {"totalSeconds", "lines", "panels"} <= keys:
        return "film"
    return "unknown"


def _sh(py, script, args):
    cmd = [py, str(script)] + [str(x) for x in args]
    print("[auto] " + " ".join(cmd[1:]))
    return subprocess.call(cmd)


def cmd_auto(a):
    """一条命令跑完：抽结构 → 抽每屏代表帧 → 出剪映草稿。

    这是「换片就能复刻」的入口：换第一个参数即可，不花钱、不联网。
    画面是原片代表帧、配音是原片音轨；要「重画 + 克隆」版本时，替换
    spec 的 assets[].file 与 voice.wav 后重跑 jianying，下游不用改。
    """
    here = pathlib.Path(__file__).resolve().parent
    py = a.python or sys.executable
    stem = pathlib.Path(a.video).stem
    spec = pathlib.Path(a.out) if a.out else (REPLICA / "out" / f"{stem}.spec.json")

    ex = ["--out", str(spec)]
    for flag, val in (("--start", a.start), ("--dur", a.dur), ("--model", a.model), ("--segs", a.segs)):
        if val:
            ex += [flag, val]
    if a.refresh:
        ex.append("--refresh")
    rc = _sh(py, here / "replica_extract.py", [a.video] + ex)
    if rc:
        return rc

    rc = _sh(py, here / "replica_shots.py", ["--spec", str(spec)])
    if rc:
        return rc

    if a.no_jianying:
        print("[auto] 跳过剪映草稿（--no-jianying）")
        return 0
    name = a.name or f"{spec.stem.replace('.spec', '')}_自动复刻"
    return _sh(py, here / "replica.py", ["jianying", "--spec", str(spec), "--name", name])


def cmd_extract(a):
    """任意动画式参考片 → spec.json（转调 replica_extract.py）。

    换片就换第一个参数，不用改代码；没有 faster_whisper 的解释器会自动
    降级为「无转写模式」，此时用 --segs 补字幕或用 --python 指到装了
    faster-whisper 的解释器。
    """
    here = pathlib.Path(__file__).resolve().parent
    script = here / "replica_extract.py"
    py = a.python or sys.executable
    cmd = [py, str(script), str(a.video)]
    if a.out:
        cmd += ["-o", a.out]
    if a.start:
        cmd += ["--start", str(a.start)]
    if a.dur:
        cmd += ["--dur", str(a.dur)]
    if a.model:
        cmd += ["--model", a.model]
    if a.segs:
        cmd += ["--segs", a.segs]
    if a.no_layout:
        cmd += ["--no-layout"]
    if a.sub_chars:
        cmd += ["--sub-chars", str(a.sub_chars)]
    if a.refresh:
        cmd += ["--refresh"]
    print(f"[extract] {py}")
    return subprocess.call(cmd)


def cmd_normalize(a):
    src = pathlib.Path(a.input).resolve()
    d = json.loads(src.read_text(encoding="utf-8"))
    kind = detect(d)
    if kind == "q6":
        spec = from_q6(d, src)
    elif kind == "film":
        spec = from_film(d, src)
    elif kind == "spec":
        spec = d
        spec.setdefault("provenance", {})["from"] = "pass-through"
    else:
        raise SystemExit(f"不认识的输入结构 keys={sorted(d.keys())}；"
                         f"支持 q6.json / film.json / 通用 spec.json")
    out = pathlib.Path(a.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[normalize] {kind} → {out}")
    print(f"  meta.duration={spec['meta'].get('target_duration')}s  "
          f"subs={len(spec.get('subs') or [])}  sections={len(spec.get('sections') or [])}  "
          f"scenes={len(spec.get('scenes') or [])}")
    n_assets = sum(len(sc.get("assets") or []) for sc in spec.get("scenes") or [])
    print(f"  assets 占位={n_assets}（GPT image 待生成，P2）  voice.wav="
          f"{(spec.get('voice') or {}).get('wav') or '未填（克隆待跑）'}")
    return 0


def cmd_validate(a):
    spec = json.loads(pathlib.Path(a.spec).read_text(encoding="utf-8"))
    meta, subs, scenes = spec.get("meta") or {}, spec.get("subs") or [], spec.get("scenes") or []
    total = f(meta.get("target_duration") or meta.get("src_duration"))
    problems, warns = [], []

    # 时长
    last = max((f(x.get("e")) for x in subs), default=0.0)
    diff = abs(last - total)
    tol = max(0.02 * total, 5.0)
    print(f"[validate] 时长: target={total:.2f}s  last_sub_e={last:.2f}s  diff={diff:.2f}s  tol={tol:.2f}s")
    if diff > tol:
        problems.append(f"时长差 {diff:.2f}s 超容差 {tol:.2f}s")

    # 字幕覆盖：空 / 越界 / 重叠 / 大空档
    empty = [i for i, x in enumerate(subs) if not (x.get("text") or "").strip()]
    oor = [i for i, x in enumerate(subs) if f(x.get("s")) < 0 or f(x.get("e")) > total + tol]
    overlaps, gaps = [], []
    srt = sorted(((f(x.get("s")), f(x.get("e")), i) for i, x in enumerate(subs)))
    for (s1, e1, i1), (s2, e2, i2) in zip(srt, srt[1:]):
        if s2 < e1 - 1e-6:
            overlaps.append((i1, i2, round(e1 - s2, 3)))
        if s2 - e1 > 2.0:
            gaps.append((round(e1, 2), round(s2, 2), round(s2 - e1, 2)))
    print(f"[validate] 字幕: {len(subs)} 段  empty={len(empty)}  out_of_range={len(oor)}  "
          f"overlaps={len(overlaps)}  gaps>2s={len(gaps)}")
    if empty:
        problems.append(f"{len(empty)} 段空字幕")
    if oor:
        problems.append(f"{len(oor)} 段越界")
    if overlaps:
        problems.append(f"{len(overlaps)} 处重叠")
    if gaps:
        warns.append(f"{len(gaps)} 处 >2s 空档（可能是刻意停顿）: {gaps[:3]}")

    # scene 连续性
    ssrt = sorted(((f(x.get("s")), f(x.get("e"))) for x in scenes))
    sgaps = [(round(e1, 2), round(s2, 2)) for (s1, e1), (s2, e2) in zip(ssrt, ssrt[1:])
             if abs(s2 - e1) > 1e-3]
    print(f"[validate] scenes: {len(scenes)} 屏  continuity_gaps={len(sgaps)}")
    if sgaps:
        problems.append(f"{len(sgaps)} 处 scene 不连续: {sgaps[:3]}")

    # 结构
    for k in ("meta", "subs", "scenes"):
        if k not in spec:
            problems.append(f"缺字段 {k}")
    if not SCHEMA.exists():
        warns.append(f"schema 文件不在 {SCHEMA}（不阻塞）")

    # 待接入项（如实标注，不假装完成）
    n_assets = sum(len(sc.get("assets") or []) for sc in scenes)
    exts_missing = sum(1 for sc in scenes for x in sc.get("assets") or []
                       if not (pathlib.Path(a.spec).parent / x.get("file", "")).exists())
    voice = spec.get("voice") or {}
    print(f"[validate] 待接入 stub: GPT 素材 {n_assets} 个（本地缺 {exts_missing}）· "
          f"克隆配音 {'缺' if not voice.get('wav') else '有'} · Remotion MP4 未渲（P1/P2）")

    for w in warns:
        print(f"  WARN  {w}")
    if problems:
        print("[validate] FAIL:")
        for p in problems:
            print("   -", p)
        return 1
    print("[validate] PASS（本地可判项全绿；联网段待 key）")
    return 0


def cmd_jianying(a):
    args = [PY, str(HERE / "jy_from_spec.py"), "--spec", str(pathlib.Path(a.spec).resolve())]
    if a.name:
        args += ["--name", a.name]
    if a.dry:
        args += ["--dry-run"]
    if a.spec_out:
        args += ["--spec-out", a.spec_out]
    return subprocess.call(args)


def cmd_verify(a):
    root = pathlib.Path(a.dir)
    checks = {
        "spec.json": root / "spec.json",
        "MP4": None, "剪映草稿": None, "REPORT.md": root / "REPORT.md",
        "assets/": root / "assets", "voice/": root / "voice",
    }
    mp4s = list(root.glob("*.mp4"))
    checks["MP4"] = mp4s[0] if mp4s else None
    drafts = [p for p in root.glob("*") if p.is_dir() and p.name not in ("assets", "voice")]
    if not mp4s:
        # 草稿可能不在 deliver 里，标为待查而非失败
        pass
    print(f"[verify] 交付目录 {root}  存在={root.exists()}")
    ok = True
    for k, p in checks.items():
        hit = bool(p and p.exists())
        if k in ("MP4", "剪映草稿", "REPORT.md", "spec.json"):
            ok = ok and hit
        print(f"  {'OK ' if hit else '-- '} {k:10s} {p or '(未找到)'}")
    print("[verify] " + ("PASS" if ok else "INCOMPLETE（P0 阶段预期：MP4/草稿/REPORT 由 P1/P3 补齐）"))
    return 0 if ok else 1


def cmd_all(a):
    print("[all] P0 本地链路：normalize → validate → jianying(dry)")
    if cmd_normalize(a):
        return 1
    a2 = argparse.Namespace(spec=a.out)
    rc = cmd_validate(a2)
    a3 = argparse.Namespace(spec=a.out, name=a.name, dry=True, spec_out=a.spec_out)
    jrc = cmd_jianying(a3)
    print("[all] 完成。联网/花钱段（GPT image / 声音克隆 / Remotion 渲 MP4 / 真建草稿）"
          "按定稿 §5 的 P1/P2/P3 接入，本骨架未执行。")
    return rc or jrc


def main(argv):
    try:
        sys.stdout.reconfigure(line_buffering=True)  # 子进程输出不被父进程块缓冲打乱顺序
    except AttributeError:
        pass
    ap = argparse.ArgumentParser(prog="replica.py")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("auto", help="一条命令：抽结构 → 抽帧 → 剪映草稿")
    p.add_argument("video", help="任意动画式参考片 mp4")
    p.add_argument("-o", "--out", default="")
    p.add_argument("--start", type=float, default=0.0)
    p.add_argument("--dur", type=float, default=0.0)
    p.add_argument("--model", default="")
    p.add_argument("--segs", default="")
    p.add_argument("--name", default="")
    p.add_argument("--no-jianying", action="store_true")
    p.add_argument("--refresh", action="store_true")
    p.add_argument("--python", default="", help="跑子脚本的解释器（默认当前）")
    p.set_defaults(fn=cmd_auto)

    p = sub.add_parser("extract")
    p.add_argument("video", help="任意动画式参考片 mp4")
    p.add_argument("-o", "--out", default="")
    p.add_argument("--start", type=float, default=0.0)
    p.add_argument("--dur", type=float, default=0.0)
    p.add_argument("--model", default="", help="faster-whisper 模型，默认 small")
    p.add_argument("--segs", default="", help="复用已有 ASR segs.json，跳过转写")
    p.add_argument("--no-layout", action="store_true")
    p.add_argument("--sub-chars", type=int, default=24)
    p.add_argument("--refresh", action="store_true", help="忽略 facts.json 缓存")
    p.add_argument("--python", default="", help="跑 extract 的解释器（默认当前）")
    p.set_defaults(fn=cmd_extract)

    p = sub.add_parser("normalize")
    p.add_argument("--in", dest="input", required=True)
    p.add_argument("--out", default=str(REPLICA / "out" / "spec.json"))
    p.set_defaults(fn=cmd_normalize)

    p = sub.add_parser("validate")
    p.add_argument("--spec", required=True)
    p.set_defaults(fn=cmd_validate)

    p = sub.add_parser("jianying")
    p.add_argument("--spec", required=True)
    p.add_argument("--name", default="")
    p.add_argument("--dry", action="store_true")
    p.add_argument("--spec-out", default="")
    p.set_defaults(fn=cmd_jianying)

    p = sub.add_parser("verify")
    p.add_argument("--dir", required=True)
    p.set_defaults(fn=cmd_verify)

    p = sub.add_parser("all")
    p.add_argument("--in", dest="input", required=True)
    p.add_argument("--out", default=str(REPLICA / "out" / "spec.json"))
    p.add_argument("--name", default="")
    p.add_argument("--spec-out", default="")
    p.set_defaults(fn=cmd_all)

    a = ap.parse_args(argv[1:])
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
