# -*- coding: utf-8 -*-
"""统一环境发现：路径 / ffmpeg / python / 外部工具，全从这里拿。

**为什么有这个文件**：以前 `align_v2.py`、`cosy_chapter.py`、`shot_stats.py`、
`stock.py`、`preflight.py`、`run.py` 各自写死了作者机器的
`C:\\Users\\张宇\\...` 和 `E:\\miniconda\\...`，换一台机器必然跑不通。
现在所有工具 `import env` 就够了。

解析优先级（每一层都可覆盖上一层）：
    环境变量  →  pipeline/config.json 的 paths.*  →  自动探测  →  报错并给出修复命令

环境变量：
    LBR_PROMO      视频工程目录（含 remotion/ 与 public/）
    LBR_ROOT       工程根目录（含 pipeline/ tools/ scripts/）
    FFMPEG         ffmpeg 可执行文件
    PYTHON         指定 python
    VIDEO_SHOTCRAFT  卡库目录（找灵感用，可选）
    TTS_CONFIG     tts-service 的 config.local.json（配音用，含 key）

自检：
    python pipeline/env.py
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent

_cfg_cache: dict | None = None


def config() -> dict:
    """pipeline/config.json（不存在则回落到 config.example.json）。"""
    global _cfg_cache
    if _cfg_cache is not None:
        return _cfg_cache
    for name in ("config.json", "config.example.json"):
        p = HERE / name
        if p.is_file():
            try:
                _cfg_cache = json.loads(p.read_text(encoding="utf-8-sig"))
                break
            except ValueError:
                continue
    else:
        _cfg_cache = {}
    return _cfg_cache


def _from_cfg(key: str) -> str | None:
    val = (config().get("paths") or {}).get(key)
    return str(val) if val else None


def _abs(p: str | Path) -> Path:
    """相对路径按 PROJECT 解析。"""
    path = Path(os.path.expandvars(os.path.expanduser(str(p))))
    return path if path.is_absolute() else (PROJECT / path).resolve()


def _first_existing(*cands: Path | None) -> Path | None:
    for c in cands:
        if c and Path(c).exists():
            return Path(c)
    return None


# ---------------------------------------------------------------- 目录

def root() -> Path:
    """工程根：含 pipeline/ 的那一层。"""
    env = os.environ.get("LBR_ROOT")
    return _abs(env) if env else PROJECT


def promo() -> Path:
    """视频工程：含 remotion/ 与 public/ 的那一层。"""
    env = os.environ.get("LBR_PROMO")
    if env:
        return _abs(env)
    cand = _from_cfg("promo")
    r = root()
    found = _first_existing(
        _abs(cand) if cand else None,
        r / "remotion",            # 仓库布局：remotion 在根下
        r,                          # 工作目录布局：pipeline 在 lbr-promo 里
        r.parent / "lbr-promo",
    )
    # 必须是"含 remotion 或 public"的那层
    for c in (found, r, r.parent / "lbr-promo", PROJECT, PROJECT.parent):
        if c and ((c / "remotion").is_dir() or (c / "public").is_dir()):
            return Path(c).resolve()
    return r


def scripts() -> Path:
    """放 script-*.json 的目录。"""
    for c in (promo().parent / "scripts", root() / "scripts", promo() / "scripts"):
        if c.is_dir():
            return c.resolve()
    return (root() / "scripts")


def tools() -> Path:
    """放 align_v2.py / img.py 等工具的目录。"""
    for c in (root() / "tools", promo().parent / "tools", promo() / "tools"):
        if c.is_dir():
            return c.resolve()
    return (root() / "tools")


def public(*parts: str) -> Path:
    """Remotion 的静态资源目录（textures / audio / cards / icons）。"""
    p = promo()
    base = p / "public" if (p / "public").is_dir() else p / "remotion" / "public"
    return base.joinpath(*parts)


def data(*parts: str, create: bool = False) -> Path:
    """remotion/src/data（film.json / sfx.json）。生成的目录，缺了自动建。"""
    p = promo()
    base = p / "remotion" / "src" / "data"
    if not base.is_dir():
        base = p / "src" / "data"
    if create:
        base.mkdir(parents=True, exist_ok=True)
    return base.joinpath(*parts)


# ---------------------------------------------------------------- 可执行文件

def ffmpeg() -> str | None:
    env = os.environ.get("FFMPEG")
    if env and Path(env).is_file():
        return env
    cand = _from_cfg("ffmpeg")
    if cand:
        p = _abs(cand)
        if p.is_file():
            return str(p)
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:                                  # pip 装 imageio-ffmpeg 自带的那个
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def python() -> str:
    env = os.environ.get("PYTHON")
    if env and Path(env).is_file():
        return env
    cand = _from_cfg("python")
    if cand:
        p = _abs(cand)
        if p.is_file():
            return str(p)
    return sys.executable


def shotcraft() -> Path | None:
    """卡库（找灵感用，没有也能跑）。"""
    env = os.environ.get("VIDEO_SHOTCRAFT")
    if env:
        return _abs(env)
    cand = _from_cfg("shotcraft")
    if cand and _abs(cand).is_dir():
        return _abs(cand)
    for c in (root().parent / "video-shotcraft", root() / "video-shotcraft"):
        if c.is_dir():
            return c
    return None


def tts_config() -> Path | None:
    """tts-service 的 config.local.json（含 dashscope key；没有就用环境变量）。"""
    env = os.environ.get("TTS_CONFIG")
    if env and Path(env).is_file():
        return _abs(env)
    cand = _from_cfg("tts_config")
    if cand and _abs(cand).is_file():
        return _abs(cand)
    home = Path(os.environ.get("USERPROFILE") or Path.home())
    for c in (home / ".dsh/skills/tts-service/config.local.json",
              home / ".dsh/skills/tts-service/config.json"):
        if c.is_file():
            return c
    return None


# ---------------------------------------------------------------- 自检

def summary() -> list[tuple[str, str, str]]:
    """(项, 值, 状态) —— 给 CLI 和 preflight 用。"""
    rows = []
    for label, p, need in (
        ("工程根", root(), True),
        ("视频工程", promo(), True),
        ("脚本目录", scripts(), True),
        ("工具目录", tools(), True),
        ("资源目录", public(), True),
        ("数据目录", data(), False),      # 生成的，缺了由 build_film 建
    ):
        rows.append((label, str(p), "✓" if p.exists() else ("✗ 缺" if need else "·")))
    ff = ffmpeg()
    rows.append(("ffmpeg", ff or "找不到：装 ffmpeg 或 pip install imageio-ffmpeg", "✓" if ff else "✗"))
    rows.append(("python", python(), "✓" if Path(python()).is_file() else "✗"))
    sc = shotcraft()
    rows.append(("卡库(可选)", str(sc) if sc else "未找到（不影响出片）", "✓" if sc else "·"))
    tc = tts_config()
    rows.append(("tts 配置(可选)", str(tc) if tc else "未找到（用 DASHSCOPE_API_KEY 环境变量）", "✓" if tc else "·"))
    return rows


def main() -> int:
    print("环境解析结果（从左到右：环境变量 → config.json → 自动探测）\n")
    bad = 0
    for label, val, status in summary():
        print(f"  {status:2s} {label:12s} {val}")
        if status.startswith("✗"):
            bad += 1
    if bad:
        print("\n有 ✗ 项。修法：")
        print("  · 路径类：设环境变量 LBR_ROOT / LBR_PROMO 指向正确目录")
        print("  · ffmpeg：pip install imageio-ffmpeg，或把 ffmpeg.exe 放进 PATH，或设 FFMPEG 环境变量")
        print("  · python：设 PYTHON 环境变量，或把 python 加进 PATH")
        return 1
    print("\n全部就绪。下一步：python pipeline/selftest.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
