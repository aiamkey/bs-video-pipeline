r"""给「自动播放 PPT」配一轨克隆旁白，再合成带声音的视频。

三步串起来：
1. 按每页 advTm 算出时间轴，造一份只有 20 条字幕的 spec
2. replica_voice.py speak 用已建好的克隆音色逐条合成
3. replica_assemble.py 把 20 段铺回整条音轨 → ppt2video.py --voice

用法：
    python tools\ppt_narration.py                     # 合成旁白 + 出带声视频
    python tools\ppt_narration.py --only-voice        # 只合成音轨
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys

from pptx import Presentation
from pptx.oxml.ns import qn

ROOT = pathlib.Path(__file__).resolve().parent.parent
PPTX = ROOT / "deliver" / "七个信号-图文版.pptx"
SPEC = ROOT / "qa2" / "replica" / "out" / "ppt-voice.spec.json"
VOICE_JSON = ROOT / "qa2" / "replica" / "voice.json"
VOICE_DIR = ROOT / "qa2" / "replica" / "voice-out-ppt"
VOICE_WAV = ROOT / "qa2" / "replica" / "voice-ppt.wav"
TRANS = 0.5  # 与 ppt2video 默认转场一致

PY = sys.executable                                    # 读 pptx（本进程解释器）
VOICE_PY = r"C:\Users\张宇\AppData\Local\venv-clone\Scripts\python.exe"  # dashscope + requests
ASM_PY = r"E:\miniconda\envs\JupyterProject\python.exe"                  # imageio-ffmpeg + numpy

# 每页一句旁白（口语，比副文长一点，念出来正好卡满一页）
NARRATION: list[str] = [
    "看似拒绝，其实是偷偷喜欢你。七个信号，中了四个以上，就别再犹豫了。",
    "她可能也在偷偷喜欢你，只是她的表达方式，你还没读懂。",
    "第一，她愿意积极回应。每次都回得很认真，不敷衍，不冷场。",
    "第二，她不排斥你靠近。你走近一点，她没有下意识地退开。",
    "第三，她会对你发脾气。脾气是在意，不在意的人只会客气。",
    "第四，她愿意麻烦你。什么都不会，什么都想让你帮一把。",
    "第五，见你之前会用心打扮。穿得漂漂亮亮，是有备而来。",
    "第六，她愿意跟你讲道理。还愿意争，说明她还想要这段关系。",
    "第七，她会做一些小测试。杯子测试，就看她是挪近，还是挪远。",
    "看懂信号，不等于会接话。你缺的不是眼睛，是接得住的那句话。",
    "大大方方的是友情，小心翼翼的，才是爱情。",
    "信号要分级回应。回复积极但不主动，和主动找你，接法完全不同。",
    "喜欢你是麻烦。但要先分清，她是依赖你，还是只想使唤你。",
    "她的克制是有来源的。从小的教育、性格习惯，还有外界的环境。",
    "她在试探你的价值。想知道你值不值得她继续投入感情。",
    "人的精力是有限的。她愿意把有限的分给你，本身就是一种态度。",
    "重点看她的态度反应。细节里藏着对一个人的重视程度。",
    "但别太过分。试探是为了靠近，不是为了把人推远。",
    "下一步怎么走。先接住信号，再给一个明确的、不油腻的回应。",
    "别再让喜欢的人等太久。她已经在很小心地靠近你了。",
]


def page_durations() -> list[float]:
    prs = Presentation(str(PPTX))
    out = []
    for s in prs.slides:
        tr = s._element.find(qn("p:transition"))
        adv = tr.get("advTm") if tr is not None else None
        out.append(int(adv) / 1000.0 if adv else 3.0)
    return out


def make_spec() -> pathlib.Path:
    durs = page_durations()
    if len(durs) != len(NARRATION):
        raise SystemExit(f"[nar] 页数 {len(durs)} 与旁白条数 {len(NARRATION)} 不一致")

    subs = []
    start = 0.0
    for i, (d, text) in enumerate(zip(durs, NARRATION)):
        # 旁白在页内留 0.35s 起步、0.35s 收尾，给转场留余量
        s = max(0.0, start + 0.35)
        e = start + d - 0.35
        subs.append({"s": round(s, 3), "e": round(e, 3), "text": text})
        start = start + d - TRANS  # 下一开口（xfade 重叠）

    spec = {
        "meta": {
            "source": "七个信号-图文版.pptx",
            "duration": round(start + durs[-1] - (durs[-1] - TRANS), 3),
            "width": 1280,
            "height": 720,
            "w": 1280,
            "h": 720,
            "fps": 30,
        },
        "voice": {"provider": "dashscope", "rate": 1.0},
        "subs": subs,
        "scenes": [
            {"s": x["s"], "e": x["e"], "mode": "title", "assets": []} for x in subs
        ],
    }
    spec["meta"]["duration"] = round(subs[-1]["e"] + 0.35, 3)
    SPEC.parent.mkdir(parents=True, exist_ok=True)
    SPEC.write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[nar] spec {SPEC.name}  条数 {len(subs)}  末句 {subs[-1]['e']:.2f}s")
    return SPEC


def run(cmd: list[str], title: str) -> None:
    print(f"[nar] {title} …")
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        sys.stderr.write(r.stdout[-800:] + "\n" + r.stderr[-1200:] + "\n")
        raise SystemExit(f"[nar] {title} 失败")
    tail = (r.stdout or "").strip().splitlines()[-3:]
    for line in tail:
        print("   ", line)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only-voice", action="store_true", help="只合成音轨，不出视频")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    spec = make_spec()

    speak = [
        VOICE_PY, str(ROOT / "tools" / "replica_voice.py"), "speak",
        str(spec), str(VOICE_DIR),
    ]
    if a.limit:
        speak += ["--limit", str(a.limit)]
    run(speak, "逐条合成克隆旁白")

    run(
        [
            ASM_PY, str(ROOT / "tools" / "replica_assemble.py"),
            "--spec", str(spec),
            "--voice-dir", str(VOICE_DIR),
            "-o", str(VOICE_WAV),
            "--fit", "tempo",
        ],
        "铺回整条音轨",
    )

    if a.only_voice:
        print(f"[nar] 音轨 {VOICE_WAV}")
        return

    run(
        [
            PY, str(ROOT / "tools" / "ppt2video.py"),
            "--voice", str(VOICE_WAV),
        ],
        "合成带声音的视频",
    )
    print("[nar] 全部完成")


if __name__ == "__main__":
    main()
