"""素材检索：先找现成素材，找不到再用 AI 生成（tools/img.py）。

为什么默认走 bing：
  本机无代理，commons/openverse/pexels 直连超时；cn.bing.com/images 可达（http 200），
  且无需 key，是当前"先找素材"的稳定通道。有代理时可切 --source commons/openverse。

用法：
  # 1) 搜
  python tools/stock.py search "男生 瘫坐 沙发 手机 卡通" --n 12 --json qa2/q-sofa.json
  # 2) 先看拼图，判断"这张到底对不对场景"（关键一步，不要跳过）
  python tools/stock.py preview --json qa2/q-sofa.json --out qa2/q-sofa.jpg
  # 3) 只下载对得上的那几张
  python tools/stock.py save 2 7 --json qa2/q-sofa.json --out lbr-promo/public/textures/stock --name sofa

来源：
  bing      cn.bing.com/images（无需 key，国内可达，噪声大→必须 preview 复核）
  commons   Wikimedia Commons（无需 key，需外网）
  openverse Openverse 聚合（无需 key，需外网）
  pexels    Pexels（需 PEXELS_API_KEY）

铁律：
  - 素材必须对上这句话的场景；对不上宁可换关键词，也不硬塞
  - 同一张图不得跨场景复用；同场景连用 ≤3 句
  - 下载后统一转 jpg，文件名带场景语义（sofa-01 / metro-02），便于后续查重
"""
import argparse
import html as html_lib
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36"}
S = requests.Session()
S.trust_env = False  # 系统代理未开启，直接连

_HERE = Path(__file__).resolve()
for _base in (_HERE.parents[1], _HERE.parents[1] / "lbr-promo", _HERE.parent, _HERE.parent / "lbr-promo"):
    if (_base / "pipeline" / "env.py").is_file():
        sys.path.insert(0, str(_base / "pipeline"))
        break
import env  # noqa: E402  统一环境发现（路径/ffmpeg/python 都从这来）

FFMPEG = env.ffmpeg()


def _ok(w, h):
    if not w or not h:
        return False
    if w < 800:
        return False
    return 0.5 <= w / h <= 2.2


def search_bing(q, n):
    """解析 bing 图片搜索页里 class=iusc 的 m="{...}" 属性，比 async 接口可靠。"""
    url = "https://cn.bing.com/images/search"
    params = {"q": q, "form": "HDRSC2", "first": 1, "tsc": "ImageBasicHover"}
    r = S.get(url, params=params, headers=UA, timeout=25)
    r.raise_for_status()
    html = r.text
    out, seen = [], set()
    for raw in re.findall(r'm="(\{&quot;.*?\})"', html):
        try:
            meta = json.loads(html_lib.unescape(raw))
        except Exception:  # noqa: BLE001
            continue
        u = (meta.get("murl") or "").replace("\\/", "/")
        if not u or u in seen:
            continue
        seen.add(u)
        out.append(
            {
                "title": (meta.get("t") or "")[:80],
                "w": None,
                "h": None,
                "license": "网络图（自查版权）",
                "page": meta.get("purl") or ("https://cn.bing.com/images/search?q=" + urllib.parse.quote(q)),
                "url": u,
            }
        )
        if len(out) >= max(n * 2, n):
            break
    if not out:  # 兜底：老式 murl 正则
        for u in re.findall(r'murl&quot;:&quot;(.*?)&quot;', html)[: n * 2]:
            u = u.replace("\\/", "/")
            if u in seen:
                continue
            seen.add(u)
            out.append({"title": "", "w": None, "h": None, "license": "网络图（自查版权）", "page": "", "url": u})
    return out


def search_commons(q, n):
    url = (
        "https://commons.wikimedia.org/w/api.php?action=query&format=json"
        "&generator=search&gsrnamespace=6&gsrlimit=%d"
        "&gsrsearch=%s&prop=imageinfo&iiprop=url|size|extmetadata&iiurlwidth=1280"
        % (n * 2, urllib.parse.quote(q))
    )
    r = S.get(url, headers=UA, timeout=40)
    r.raise_for_status()
    pages = (r.json().get("query") or {}).get("pages") or {}
    out = []
    for p in pages.values():
        info = (p.get("imageinfo") or [{}])[0]
        if not _ok(info.get("width"), info.get("height")):
            continue
        meta = info.get("extmetadata") or {}
        out.append(
            {
                "title": p.get("title", ""),
                "w": info.get("width"),
                "h": info.get("height"),
                "license": re.sub("<[^>]+>", "", (meta.get("LicenseShortName") or {}).get("value", "")),
                "page": info.get("descriptionurl", ""),
                "url": info.get("thumburl") or info.get("url"),
            }
        )
    return out[:n]


def search_openverse(q, n):
    url = "https://api.openverse.org/v1/images/"
    params = {"q": q, "page_size": n * 2, "license_type": "commercial"}
    last = ""
    for _ in range(2):
        try:
            r = S.get(url, params=params, headers=UA, timeout=30)
            if r.status_code == 200:
                break
            last = "HTTP %s" % r.status_code
        except Exception as e:  # noqa: BLE001
            last = str(e)
        time.sleep(2)
    else:
        raise RuntimeError("openverse 不可达：%s" % last)
    out = []
    for it in r.json().get("results", []):
        if not _ok(it.get("width"), it.get("height")):
            continue
        out.append(
            {
                "title": it.get("title") or "",
                "w": it.get("width"),
                "h": it.get("height"),
                "license": "%s %s" % (it.get("license") or "", it.get("license_version") or ""),
                "page": it.get("foreign_landing_url", ""),
                "url": it.get("url"),
            }
        )
    return out[:n]


def search_pexels(q, n):
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        raise RuntimeError("缺 PEXELS_API_KEY")
    r = S.get(
        "https://api.pexels.com/v1/search",
        params={"query": q, "per_page": n, "orientation": "landscape"},
        headers={"Authorization": key},
        timeout=30,
    )
    r.raise_for_status()
    out = []
    for it in r.json().get("photos", []):
        if not _ok(it.get("width"), it.get("height")):
            continue
        out.append(
            {
                "title": (it.get("alt") or "")[:80],
                "w": it.get("width"),
                "h": it.get("height"),
                "license": "Pexels License",
                "page": it.get("url"),
                "url": (it.get("src") or {}).get("large2x"),
            }
        )
    return out[:n]


SOURCES = {"bing": search_bing, "commons": search_commons, "openverse": search_openverse, "pexels": search_pexels}


def cmd_search(a):
    hits = SOURCES[a.source](a.q, a.n)
    if not hits:
        print("无结果：换成「主体+动作+场景+风格」的关键词，或换 --source")
        return 1
    payload = {"query": a.q, "source": a.source, "hits": hits}
    if a.json:
        d = os.path.dirname(os.path.abspath(a.json))
        if d:
            os.makedirs(d, exist_ok=True)
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
        print("已写 %s（%d 条）" % (a.json, len(hits)))
    for i, h in enumerate(hits, 1):
        print("%2d %-10s %s" % (i, h["license"][:10], (h["title"] or h["url"])[:70]))
    return 0


def cmd_preview(a):
    from PIL import Image, ImageDraw, ImageFont

    with open(a.json, encoding="utf-8") as f:
        hits = json.load(f)["hits"]
    tmp = os.path.join(os.path.dirname(os.path.abspath(a.out)) or ".", "_prev")
    os.makedirs(tmp, exist_ok=True)
    CW, CH = 360, 240
    cols = a.cols
    rows = (len(hits) + cols - 1) // cols
    sheet = Image.new("RGB", (CW * cols, (CH + 22) * rows), (16, 16, 16))
    d = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.load_default(size=15)
    except Exception:  # noqa: BLE001
        font = None
    got = 0
    for i, h in enumerate(hits):
        p = os.path.join(tmp, "%03d.img" % i)
        x, y = (i % cols) * CW, (i // cols) * (CH + 22)
        try:
            with S.get(h["url"], headers={**UA, "Referer": "https://cn.bing.com/"}, timeout=25, stream=True) as r:
                r.raise_for_status()
                with open(p, "wb") as f:
                    for chunk in r.iter_content(1 << 15):
                        f.write(chunk)
            im = Image.open(p).convert("RGB")
            im.thumbnail((CW - 6, CH - 6))
            sheet.paste(im, (x + 3, y + 3))
            got += 1
        except Exception:  # noqa: BLE001
            d.text((x + 8, y + 8), "#%d 取图失败" % (i + 1), fill=(255, 90, 90), font=font)
        d.text((x + 6, y + CH - 2), "#%d %s" % (i + 1, (h["title"] or "")[:22]), fill=(255, 210, 80), font=font)
    sheet.save(a.out, quality=88)
    print("preview -> %s（成功 %d/%d）" % (a.out, got, len(hits)))
    return 0


def cmd_save(a):
    with open(a.json, encoding="utf-8") as f:
        hits = json.load(f)["hits"]
    os.makedirs(a.out, exist_ok=True)
    for i in a.idx:
        h = hits[i - 1]
        dst = os.path.join(a.out, "%s-%02d.jpg" % (a.name, i))
        raw = dst + ".src"
        with S.get(h["url"], headers={**UA, "Referer": "https://cn.bing.com/"}, timeout=60, stream=True) as r:
            r.raise_for_status()
            with open(raw, "wb") as f:
                for chunk in r.iter_content(1 << 16):
                    f.write(chunk)
        subprocess.run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", raw, "-q:v", "3", dst], check=True)
        os.remove(raw)
        print("saved %s  <- %s" % (dst, (h["title"] or h["url"])[:50]))
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search")
    s.add_argument("q")
    s.add_argument("--source", default="bing", choices=list(SOURCES))
    s.add_argument("--n", type=int, default=12)
    s.add_argument("--json")
    s.set_defaults(func=cmd_search)

    p = sub.add_parser("preview")
    p.add_argument("--json", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--cols", type=int, default=4)
    p.set_defaults(func=cmd_preview)

    g = sub.add_parser("save")
    g.add_argument("idx", nargs="+", type=int)
    g.add_argument("--json", required=True)
    g.add_argument("--out", required=True)
    g.add_argument("--name", default="stock")
    g.set_defaults(func=cmd_save)

    a = ap.parse_args()
    sys.exit(a.func(a))


if __name__ == "__main__":
    main()
