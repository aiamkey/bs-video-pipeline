"""统计一个视频的切点与镜头长度：ffmpeg 解码 fps=2 灰度小图 → numpy 帧差。

用法: python tools/shot_stats.py <video> [threshold] [fps]
默认 threshold=9（0-255 灰度平均绝对差），fps=2
输出: 总时长 / 切点数 / 镜头数 / 中位镜长 / 静止占比
"""
import subprocess
import sys

import numpy as np

FF = r"E:\miniconda\envs\JupyterProject\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v9.0.2.exe"


def stats(path, thr=9.0, fps=2, w=160, h=90):
    cmd = [FF, "-v", "error", "-i", path, "-vf", f"fps={fps},scale={w}:{h},format=gray",
           "-f", "rawvideo", "-"]
    raw = subprocess.run(cmd, capture_output=True).stdout
    n = len(raw) // (w * h)
    frames = np.frombuffer(raw[: n * w * h], dtype=np.uint8).reshape(n, h, w).astype(np.int16)
    d = np.abs(np.diff(frames, axis=0)).mean(axis=(1, 2))
    cuts = np.where(d > thr)[0] + 1
    still = np.where(d < 1.0)[0]
    shot_lens = np.diff(np.concatenate([[0], cuts, [n]])) / fps
    print(f"file={path}")
    print(f"duration={n/fps:.1f}s  samples={n}  cuts={len(cuts)}  shots={len(shot_lens)}")
    print(f"shot_median={np.median(shot_lens):.2f}s  shot_mean={shot_lens.mean():.2f}s  shot_max={shot_lens.max():.2f}s")
    print(f"still_ratio={len(still)/max(1,len(d))*100:.0f}%  still_runs_max={max((len(list(g)) for k,g in __import__('itertools').groupby(d<1.0) if k), default=0)/fps:.1f}s")
    if len(cuts):
        print("cut_times=" + ",".join(f"{c/fps:.1f}" for c in cuts[:80]))
    return cuts, shot_lens


if __name__ == "__main__":
    stats(sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 9.0,
          float(sys.argv[3]) if len(sys.argv) > 3 else 2.0)
