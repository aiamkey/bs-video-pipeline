r"""把自动播放的 PPT 渲成 MP4 —— 和原片一样的「一口气看完」版本。

用法：
    python tools\ppt2video.py                                   # 默认出 1280x720 / 30fps / 0.5s 转场
    python tools\ppt2video.py --no-xfade                        # 硬切（转场关掉）
    python tools\ppt2video.py --voice <wav> --voice-at 0        # 垫一条音轨

两件事：
1. 每页停留时间**不写死**，从 pptx 的 <p:transition advTm> 读 —— 改 PPT 就自动跟着变。
2. 转场用 ffmpeg 的 xfade 串起来，offset 按「已输出长度 - 转场时长」递推，
   保证 20 段接完总长正好是 sum(advTm) - 19*转场时长。
"""
from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys

try:
    import imageio_ffmpeg
except ModuleNotFoundError:  # 自带 python 不一定装了这个包
    imageio_ffmpeg = None

from pptx import Presentation
from pptx.oxml.ns import qn

FFMPEG_FALLBACK = pathlib.Path(
    r"E:\miniconda\envs\JupyterProject\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v9.0.2.exe"
)


def ffmpeg_exe() -> str:
    """优先用 imageio_ffmpeg 带的，没有再落到本机已知那份。"""
    try:
        if imageio_ffmpeg is None:
            raise ImportError("no imageio_ffmpeg")
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        if FFMPEG_FALLBACK.exists():
            return str(FFMPEG_FALLBACK)
        raise SystemExit("[vid] 找不到 ffmpeg")

ROOT = pathlib.Path(__file__).resolve().parent.parent
PPTX = ROOT / "deliver" / "七个信号-图文版.pptx"
DEFAULT_OUT = ROOT / "deliver" / "七个信号-自动播放.mp4"

NODE = pathlib.Path(
    r"E:\software\DeepSeek Plus\DSH NEXT\resources\runtime\x64\primary-runtime\dependencies\node\bin\node.exe"
)
CLI = pathlib.Path(
    r"E:\software\DeepSeek Plus\DSH NEXT\resources\app.asar.unpacked\node_modules\@deepseek-ai\libreoffice-kit\lib\cli.js"
)


def page_durations(pptx: pathlib.Path) -> list[float]:
    prs = Presentation(str(pptx))
    durs: list[float] = []
    for s in prs.slides:
        tr = s._element.find(qn("p:transition"))
        adv = tr.get("advTm") if tr is not None else None
        durs.append(int(adv) / 1000.0 if adv else 3.0)
    return durs


def render_pages(pptx: pathlib.Path, outdir: pathlib.Path) -> list[pathlib.Path]:
    # libreoffice-kit 要求目标目录不存在
    if outdir.exists():
        import shutil

        shutil.rmtree(outdir)
    outdir.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        [str(NODE), str(CLI), "render", "--input", str(pptx), "--output-dir", str(outdir)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if r.returncode != 0:
        raise SystemExit(f"[vid] 渲染失败：{r.stderr[-600:]}")
    pages = sorted(outdir.glob("page-*.png"))
    if not pages:
        raise SystemExit("[vid] 渲染没出图")
    return pages


def build_video(
    pages: list[pathlib.Path],
    durs: list[float],
    out: pathlib.Path,
    w: int = 1280,
    h: int = 720,
    fps: int = 30,
    trans: float = 0.5,
    workdir: pathlib.Path | None = None,
    voice: pathlib.Path | None = None,
    voice_at: float = 0.0,
) -> pathlib.Path:
    ff = ffmpeg_exe()
    workdir = workdir or out.parent / "_ppt2video"
    workdir.mkdir(parents=True, exist_ok=True)

    if len(pages) != len(durs):
        raise SystemExit(f"[vid] 页数 {len(pages)} 与 advTm {len(durs)} 对不上")

    args: list[str] = [ff, "-y", "-loglevel", "error"]
    for pg, d in zip(pages, durs):
        # loop 一张图，多给 trans 秒余量给最后的 xfade 用
        args += ["-loop", "1", "-t", f"{d + trans:.3f}", "-i", str(pg)]
    if voice:
        args += ["-i", str(voice)]

    parts: list[str] = []
    for i in range(len(pages)):
        parts.append(
            f"[{i}:v]scale={w}:{h}:force_original_aspect_ratio=increase,"
            f"crop={w}:{h},fps={fps},setsar=1,format=yuv420p[v{i}]"
        )

    if trans > 0 and len(pages) > 1:
        cur = "v0"
        acc = durs[0]
        for i in range(1, len(pages)):
            off = acc - trans
            nxt = f"x{i}"
            parts.append(
                f"[{cur}][v{i}]xfade=transition=fade:duration={trans}:offset={off:.3f}[{nxt}]"
            )
            cur = nxt
            acc = acc + durs[i] - trans
        label = cur
        total = acc
    else:
        parts.append("".join(f"[v{i}]" for i in range(len(pages))) + f"concat=n={len(pages)}:v=1:a=0[vc]")
        label = "vc"
        total = sum(durs)

    script = workdir / "filter.txt"
    script.write_text(";\n".join(parts), encoding="utf-8")
    filter_str = script.read_text(encoding="utf-8")

    args += [
        # 这台机器的 ffmpeg 构建不认 -filter_complex_script，直接传字符串
        # （20 段约 2 KB，远低于 Windows 命令行 32 KB 上限）
        "-filter_complex", filter_str,
        "-map", f"[{label}]",
        "-t", f"{total:.3f}",
        "-c:v", "libx264", "-crf", "20", "-preset", "medium",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
    ]
    if voice:
        args += ["-map", f"{len(pages)}:a", "-c:a", "aac", "-b:a", "128k",
                 "-af", f"adelay={int(voice_at * 1000)}|{int(voice_at * 1000)}"]
    out.parent.mkdir(parents=True, exist_ok=True)
    args += [str(out.resolve())]

    print(f"[vid] 页数 {len(pages)}  单页 {min(durs):.1f}-{max(durs):.1f}s  "
          f"转场 {trans}s  目标时长 {total:.1f}s")
    r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise SystemExit(f"[vid] ffmpeg 失败：\n{r.stderr[-1500:]}")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pptx", default=str(PPTX))
    ap.add_argument("-o", "--out", default=str(DEFAULT_OUT))
    ap.add_argument("--no-xfade", action="store_true")
    ap.add_argument("--trans", type=float, default=0.5)
    ap.add_argument("--voice", default="")
    ap.add_argument("--voice-at", type=float, default=0.0)
    a = ap.parse_args()

    pptx = pathlib.Path(a.pptx)
    out = pathlib.Path(a.out)
    durs = page_durations(pptx)
    pages = render_pages(pptx, out.parent / "_ppt2video" / "pages")
    print(f"[vid] 渲染出 {len(pages)} 页")
    build_video(
        pages, durs, out,
        trans=0.0 if a.no_xfade else a.trans,
        workdir=out.parent / "_ppt2video",
        voice=pathlib.Path(a.voice) if a.voice else None,
        voice_at=a.voice_at,
    )
    mb = out.stat().st_size / 1024 / 1024
    print(f"[vid] 写出 {out}  {mb:.2f} MB")


if __name__ == "__main__":
    main()
