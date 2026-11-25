# -*- coding: utf-8 -*-
"""冒烟自检：不联网、不渲染、不花钱，30 秒内回答"这条链现在还是好的吗"。

对标 capcut-mate 的 tests/：我们没有完整单测，但至少要有一个"改完代码跑一下"的把手。

    python lbr-promo\\pipeline\\selftest.py
    python lbr-promo\\pipeline\\selftest.py --verbose

退出码 0 = 全过（SKIP 不算失败）；1 = 有 FAIL。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROMO = ROOT / "lbr-promo"
PY = sys.executable

RESULTS: list[tuple[str, str, str]] = []  # (level, name, detail)


def ok(name: str, detail: str = "") -> None:
    RESULTS.append(("PASS", name, detail))


def bad(name: str, detail: str) -> None:
    RESULTS.append(("FAIL", name, detail))


def skip(name: str, detail: str) -> None:
    RESULTS.append(("SKIP", name, detail))


def run(args: list[str], timeout: int = 120) -> tuple[int, str]:
    try:
        p = subprocess.run(args, cwd=str(ROOT), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except (OSError, subprocess.TimeoutExpired) as exc:  # noqa: BLE001
        return 1, str(exc)


# ------------------------------------------------------------------ 各项检查

def t_config() -> None:
    path = PROMO / "pipeline" / "config.json"
    if not path.is_file():
        return bad("config.json 存在", str(path))
    try:
        cfg = json.loads(path.read_text(encoding="utf-8-sig"))
    except ValueError as exc:
        return bad("config.json 可解析", str(exc))
    need = ("project", "paths", "text", "voice", "video", "card", "check")
    miss = [k for k in need if k not in cfg]
    if miss:
        return bad("config.json 七组齐全", "缺 " + ", ".join(miss))
    ok("config.json 七组齐全", f"{len(cfg)} 组")


def t_film() -> None:
    path = PROMO / "src" / "data" / "film.json"
    if not path.is_file():
        return skip("film.json 结构", "还没 build 过，先跑 build_film.py")
    try:
        film = json.loads(path.read_text(encoding="utf-8-sig"))
    except ValueError as exc:
        return bad("film.json 可解析", str(exc))
    lines = film.get("lines") or []
    panels = film.get("panels") or []
    if not lines:
        return bad("film.json 有 lines", "0 句")
    total = float(film.get("totalSeconds") or 0)
    if total <= 0:
        return bad("film.json totalSeconds > 0", str(total))
    if not film.get("voice"):
        return bad("film.json 有 voice", "空")
    covered = sum(1 for ln in lines if ln.get("panel"))
    ok("film.json 结构", f"{len(lines)} 句 / {len(panels)} 屏 / {covered} 句进 panel / {total:.1f}s")


def t_audit() -> None:
    code, out = run([PY, str(PROMO / "pipeline" / "audit.py")])
    tail = [ln for ln in out.strip().splitlines() if ln.strip()][-1:] or [""]
    if code == 0:
        ok("audit.py 无 FAIL", tail[0].strip())
    elif "FAIL" in out:
        bad("audit.py 无 FAIL", tail[0].strip() or "有 FAIL，见 audit 输出")
    else:
        skip("audit.py", f"exit={code}（可能没有 film.json）")


def t_spec() -> None:
    if not (PROMO / "src" / "data" / "film.json").is_file():
        return skip("film.json → spec", "没有 film.json")
    spec_out = ROOT / "qa2" / "_selftest-spec.json"
    spec_out.parent.mkdir(exist_ok=True)
    code, out = run([PY, str(ROOT / "tools" / "jy_from_film.py"),
                     "--spec-out", str(spec_out)])
    if code != 0 or not spec_out.is_file():
        return bad("film.json → spec", out.strip().splitlines()[-1] if out.strip() else f"exit={code}")
    spec = json.loads(spec_out.read_text(encoding="utf-8-sig"))
    tracks = spec.get("tracks") or []
    items = sum(len(t.get("items") or []) for t in tracks)
    ok("film.json → spec", f"{len(tracks)} 轨 / {items} 段")

    code2, out2 = run([PY, str(ROOT / "tools" / "jy_draft.py"), str(spec_out), "--validate"])
    if code2 == 0:
        ok("spec 契约校验", out2.strip().splitlines()[-1])
    else:
        bad("spec 契约校验", out2.strip().splitlines()[-1] if out2.strip() else f"exit={code2}")
    spec_out.unlink(missing_ok=True)


def t_env() -> None:
    code, out = run([PY, str(ROOT / "tools" / "jy_env.py"), "--check"])
    if code != 0:
        return bad("jy_env --check", out.strip().splitlines()[-1] if out.strip() else f"exit={code}")
    lines = [ln for ln in out.strip().splitlines() if ln.strip()]
    version_line = next((ln for ln in lines if "版本能力表" in ln), lines[-1])
    if "未登记" in version_line:
        return skip("剪映版本能力表", version_line)
    ok("剪映版本能力表", version_line)


def t_audio() -> None:
    v = PROMO / "public" / "audio"
    if not v.is_dir():
        return skip("配音文件", "public/audio 不存在")
    wavs = sorted(v.glob("*.wav"))
    if not wavs:
        return skip("配音文件", "没有 wav")
    newest = max(wavs, key=lambda p: p.stat().st_mtime)
    ok("配音文件", f"{len(wavs)} 个，最新 {newest.name} {newest.stat().st_size/1e6:.1f}MB")


def t_draft() -> None:
    try:
        sys.path.insert(0, str(ROOT / "tools"))
        import jy_env  # noqa: PLC0415

        root = jy_env.discover().get("drafts_root")
    except Exception as exc:  # noqa: BLE001
        return skip("最近草稿可读", f"探测失败：{exc}")
    if not root or not Path(root).is_dir():
        return skip("最近草稿可读", "没找到草稿根")
    drafts = [p for p in Path(root).iterdir() if p.is_dir() and (p / "draft_content.json").is_file()]
    if not drafts:
        return skip("最近草稿可读", "草稿根下没有草稿")
    newest = max(drafts, key=lambda p: p.stat().st_mtime)
    code, out = run([PY, str(ROOT / "tools" / "jy_check.py"), str(newest)], timeout=180)
    if code != 0:
        return bad("最近草稿可读", f"{newest.name}: exit={code}")
    local_line = next((ln for ln in out.splitlines() if "素材本地化" in ln), "")
    ok("最近草稿可读", f"{newest.name} · {local_line.strip() or '未见本地化栏'}")


CHECKS = [t_config, t_film, t_audit, t_spec, t_env, t_audio, t_draft]


def main() -> int:
    ap = argparse.ArgumentParser(description="流水线冒烟自检")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()

    for fn in CHECKS:
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            bad(fn.__name__, f"未捕获异常：{exc}")

    width = max(len(n) for _, n, _ in RESULTS) + 2
    for level, name, detail in RESULTS:
        mark = {"PASS": "✓", "FAIL": "✗", "SKIP": "·"}[level]
        print(f"{mark} {name.ljust(width)} {detail}")

    n_fail = sum(1 for lv, _, _ in RESULTS if lv == "FAIL")
    n_skip = sum(1 for lv, _, _ in RESULTS if lv == "SKIP")
    print(f"\n{len(RESULTS)} 项：{len(RESULTS)-n_fail-n_skip} 通过 / {n_fail} 失败 / {n_skip} 跳过")
    if a.verbose and n_fail:
        print("失败项请对照 pipeline/TROUBLES.md")
    return 1 if n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
