# -*- coding: utf-8 -*-
"""生成统一风格的图标 PNG（替代 emoji）。

为什么不直接用 emoji：剪映/Windows/手机 三端渲染的是各自的彩色表情字体，跨设备不一致，
而且和卡通底板的粗描边风格打架。这里用 Pillow 画线条几何图标，粗描边 + 单一强调色，
256×256 透明底，和 Panel.tsx 里的 SVG 保持同一套形状。

    python tools\\mk_icons.py            # 输出到 lbr-promo\\public\\textures\\icons\\
"""
from __future__ import annotations

import pathlib

from PIL import Image, ImageDraw

SIZE = 256
PAD = 26
W = 16                      # 描边粗细
INK = (26, 24, 21, 255)     # 近黑
RED = (200, 52, 43, 255)
GREEN = (27, 74, 60, 255)
OUT = pathlib.Path(__file__).resolve().parent.parent / "lbr-promo" / "public" / "textures" / "icons"


def canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img)


def save(img: Image.Image, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{name}.png"
    img.save(path)
    print(f"  {path.name}  {path.stat().st_size/1024:.1f} KB")


def check() -> None:
    img, d = canvas()
    d.line([(52, 132), (104, 184), (204, 76)], fill=GREEN, width=W + 6, joint="curve")
    save(img, "check")


def cross() -> None:
    img, d = canvas()
    d.line([(66, 66), (190, 190)], fill=RED, width=W + 6)
    d.line([(190, 66), (66, 190)], fill=RED, width=W + 6)
    save(img, "cross")


def house() -> None:
    img, d = canvas()
    d.line([(40, 128), (128, 46), (216, 128)], fill=INK, width=W, joint="curve")
    d.rectangle([70, 128, 186, 212], outline=INK, width=W)
    d.rectangle([112, 158, 144, 212], outline=INK, width=W)
    save(img, "house")


def family() -> None:
    img, d = canvas()
    for cx, r in ((92, 26), (164, 20)):
        d.ellipse([cx - r, 58 - r, cx + r, 58 + r], outline=INK, width=W)          # 头
        d.arc([cx - 40, 96, cx + 40, 180], 180, 360, fill=INK, width=W)             # 肩
    d.line([(92, 150), (92, 210)], fill=INK, width=W)
    d.line([(164, 140), (164, 210)], fill=INK, width=W)
    save(img, "family")


def clock() -> None:
    img, d = canvas()
    d.ellipse([40, 40, 216, 216], outline=INK, width=W)
    d.line([(128, 128), (128, 74)], fill=INK, width=W)
    d.line([(128, 128), (176, 150)], fill=INK, width=W)
    save(img, "clock")


def phone() -> None:
    img, d = canvas()
    d.rounded_rectangle([76, 34, 180, 222], radius=22, outline=INK, width=W)
    d.line([(108, 190), (148, 190)], fill=INK, width=W)
    save(img, "phone")


def money() -> None:
    img, d = canvas()
    d.rounded_rectangle([34, 88, 222, 178], radius=14, outline=INK, width=W)
    d.ellipse([104, 114, 152, 152], outline=INK, width=W - 4)
    d.line([(56, 116), (56, 150)], fill=INK, width=W - 4)
    d.line([(200, 116), (200, 150)], fill=INK, width=W - 4)
    save(img, "money")


def up() -> None:
    img, d = canvas()
    d.line([(128, 208), (128, 62)], fill=GREEN, width=W + 4)
    d.line([(74, 116), (128, 58), (182, 116)], fill=GREEN, width=W + 4, joint="curve")
    save(img, "up")


def down() -> None:
    img, d = canvas()
    d.line([(128, 48), (128, 194)], fill=RED, width=W + 4)
    d.line([(74, 140), (128, 198), (182, 140)], fill=RED, width=W + 4, joint="curve")
    save(img, "down")


def arrow() -> None:
    img, d = canvas()
    d.line([(36, 128), (196, 128)], fill=INK, width=W, joint="curve")
    d.line([(150, 82), (204, 128), (150, 174)], fill=INK, width=W, joint="curve")
    save(img, "arrow")


def dot() -> None:
    img, d = canvas()
    d.ellipse([88, 88, 168, 168], fill=RED)
    save(img, "dot")


ICONS = {
    "check": check, "cross": cross, "house": house, "family": family,
    "clock": clock, "phone": phone, "money": money,
    "up": up, "down": down, "arrow": arrow, "dot": dot,
}


def main() -> int:
    print(f"输出目录：{OUT}")
    for name, fn in ICONS.items():
        fn()
    print(f"\n{len(ICONS)} 个图标完成。剪映侧走「图标」图片轨，Remotion 侧仍用 Panel.tsx 的 SVG（同形状）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
