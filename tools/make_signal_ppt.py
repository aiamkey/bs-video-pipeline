r"""把复刻出来的 163 张插画挑 20 张，做成带「闪光」切换动效的图文 PPT。

用法：
    python tools\make_signal_ppt.py            # 出 deliver\七个信号-图文版.pptx
    python tools\make_signal_ppt.py --open      # 出完直接打开

三个设计取舍：
1. 图 1672x941（1.7768）铺 13.333x7.5（1.7778），拉伸 0.06%，看不出来。
2. 遮罩用**渐变**不用纯色块：内页字压在底部，从 3.6in 起由透明过渡到 85% 黑；
   封面字压右侧，横向渐变。硬边色块会让画面像贴了条黑胶带。
3. 切换效果 python-pptx 写不了，直接往 slide XML 插 <p:transition>。
   PowerPoint 的「闪光」XML 是 <p:newsflash/>，本脚本一半页面用它，其余轮
   dissolve / zoom / fade / push / wipe / split / cover / uncover，速度全 fast。
"""
from __future__ import annotations

import argparse
import pathlib
import subprocess

from lxml import etree
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

ROOT = pathlib.Path(__file__).resolve().parent.parent
STEM = "看似拒绝实际上是女生偷偷喜欢你的七个信号"
IMG = ROOT / "qa2" / "replica" / "out" / "assets" / STEM / "redraw"
OUT = ROOT / "deliver" / "七个信号-图文版.pptx"

ORANGE = RGBColor(0xE8, 0x72, 0x2F)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
GREY = RGBColor(0xEC, 0xE6, 0xDA)

W, H = 13.333, 7.5

# (图号, 角标, 标题, 副文)
PAGES: list[tuple[int, str, str, str]] = [
    (0, "", "看似拒绝，其实是偷偷喜欢你", "7 个信号，中了 4 个以上就别再犹豫了"),
    (2, "开场", "她可能也在偷偷喜欢你", "只是她表达的方式，你还没读懂"),
    (24, "SIGNAL 01", "她愿意积极回应", "每次都回得很认真，不敷衍、不冷场"),
    (48, "SIGNAL 02", "她不排斥你靠近", "你走近一点，她没有下意识退开"),
    (92, "SIGNAL 03", "她会对你发脾气", "脾气是在意，不是讨厌——不在意的人只会客气"),
    (96, "SIGNAL 04", "她愿意麻烦你", "什么都「不会」，什么都想让你帮一把"),
    (112, "SIGNAL 05", "见你之前会用心打扮", "穿得漂漂亮亮，是有备而来"),
    (128, "SIGNAL 06", "她愿意跟你讲道理", "还愿意争，说明还想要这段关系"),
    (148, "SIGNAL 07", "她会做一些小测试", "杯子测试：看她是挪近，还是挪远"),
    (58, "转折", "看懂信号，不等于会接话", "你缺的不是眼睛，是接得住的那句话"),
    (75, "认知 01", "大大方方的是友情", "小心翼翼的，才是爱情"),
    (64, "认知 02", "信号要分级回应", "回复积极但不主动，和主动找你，接法完全不同"),
    (104, "认知 03", "喜欢你是麻烦", "但要先分清，是依赖你，还是只想使唤你"),
    (16, "认知 04", "她的克制有来源", "从小的教育、性格习惯、还有外界环境"),
    (32, "认知 05", "她在试探你的价值", "想知道你值不值得她继续投入感情"),
    (88, "认知 06", "人的精力是有限的", "她愿意把有限的分给你，本身就是态度"),
    (124, "认知 07", "重点看她的态度反应", "细节里藏着对一个人的重视程度"),
    (143, "提醒", "但别太过分", "试探是为了靠近，不是为了把人推远"),
    (152, "行动", "下一步怎么走", "先接住信号，再给一个明确的、不油腻的回应"),
    (160, "结尾", "别再让喜欢的人等太久", "她已经在很小心地靠近你了"),
]

# 「闪光」占一半，其余轮换，保证相邻两页几乎不重样
FLASH = [
    "newsflash", "dissolve", "newsflash", "zoom", "newsflash",
    "fade", "newsflash", "push", "newsflash", "wipe",
    "newsflash", "split", "newsflash", "cover", "newsflash",
    "uncover", "newsflash", "dissolve", "newsflash", "zoom",
]

# 纯图版（不要文字）用的**连贯**转场序列：方向感强、不留停顿
# push 连推 → 覆盖叠层 → 擦除 → 溶解 → 缩放收尾，全程 med 速度
FLOW = [
    "fade",         # 1 封面：淡入
    "push",         # 2 开场推进
    "push",         # 3 连推，像镜头往前
    "cover",        # 4 叠一层
    "push",         # 5
    "cover",        # 6
    "push",         # 7
    "wipe",         # 8 横向擦
    "push",         # 9
    "fade",         # 10 转折：断一下节奏
    "zoom",         # 11 拉近
    "cover",        # 12
    "push",         # 13
    "wipe",         # 14
    "cover",        # 15
    "zoom",         # 16
    "push",         # 17
    "dissolve",     # 18 提醒：柔化
    "zoom",         # 19 行动：推近
    "fade",         # 20 结尾：收
]

NS_P = "http://schemas.openxmlformats.org/presentationml/2006/main"
NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"


def set_transition(slide, kind: str, adv_ms: int = 0, speed: str = "fast") -> None:
    """插 <p:transition>，位置在 clrMapOvr 之后、timing 之前。

    adv_ms > 0 时写 advTm —— 这就是「自动换片」：放映到时间自动翻页，不用点。
    """
    sld = slide._element
    for old in sld.findall(qn("p:transition")):
        sld.remove(old)
    adv = f' advTm="{adv_ms}"' if adv_ms else ""
    el = etree.fromstring(
        f'<p:transition xmlns:p="{NS_P}" spd="{speed}"{adv}><p:{kind}/></p:transition>'
    )
    anchor = sld.find(qn("p:clrMapOvr"))
    if anchor is None:
        anchor = sld.find(qn("p:cSld"))
    anchor.addnext(el)


def page_seconds(title: str, sub: str) -> float:
    """一页停留多久：按字数估读完的时间，夹在 5–9 秒。"""
    n = len(title) + len(sub)
    return max(5.0, min(9.0, 4.0 + n * 0.08))


def enable_auto_show(prs) -> None:
    """presentation.xml 里开循环放映 + 用排练时间，配合每页 advTm 就是自动播放。"""
    root = prs.part._element
    for old in root.findall(qn("p:showPr")):
        root.remove(old)
    el = etree.fromstring(
        f'<p:showPr xmlns:p="{NS_P}" loop="1" showAnimation="1" showScrollbar="0">'
        f"<p:present/></p:showPr>"
    )
    # showPr 排在 notesSz 之后（schema 顺序），插在 defaultTextStyle 前最稳
    anchor = root.find(qn("p:defaultTextStyle"))
    if anchor is not None:
        anchor.addprevious(el)
    else:
        root.append(el)


def grad_rect(slide, x, y, w, h, stops, ang=5400000):
    """stops: [(pos 0-100, 'RRGGBB', alpha 0-100)]，ang 单位是 1/60000 度（5400000=向下）。"""
    sp = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, w, h)
    sp.line.fill.background()
    sp.shadow.inherit = False
    spPr = sp._element.spPr
    for tag in ("a:solidFill", "a:gradFill", "a:noFill", "a:pattFill", "a:blipFill"):
        for e in spPr.findall(qn(tag)):
            spPr.remove(e)
    gs = "".join(
        f'<a:gs pos="{int(pos * 1000)}">'
        f'<a:srgbClr val="{val}"><a:alpha val="{int(alpha * 1000)}"/></a:srgbClr>'
        f"</a:gs>"
        for pos, val, alpha in stops
    )
    el = etree.fromstring(
        f'<a:gradFill xmlns:a="{NS_A}" rotWithShape="1">'
        f'<a:gsLst>{gs}</a:gsLst><a:lin ang="{ang}" scaled="0"/></a:gradFill>'
    )
    spPr.find(qn("a:prstGeom")).addnext(el)
    return sp


def add_text(slide, x, y, w, h, runs, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP):
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    first = True
    for text, size, color, bold, space_before in runs:
        para = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        para.alignment = align
        if space_before:
            para.space_before = Pt(space_before)
        run = para.add_run()
        run.text = text
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.color.rgb = color
        run.font.name = "微软雅黑"
    return tb


def build(no_text: bool = False, out: pathlib.Path | None = None) -> pathlib.Path:
    """no_text=True 出纯图版：只有画 + 转场，不放任何文字与遮罩。"""
    missing = [i for i, *_ in PAGES if not (IMG / f"p{i:03d}.jpg").exists()]
    if missing:
        raise SystemExit(f"[ppt] 缺图：{missing}")

    prs = Presentation()
    prs.slide_width = Inches(W)
    prs.slide_height = Inches(H)
    blank = prs.slide_layouts[6]

    for n, (idx, kicker, title, sub) in enumerate(PAGES, 1):
        s = prs.slides.add_slide(blank)
        s.shapes.add_picture(str(IMG / f"p{idx:03d}.jpg"), 0, 0, Inches(W), Inches(H))

        if no_text:
            # 纯图：不放文字、不放遮罩，每页 3.6 秒，转场按 FLOW 走
            set_transition(s, FLOW[(n - 1) % len(FLOW)], 3600, speed="med")
            continue

        trans = FLASH[(n - 1) % len(FLASH)]

        if n == 1:
            # 封面：主体在左，字压右侧；横向渐变把右边压暗
            grad_rect(
                s, 0, 0, Inches(W), Inches(H),
                [(0, "0F0D0A", 0), (42, "0F0D0A", 0), (100, "0F0D0A", 72)], ang=0,
            )
            add_text(
                s, Inches(7.1), Inches(1.55), Inches(5.6), Inches(3.2),
                [
                    ("看似拒绝，", 50, WHITE, True, 0),
                    ("其实是偷偷喜欢你", 50, WHITE, True, 4),
                    ("7 个信号，中了 4 个以上", 21, GREY, False, 22),
                    ("就别再犹豫了", 21, GREY, False, 4),
                ],
            )
            add_text(
                s, Inches(7.1), Inches(6.15), Inches(5.6), Inches(0.6),
                [("—— 从一条抖音片反推出来的判断清单", 14, ORANGE, True, 0)],
            )
            set_transition(s, trans, 5000)
            continue

        # 内页：底部渐变压暗，字压在下三分之一
        grad_rect(
            s, 0, Inches(3.45), Inches(W), Inches(H - 3.45),
            [(0, "0F0D0A", 0), (55, "0F0D0A", 55), (100, "0F0D0A", 88)],
        )
        grad_rect(s, Inches(0.98), Inches(4.42), Inches(0.95), Inches(0.05), [(0, "E8722F", 0)]) \
            if False else None
        # 橙色短横线（纯色，用 1px 高矩形）
        bar = s.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, Inches(0.98), Inches(4.4), Inches(0.95), Inches(0.05)
        )
        bar.fill.solid()
        bar.fill.fore_color.rgb = ORANGE
        bar.line.fill.background()
        bar.shadow.inherit = False

        runs = []
        if kicker:
            runs.append((kicker, 15, ORANGE, True, 0))
        runs.append((title, 40 if len(title) <= 12 else 34, WHITE, True, 8 if kicker else 0))
        runs.append((sub, 19, GREY, False, 10))
        add_text(s, Inches(1.0), Inches(4.6), Inches(11.3), Inches(2.4), runs)

        add_text(
            s, Inches(W - 1.45), Inches(H - 0.6), Inches(1.0), Inches(0.32),
            [(f"{n:02d} / {len(PAGES)}", 12, GREY, False, 0)],
            align=PP_ALIGN.RIGHT,
        )
        set_transition(s, trans, int(page_seconds(title, sub) * 1000))

    # 注意：不写 presentation.xml 的 <p:showPr>。advTm 已足够让放映自动翻页，
    # 而 showPr 不在 CT_Presentation 的 schema 序列里，硬插会让 PowerPoint 提示「需要修复」。
    target = out or OUT
    target.parent.mkdir(parents=True, exist_ok=True)
    prs.save(target)
    return target


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--open", action="store_true", help="出完直接打开")
    ap.add_argument("--no-text", action="store_true",
                    help="纯图版：不放标题/副文/页码，只做画面与转场衔接")
    a = ap.parse_args()
    target = ROOT / "deliver" / ("七个信号-动画版.pptx" if a.no_text else "七个信号-图文版.pptx")
    out = build(no_text=a.no_text, out=target)
    print(f"[ppt] 写出 {out}  {out.stat().st_size / 1024 / 1024:.2f} MB  页数 {len(PAGES)}")
    if a.open:
        subprocess.Popen(["cmd", "/c", "start", "", str(out)], shell=False)


if __name__ == "__main__":
    main()
