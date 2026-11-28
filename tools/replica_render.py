#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""replica_render.py —— 把 replica spec 直接渲成 MP4（图片序列 + 烧字幕 + 音轨）。

为什么要有它：
  剪映草稿适合微调，但交付要一条 MP4。spec 里已经有渲片需要的全部事实
  （每屏 start/end + 代表图、每句字幕 s/e + 文本、音轨），ffmpeg 足够渲出来，
  不必绕 Remotion（那是「自己写剧本」那条线的引擎，数据格式不一样）。

用法：
  python tools/replica_render.py --spec qa2/replica/out/xxx.spec.json -o qa2/replica/out/xxx.mp4 \
      --voice qa2/replica/voice.wav
  python tools/replica_render.py --spec ... -o ... --no-subs --crf 18 --fps 30

输入约定（跟 replica.py / jy_from_spec.py 一致）：
  scenes[].start / end        屏的起止秒
  scenes[].assets[].file      相对 spec 所在目录的图；缺图用纯色占位
  subs[]                      字幕（s / e / text）
  --voice                     整条音轨（没有就出静音片）
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

FONT = "Microsoft YaHei"          # Windows 上一定有；别的系统改成可用字体
PLACEHOLDER = "0xE8E2D8"          # 缺图时的米白底（跟重画风格同色系）


def ffmpeg() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    here = Path(__file__).resolve().parent
    ff = here / "ff.cmd"
    if ff.exists():
        return str(ff)
    raise SystemExit("找不到 ffmpeg：pip install imageio-ffmpeg，或把 ffmpeg 加进 PATH")


def srt_time(t: float) -> str:
    h, r = divmod(max(0.0, t), 3600)
    m, s = divmod(r, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int(round((s - int(s)) * 1000)):03d}"


def build_srt(subs: list[dict], path: Path) -> int:
    lines, n = [], 0
    for seg in subs:
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        n += 1
        lines.append(str(n))
        lines.append(f"{srt_time(float(seg.get('s') or 0))} --> {srt_time(float(seg.get('e') or 0))}")
        lines.append(text)
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return n


def render(spec_path: Path, out: Path, voice: Path | None, subs_on: bool,
           crf: int, fps: int, placeholder: str, dry: bool) -> int:
    spec = json.loads(spec_path.read_text(encoding="utf-8-sig"))
    meta = spec.get("meta") or {}
    total = float(meta.get("target_duration") or meta.get("src_duration") or meta.get("duration") or 0)
    w = int(meta.get("w") or meta.get("width") or 1280)
    h = int(meta.get("h") or meta.get("height") or 720)
    scenes = spec.get("scenes") or []
    subs = spec.get("subs") or []
    if not scenes:
        raise SystemExit("spec 里没有 scenes")
    if total <= 0:
        total = float(scenes[-1].get("e") or scenes[-1].get("end") or 0)
    base = spec_path.parent

    # ---- 铺时间轴：屏按 start/end 排，空档用占位补满 ----
    def img_of(sc: dict) -> Path | None:
        for a in (sc.get("assets") or []):
            f = a.get("file")
            if not f:
                continue
            p = Path(f)
            p = p if p.is_absolute() else (base / p)
            if p.exists():
                return p
        return None

    timeline, t = [], 0.0

    def _s(sc: dict) -> float:
        v = sc.get("s")
        return float(v if v is not None else (sc.get("start") or 0))

    def _e(sc: dict) -> float:
        v = sc.get("e")
        return float(v if v is not None else (sc.get("end") or 0))

    for sc in sorted(scenes, key=_s):
        s, e = _s(sc), _e(sc)
        if s - t > 0.02:                       # 屏间空档
            timeline.append((None, t, s))
        if e - s > 0.02:
            timeline.append((img_of(sc), s, e))
        t = max(t, e)
    if total - t > 0.02:
        timeline.append((None, t, total))

    missing = sum(1 for im, _, _ in timeline if im is None)
    print(f"[render] {w}x{h}  {total:.2f}s  屏 {len(scenes)}  时间片 {len(timeline)}  缺图 {missing}")
    if dry:
        print("[render] --dry：不渲")
        return 0

    # 不用 TemporaryDirectory：它在 with 退出时立刻删目录，而 ffmpeg 的 cwd 指向它
    # 时 Windows 会拒绝删除 / 或残留占用；改成显式 mkdtemp 并把现场留着便于排查。
    td = Path(tempfile.mkdtemp(prefix="replica_render_"))
    try:
        listfile = td / "list.txt"
        lines = []
        last_file = ""
        for i, (im, s, e) in enumerate(timeline):
            dur = max(0.04, e - s)
            if im is None:
                # 用一个纯色帧当占位（-f lavfi 不能进 concat，先转成图）
                ph = td / f"ph{i:04d}.png"
                subprocess.run([ffmpeg(), "-y", "-loglevel", "error", "-f", "lavfi",
                                "-i", f"color=c={placeholder}:s={w}x{h}:d=1",
                                "-frames:v", "1", str(ph)], check=True)
                im = ph
            # 必须绝对路径：concat 列表里的相对路径是相对 list.txt 解析的，
            # ffmpeg 的 cwd 又指向临时目录，相对路径一定打不开（踩过）。
            last_file = im.resolve().as_posix()
            lines.append(f"file '{last_file}'")
            lines.append(f"duration {dur:.3f}")
        # concat 已知怪癖：末项要再写一次，否则最后一帧被吞
        if last_file:
            lines.append(f"file '{last_file}'")
        listfile.write_text("\n".join(lines) + "\n", encoding="utf-8")
        assert listfile.exists(), f"concat 列表没写出来：{listfile}"
        print(f"[render] 工作目录 {td}  list.txt {listfile.stat().st_size} B  行数 {len(lines)}")

        srt = td / "sub.srt"
        n_sub = build_srt(subs, srt) if subs_on else 0

        vf = [f"scale={w}:{h}:force_original_aspect_ratio=decrease",
              f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color={placeholder.replace('0x', '#')}",
              "setsar=1", "format=yuv420p"]
        if n_sub:
            # 字幕文件用相对路径（cwd 指到 td），躲开 Windows 盘符转义
            vf.append(f"subtitles=sub.srt:force_style='FontName={FONT},FontSize=22,"
                      f"PrimaryColour=&H00FFFFFF,OutlineColour=&H00101010,BorderStyle=1,Outline=1,Shadow=0,"
                      f"MarginV=28'")

        cmd = [ffmpeg(), "-y", "-loglevel", "error", "-stats",
               "-f", "concat", "-safe", "0", "-i", str(listfile)]
        if voice and voice.exists():
            cmd += ["-i", str(voice.resolve())]
        cmd += ["-vf", ",".join(vf), "-r", str(fps),
                "-c:v", "libx264", "-preset", "medium", "-crf", str(crf), "-pix_fmt", "yuv420p"]
        if voice and voice.exists():
            cmd += ["-map", "0:v:0", "-map", "1:a:0", "-c:a", "aac", "-b:a", "192k",
                    "-af", "apad", "-shortest"]
        else:
            cmd += ["-an"]
        cmd += ["-t", f"{total:.3f}", "-movflags", "+faststart", str(out.resolve())]

        print(f"[render] 字幕 {n_sub} 段  音轨 {'有' if voice and voice.exists() else '无（静音片）'}")
        print("[render] 开始渲染 …")
        r = subprocess.run(cmd, cwd=str(td), capture_output=True, text=True)
        if r.returncode != 0:
            print(r.stderr[-2500:], file=sys.stderr)
            raise SystemExit(f"[render] ffmpeg 失败（exit {r.returncode}）")
    finally:
        pass          # 现场（list.txt / sub.srt / 占位图）留在 mkdtemp 目录里，方便查

    if not out.exists():
        raise SystemExit("[render] 没生成文件")
    print(f"[render] → {out}  {out.stat().st_size/1048576:.1f} MB")
    return 0


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="把 replica spec 渲成 MP4")
    ap.add_argument("--spec", required=True)
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--voice", default="", help="整条音轨（replica_assemble 的产物）；不填=静音片")
    ap.add_argument("--no-subs", action="store_true")
    ap.add_argument("--crf", type=int, default=20)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--placeholder", default=PLACEHOLDER)
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    return render(Path(a.spec), Path(a.out), Path(a.voice) if a.voice else None,
                  not a.no_subs, a.crf, a.fps, a.placeholder, a.dry)


if __name__ == "__main__":
    raise SystemExit(main())
