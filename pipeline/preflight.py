"""依赖自检：缺什么、怎么装，一次说清。

用法：
  python pipeline/preflight.py            # 只体检
  python pipeline/preflight.py --install  # 缺的自动装（npm ci / pip install）

检查顺序按"先决条件"排：Python → Node → ffmpeg → Python 包 → Remotion 依赖 → 素材 → API key。
"""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REMOTION = ROOT / "remotion"
OK, BAD, WARN = "✓", "✗", "·"

rows = []


def cfg():
    for n in ("config.local.json", "config.json", "config.example.json"):
        f = HERE / n
        if f.exists():
            return json.loads(f.read_text(encoding="utf-8"))
    return {}


C = cfg()
INSTALL = "--install" in sys.argv


def add(name, ok, detail, fix="", hard=True):
    rows.append((OK if ok else (BAD if hard else WARN), name, detail, fix if not ok else ""))


def run(cmd, cwd=None):
    print(f"  $ {' '.join(map(str, cmd))}")
    return subprocess.run(cmd, cwd=cwd, shell=False).returncode == 0


# 1 Python
pv = sys.version_info
add("Python ≥3.10", pv >= (3, 10), f"{pv.major}.{pv.minor}.{pv.micro}", "安装 Python 3.10+")

# 2 Node / npx
node = shutil.which("node")
npx = shutil.which("npx")
ver = ""
if node:
    try:
        ver = subprocess.run([node, "-v"], capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:
        pass
major = int(re.sub(r"\D", "", ver)[:2]) if re.search(r"\d", ver) else 0
add("Node ≥18", bool(node) and major >= 18, ver or "未找到", "安装 Node 18/20/22（推荐 nvm）")
add("npx", bool(npx), npx or "未找到", "npx 随 Node 一起安装")

# 3 ffmpeg
ff = C.get("paths", {}).get("ffmpeg") or "ffmpeg"
ff_ok = Path(ff).exists() if ff not in ("ffmpeg", "") else bool(shutil.which("ffmpeg"))
add("ffmpeg", ff_ok, ff, "装 ffmpeg 并加入 PATH，或改 config.local.json → paths.ffmpeg")
if ff_ok and ff not in ("ffmpeg", ""):
    pass

# 4 Python 包
pkgs = {"requests": "requests", "numpy": "numpy", "dashscope": "dashscope"}
missing_py = []
for mod, pip_name in pkgs.items():
    try:
        __import__(mod)
        add(f"py:{mod}", True, "")
    except ImportError:
        missing_py.append(pip_name)
        add(f"py:{mod}", False, "未安装", f"pip install {pip_name}")
if INSTALL and missing_py:
    run([sys.executable, "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")])

# 5 Remotion 依赖
pkg_json = REMOTION / "package.json"
add("remotion/package.json", pkg_json.exists(), str(pkg_json.relative_to(ROOT)) if pkg_json.exists() else "缺")
nm = REMOTION / "node_modules"
cli = nm / "@remotion" / "cli"
add("remotion/node_modules", nm.exists() and cli.exists(), "已安装" if cli.exists() else "未安装",
    "cd remotion && npm ci")
if INSTALL and not (nm.exists() and cli.exists()) and pkg_json.exists():
    run(["npm", "ci"], cwd=REMOTION)

# 6 素材
bs = REMOTION / "public" / "textures" / "bs"
n_img = len(list(bs.glob("*.jpg"))) if bs.exists() else 0
add("实拍素材(bs)", n_img >= 1, f"{n_img} 张", "把 bs-*.jpg 放进 remotion/public/textures/bs/", hard=False)
slides = REMOTION / "public" / "textures" / "slides"
n_sl = len(list(slides.glob("*.jpg"))) if slides.exists() else 0
add("卡通素材(slides)", n_sl >= 1, f"{n_sl} 张", "用 tools/img.py 生成，见 CARTOON.md", hard=False)

# 7 API key
key = os.environ.get("DASHSCOPE_API_KEY") or C.get("keys", {}).get("dashscope")
add("DASHSCOPE_API_KEY", bool(key), "已配置" if key else "未配置",
    'set DASHSCOPE_API_KEY=sk-xxx  或 pipeline/config.local.json → keys.dashscope')

# 8 可选：video-shotcraft
sc = Path(r"C:\Users\张宇\OneDrive\Desktop\video\video-shotcraft")
add("video-shotcraft(可选)", sc.exists(), str(sc) if sc.exists() else "未找到",
    "clone https://github.com/vincentwei1021/video-shotcraft", hard=False)

# 输出
w = max(len(r[1]) for r in rows) + 2
for mark, name, detail, fix in rows:
    print(f"{mark} {name:<{w}}{detail}")
    if fix:
        print(f"    → {fix}")

fails = [r for r in rows if r[0] == BAD]
print("-" * 60)
if fails:
    print(f"{len(fails)} 项必须依赖缺失。装完重跑：python pipeline/preflight.py")
    sys.exit(1)
print("全部通过，可以开跑：python pipeline/run.py all <EP>")
