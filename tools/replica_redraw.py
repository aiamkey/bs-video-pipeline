# -*- coding: utf-8 -*-
"""复刻的「画面重画」层：把每屏的代表帧换成自己生成的插画。

现状（不接这个脚本）：复刻出来的画面是**原片的代表帧**，结构对但画面是别人的。
接上这个脚本：每屏按台词语义生成一张同构插画，风格由 STYLE 统一，**画面里不写字**
（文字全部交给字幕轨），于是成片是「原片的结构 + 自己的画面 + 自己的配音」。

它只做一件事：**改 scenes[].assets[].file**。改完重跑 `replica.py jianying`，
剪映草稿就是重画版；原来的代表帧不删，`--revert` 可退回。

用法：
  python tools\\replica_redraw.py --spec X.spec.json --limit 6          # 小样 6 屏（先看质量再全量）
  python tools\\replica_redraw.py --spec X.spec.json --only 0,5,20      # 指定屏
  python tools\\replica_redraw.py --spec X.spec.json --apply            # 全量重画并写回 spec
  python tools\\replica_redraw.py --spec X.spec.json --revert           # 退回代表帧

出图走 tools/img.py（relay.json / 百炼 / ark 三通道都通），默认读 qa2/gpt/relay.json。
**这一步会花钱**（每屏一张图），所以默认不 --apply：先出图、你看过再写回。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve()
sys.path.insert(0, str(_HERE.parent))
import img as IMG  # noqa: E402


# 全局风格：所有屏共用，保证成片不像拼贴
STYLE = (
    "极简扁平矢量插画，暖米白背景，珊瑚橙 + 墨绿 + 暖灰三色点缀，"
    "粗线条几何形状，大量留白，构图简洁有呼吸感，16:9 横版，"
    "画面里绝对不要出现任何文字、字母、数字、标点、对话框里的字或字幕条"
)

# 按屏型给不同的画面意图
BY_MODE = {
    "scene": "用一个具体的日常场景表现「{sem}」这个概念，只画一个主体加少量陪体，不要人脸大特写",
    "title": "用一个强对比的符号化图形表现「{sem}」，大面积色块，适合做章节封面",
    "chat": "表现两个人之间对话的场景（手机或两个人物剪影对望都行），气泡里留空不写字",
    "doc": "表现一份清单或文档的示意，用横线代替文字行，略带俯视角度",
}


def build_prompt(mode: str, sem: str, style: str) -> str:
    body = BY_MODE.get(mode, BY_MODE["scene"]).format(sem=sem or "一个日常片段")
    return f"{body}。风格：{style}"


def screen_texts(sc: dict, subs: list[dict]) -> str:
    """该屏覆盖的字幕拼起来，截断成一句适合当画面主题的话。"""
    inside = [t for t in subs
              if t["s"] >= sc["s"] - 0.01 and t["e"] <= sc["e"] + 0.01]
    if not inside:
        return ""
    text = "，".join(t["text"].strip() for t in inside if t.get("text"))
    return text[:60]


def main() -> int:
    ap = argparse.ArgumentParser(description="复刻：每屏按台词语义重画一张插画")
    ap.add_argument("--spec", required=True)
    ap.add_argument("--only", default="", help="只画这些屏，逗号分隔的 idx（如 0,5,20）")
    ap.add_argument("--limit", type=int, default=0, help="只画前 N 屏（小样用）")
    ap.add_argument("--apply", action="store_true", help="写回 spec（不写就只出图）")
    ap.add_argument("--revert", action="store_true", help="退回原代表帧")
    ap.add_argument("--outdir", default="", help="图放哪；默认 assets/<spec 名>/redraw")
    ap.add_argument("--style", default=STYLE)
    ap.add_argument("--relay", default="", help="覆盖 relay.json 路径")
    ap.add_argument("--sleep", type=float, default=0.5, help="每张之间歇一下（防限流）")
    a = ap.parse_args()

    sp = Path(a.spec).resolve()
    spec = json.loads(sp.read_text(encoding="utf-8"))
    scenes = spec.get("scenes") or []
    subs = spec.get("subs") or []
    if not scenes:
        sys.exit("[redraw] spec 里没有 scenes")

    if a.revert:
        n = 0
        for sc in scenes:
            for it in sc.get("assets") or []:
                if it.get("status") == "redraw":
                    old = it.get("from") or ""
                    if old:
                        it["file"] = old
                        it["status"] = "ready"
                        n += 1
        sp.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[redraw] 退回 {n} 屏代表帧 → {sp}")
        return 0

    stem = sp.name[: -len(".spec.json")] if sp.name.endswith(".spec.json") else sp.stem
    adir = Path(a.outdir).resolve() if a.outdir else (sp.parent / "assets" / stem / "redraw")
    adir.mkdir(parents=True, exist_ok=True)

    if a.relay:
        IMG.RELAY_PATH = Path(a.relay).resolve()
    cfg = IMG.load_cfg()
    key = IMG.resolve_key(cfg, None)
    model = cfg.get("model") or ""
    size = cfg.get("size") or ""
    print(f"[redraw] 通道 {cfg.get('provider')} / model={model} / size={size} / 目标 {adir}")

    want = [s for s in scenes]
    if a.only.strip():
        keep = {int(x) for x in a.only.replace(" ", "").split(",") if x}
        want = [s for s in scenes if int(s.get("idx", 0)) in keep]
    elif a.limit:
        want = want[: a.limit]

    ok, fail = 0, []
    for n, sc in enumerate(want, 1):
        idx = int(sc.get("idx", 0))
        mode = sc.get("mode") or "scene"
        sem = screen_texts(sc, subs)
        prompt = build_prompt(mode, sem, a.style)
        out = adir / f"p{idx:03d}.jpg"
        print(f"[redraw] {n}/{len(want)} p{idx:03d} [{mode}] {sem[:32]}")
        got = ""
        for attempt in (1, 2):
            try:
                got = IMG.gen_openai(prompt, out, cfg, key, model, size)
                break
            except Exception as e:  # noqa: BLE001
                print(f"          第 {attempt} 次失败：{type(e).__name__}: {e}")
                time.sleep(2.0 * attempt)
        if got and out.exists():
            ok += 1
            if a.apply:
                try:
                    rel = out.relative_to(sp.parent).as_posix()
                except ValueError:
                    rel = out.as_posix()
                prev = (sc.get("assets") or [{}])[0]
                sc["assets"] = [{
                    "slot": prev.get("slot", "bg"),
                    "file": rel,
                    "status": "redraw",
                    "from": prev.get("file", ""),
                    "prompt": prompt,
                    "t": prev.get("t"),
                }]
                if ok % 10 == 0:      # 增量存盘：全量 100+ 屏要跑很久，中断不丢进度
                    sp.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
                    print(f"[redraw]   ↳ 已存盘（{ok} 屏）")
        else:
            fail.append(idx)
        time.sleep(max(0.0, a.sleep))

    if a.apply:
        sp.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[redraw] 已写回 spec：{sp}")
    print(f"[redraw] 成功 {ok}/{len(want)}" + (f"  失败 {fail}" if fail else ""))
    if not a.apply:
        print("[redraw] 未写回（看满意后加 --apply，或 --only 精修几屏）")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
