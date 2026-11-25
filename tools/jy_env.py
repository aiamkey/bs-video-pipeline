#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
jy_env.py — 剪映环境自动探测（跨设备可迁移）

不依赖任何硬编码路径，按优先级探测并在多处兜底：
  1) 环境变量（JY_APPS_DIR / JY_APP_VERSION / JY_DRAFTS_ROOT / JY_SKILL_SCRIPTS）
  2) 剪映自己的配置（%LOCALAPPDATA%\\JianyingPro\\User Data\\Config\\globalSetting
     里的 currentCustomDraftPath 就是当前草稿根）
  3) 常见默认位置
  4) 注册表卸载项里登记的安装目录

用法：
  python tools/jy_env.py                  # 人读摘要
  python tools/jy_env.py --json           # JSON
  python tools/jy_env.py --write-env      # 写 tools/jy.env（供 jy.cmd / jy_draft.py 读）
  python tools/jy_env.py --check          # 只校验必需项，缺失返回 1
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HOME = Path.home()
LOCALAPPDATA = Path(os.environ.get("LOCALAPPDATA", HOME / "AppData/Local"))
APPDATA = Path(os.environ.get("APPDATA", HOME / "AppData/Roaming"))
ENV_FILE = Path(__file__).resolve().parent / "jy.env"

# ---------------------------------------------------------------- 安装目录

def _ver_key(name: str):
    """11.6.0.14552 -> (11,6,0,14552)，用于选最高版本"""
    parts = re.findall(r"\d+", name)
    return tuple(int(p) for p in parts) if parts else (0,)


def find_apps_dirs() -> list[Path]:
    """所有可能的 JianyingPro/Apps 目录（只保留存在且含版本子目录的）"""
    cands = []
    for base in (LOCALAPPDATA, Path(os.environ.get("ProgramFiles", "C:/Program Files")),
                 Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")),
                 Path("C:/Program Files"), Path("C:/Program Files (x86)"),
                 Path("D:/Program Files"), Path("E:/Program Files")):
        cands += [base / "JianyingPro" / "Apps",
                  base / "JianyingPro",        # 有些安装把 Apps 省掉
                  base / "剪映" / "Apps"]
    # 注册表兜底：卸载项 DisplayIcon 指向 JianyingPro.exe
    try:
        import winreg
        for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            for sub in (r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
                        r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"):
                try:
                    with winreg.OpenKey(root, sub) as k:
                        for i in range(winreg.QueryInfoKey(k)[0]):
                            try:
                                name = winreg.EnumKey(k, i)
                                if "jianying" not in name.lower() and "剪映" not in name:
                                    continue
                                with winreg.OpenKey(k, name) as sk:
                                    icon = winreg.QueryValueEx(sk, "DisplayIcon")[0]
                                p = Path(str(icon).strip('"').split(",")[0])
                                if p.exists():
                                    cands.append(p.parent if p.is_file() else p)
                                    cands.append(p.parent.parent)
                            except OSError:
                                pass
                except OSError:
                    pass
    except Exception:
        pass

    seen, out = set(), []
    for c in cands:
        try:
            c = c.resolve()
        except OSError:
            continue
        if c in seen or not c.is_dir():
            continue
        seen.add(c)
        out.append(c)
    return out


def find_app_version() -> tuple[str | None, Path | None]:
    """返回 (版本号字符串, 该版本目录)"""
    forced = os.environ.get("JY_APP_VERSION")
    dirs = [Path(os.environ["JY_APPS_DIR"])] if os.environ.get("JY_APPS_DIR") else find_apps_dirs()

    versions: list[tuple[tuple, int, str, Path]] = []
    la = str(LOCALAPPDATA).lower()
    for d in dirs:
        # LOCALAPPDATA 下的是剪映自己在用的那份（通常是 junction），优先
        pref = 0 if str(d).lower().startswith(la) else 1
        for sub in d.iterdir() if d.is_dir() else []:
            if sub.is_dir() and re.fullmatch(r"\d+(\.\d+)+", sub.name):
                versions.append((_ver_key(sub.name), pref, sub.name, sub))

    if forced:
        for _, _, name, p in versions:
            if name == forced:
                return name, p
        return forced, None
    if not versions:
        return None, None
    # 最高版本优先；同版本时 LOCALAPPDATA（pref=0）优先
    vkey, pref, name, p = max(versions, key=lambda x: (x[0], -x[1]))
    return name, p


# ---------------------------------------------------------------- 草稿根

def _read_global_setting() -> dict[str, str]:
    """极简 ini 读取：只关心 [General] 段的 key=value"""
    p = LOCALAPPDATA / "JianyingPro/User Data/Config/globalSetting"
    out: dict[str, str] = {}
    if not p.is_file():
        return out
    try:
        for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
            if "=" in line and not line.lstrip().startswith(("[", ";", "#")):
                k, _, v = line.partition("=")
                out[k.strip()] = v.strip()
    except OSError:
        pass
    return out


def find_drafts_root() -> tuple[Path | None, str]:
    """返回 (草稿根, 来源说明)"""
    env = os.environ.get("JY_DRAFTS_ROOT")
    if env and Path(env).is_dir():
        return Path(env), "环境变量 JY_DRAFTS_ROOT"

    cfg = _read_global_setting()
    for key in ("currentCustomDraftPath", "customDraftPath", "draftPath"):
        v = cfg.get(key)
        if v:
            p = Path(v.replace("\\\\", "\\"))
            if p.is_dir():
                return p, f"globalSetting:{key}"

    for p in (LOCALAPPDATA / "JianyingPro/User Data/Projects/com.lveditor.draft",
              HOME / "Documents/JianyingPro Drafts",
              HOME / "Documents/剪映草稿"):
        if p.is_dir():
            return p, "默认草稿目录"

    # 最后兜底：在常见盘符根下浅层搜 root_meta_info.json
    for drive in ("C:/", "D:/", "E:/", "F:/"):
        d = Path(drive)
        if not d.exists():
            continue
        try:
            for hit in d.glob("*/**/root_meta_info.json"):
                return hit.parent, f"扫描命中 {hit}"
        except OSError:
            pass
    return None, "未找到"


# ---------------------------------------------------------------- skill / python / ffmpeg

def find_skill_scripts() -> tuple[Path | None, Path | None]:
    """返回 (skill 根, scripts 目录)"""
    env = os.environ.get("JY_SKILL_SCRIPTS")
    if env:
        p = Path(env)
        return (p.parent if p.name == "scripts" else p), (p if p.name == "scripts" else p / "scripts")

    base = HOME / ".dsh/skills"
    cands = []
    if base.is_dir():
        for d in base.iterdir():
            if d.is_dir() and "jianying" in d.name.lower():
                cands.append(d)
    # 名字带 11-5 的优先（适配高版本），其余按名字排
    for c in sorted(cands, key=lambda x: ("11-5" not in x.name, x.name)):
        for hit in sorted(c.glob("**/scripts/jyai")):
            if hit.is_dir():
                return hit.parent.parent, hit.parent
    return None, None


def find_ffmpeg() -> str | None:
    """优先 pipeline/config.json 的 paths.ffmpeg，其次 PATH"""
    cfg = Path(__file__).resolve().parent.parent / "lbr-promo/pipeline/config.json"
    try:
        data = json.loads(cfg.read_text(encoding="utf-8"))
        p = data.get("paths", {}).get("ffmpeg")
        if p and Path(p).exists():
            return str(p)
    except (OSError, ValueError):
        pass
    import shutil
    return shutil.which("ffmpeg")


def check_pyjianyingdraft() -> str | None:
    try:
        import pyJianYingDraft  # noqa: F401
    except Exception:
        return None
    for mod in ("pyJianYingDraft", "pyJianYingDraft._version"):
        try:
            import importlib
            v = getattr(importlib.import_module(mod), "__version__", None)
            if v:
                return str(v)
        except Exception:
            pass
    try:
        from importlib.metadata import version
        return version("pyJianYingDraft")
    except Exception:
        return "installed"


# ---------------------------------------------------------------- 汇总

def discover() -> dict:
    version, ver_dir = find_app_version()
    drafts, drafts_src = find_drafts_root()
    skill, scripts = find_skill_scripts()
    exe = None
    if ver_dir:
        for name in ("JianyingPro.exe", "剪映.exe"):
            if (ver_dir / name).is_file():
                exe = ver_dir / name
                break

    return {
        "app_version": version,
        "app_dir": str(ver_dir) if ver_dir else None,
        "jianying_exe": str(exe) if exe else None,
        "drafts_root": str(drafts) if drafts else None,
        "drafts_root_source": drafts_src,
        "skill_root": str(skill) if skill else None,
        "skill_scripts": str(scripts) if scripts else None,
        "python": sys.executable,
        "ffmpeg": find_ffmpeg(),
        "pyjianyingdraft": check_pyjianyingdraft(),
        "new_version": os.environ.get("JY_DRAFT_NEW_VERSION", "110.0.0"),
    }


def write_env(info: dict) -> Path:
    lines = [
        "# 由 tools/jy_env.py --write-env 自动生成，可手工改；改完重跑 jy.cmd 即生效",
        "# 换设备时删掉本文件，跑一次: python tools\\jy_env.py --write-env",
        f"NEW_VERSION={info['new_version']}",
        f"DRAFTS_ROOT={info['drafts_root'] or ''}",
        f"APP_VERSION={info['app_version'] or ''}",
        f"APP_DIR={info['app_dir'] or ''}",
        f"SKILL_SCRIPTS={info['skill_scripts'] or ''}",
    ]
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return ENV_FILE


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--write-env", action="store_true")
    ap.add_argument("--check", action="store_true", help="缺必需项返回 1")
    a = ap.parse_args()

    info = discover()
    if a.json:
        print(json.dumps(info, ensure_ascii=False, indent=2))
    elif not a.write_env and not a.check:
        w = max(len(k) for k in info)
        for k, v in info.items():
            print(f"{k.ljust(w)} : {v}")

    if a.write_env:
        p = write_env(info)
        if not a.json:
            print(f"\n已写入 {p}")
            print("提示：jy.cmd 会自动读这个文件；换设备只需重跑本命令。")

    if a.check:
        missing = [k for k in ("app_version", "drafts_root", "skill_scripts", "pyjianyingdraft")
                   if not info.get(k)]
        if missing:
            print("缺失：" + ", ".join(missing), file=sys.stderr)
            if "pyjianyingdraft" in missing:
                print("  修复：pip install pyJianYingDraft==0.3.1", file=sys.stderr)
            if "skill_scripts" in missing:
                print("  修复：把 jianying-editor-11-5 skill 放到 ~/.dsh/skills/ 或设 JY_SKILL_SCRIPTS", file=sys.stderr)
            if "drafts_root" in missing:
                print("  修复：先在剪映里随便建一个草稿，或设 JY_DRAFTS_ROOT", file=sys.stderr)
            return 1
        print("OK：全部必需项就绪")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
