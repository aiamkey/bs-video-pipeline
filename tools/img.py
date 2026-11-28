"""生图 · 多规范统一入口。

用哪家、用谁的 key，全在 `lbr-promo/pipeline/config.json` 的 `images` 段，
或者命令行临时覆盖。默认走百炼（内置可用），也可以换成任何 OpenAI 兼容中转站。

用法:
  python tools/img.py "提示词" out.jpg
  python tools/img.py "提示词" out.jpg --provider openai --model gpt-image-1.5 --quality high
  python tools/img.py --check                      # 只验证 key 与连通性

key 的三种给法（优先级从高到低）:
  1. --key sk-xxx
  2. 环境变量（config.images.api_key_env 指定的名字，如 OPENAI_API_KEY）
  3. config.images.api_key 直接写死（本机自用可以，别提交）

支持的规范:
  openai    —— OpenAI 标准 /v1/images/generations，兼容 one-api / new-api / ohmygpt 等中转
  dashscope —— 阿里百炼 wanx（异步任务 + 轮询）
  ark       —— 火山方舟 doubao-seedream（/api/v3/images/generations）

GPT 系列（gpt-image-1 / 1.5 / mini）注意三件事，本文件已处理前两件:
  * size 只接受 1024x1024 / 1536x1024 / 1024x1536 / auto，
    流水线的 1280x720 会自动映射到 1536x1024，落盘后再中心裁回 16:9。
  * 返回默认是 b64_json 而不是 url，save() 两种都吃。
  * 没有 seed 参数——一致性只能靠 character DNA 文本或 image-edit 参考图，
    不像 wanx 能用固定 seed 锁同一个人。

中转站 base_url 三种填法都收（qa2/gpt/relay.json 里直接填）:
  https://relay.example.com
  https://relay.example.com/v1
  https://relay.example.com/v1/images/generations
openai_base() 统一归一成不带 /v1 的根，再拼 /v1/images/generations，
避免中转站文档写 /v1 时变成 /v1/v1/images/generations 的 404。
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
CFG_PATH = ROOT / "lbr-promo" / "pipeline" / "config.json"
RELAY_PATH = ROOT / "qa2" / "gpt" / "relay.json"

DEFAULT = {
    "provider": "dashscope",
    "model": "wanx2.1-t2i-turbo",
    "size": "1280x720",
    "api_key": "",
    "api_key_env": "DASHSCOPE_API_KEY",
    "base_url": "",
    "timeout": 180,
    "seed": None,
    "quality": "",
    # apimart / 其他异步中转站专用（同步中转站不生效）
    "resolution": "",       # -ext 档填 1K / 2K / 4K；留空不传
    "poll_interval": 2,     # 轮询间隔秒
    "poll_max": 90,         # 最多轮询次数
}


def load_cfg() -> dict:
    c = dict(DEFAULT)
    if CFG_PATH.exists():
        cfg = json.loads(CFG_PATH.read_text(encoding="utf-8-sig"))
        c.update(cfg.get("images", {}))
    # relay.json 是用户填中转站的地方；只认真正的配置键，跳过 _说明 / _填法 这类文档字段。
    # 关键：base_url 与 api_key 都空 = 用户还没填，整个 relay 不生效，继续走 config.json 的百炼。
    # 否则清空后 provider 会被 relay 里的默认 openai 覆盖，百炼通道就断了。
    if RELAY_PATH.exists():
        r = json.loads(RELAY_PATH.read_text(encoding="utf-8-sig"))
        base_filled = bool((r.get("base_url") or "").strip())
        key_filled = bool((r.get("api_key") or "").strip())
        if base_filled or key_filled:
            KEYS = {"provider", "model", "size", "base_url", "api_key", "api_key_env",
                    "timeout", "quality", "passthrough_size", "response_format", "seed",
                    "resolution", "version", "poll_interval", "poll_max"}
            for k in KEYS:
                v = r.get(k)
                if v not in ("", None):
                    c[k] = v
            # 填了中转地址就按 OpenAI 兼容规范走，key 也从 OPENAI_API_KEY 读
            if base_filled:
                c["provider"] = r.get("provider") or "openai"
                c["api_key_env"] = r.get("api_key_env") or "OPENAI_API_KEY"
            k = (r.get("api_key") or "").strip()
            if k:
                c["api_key"] = k
    return c


def resolve_key(cfg: dict, cli_key: str | None, strict: bool = True) -> str:
    if cli_key:
        return cli_key
    env = os.environ.get(cfg.get("api_key_env") or "", "")
    if env:
        return env
    if cfg.get("api_key"):
        return cfg["api_key"]
    if not strict:
        return ""                     # --check 用：没填也能把配置打印出来
    raise SystemExit(
        f"缺少生图 key。四种给法（推荐第 1 种）：\n"
        f"  1) 填 {RELAY_PATH} 的 api_key（或用 qa2/gpt/fill.ps1 / relay_form.py）\n"
        f"  2) --key sk-xxx\n"
        f"  3) 设环境变量 {cfg.get('api_key_env')}\n"
        f"  4) 写进 {CFG_PATH} 的 images.api_key"
    )


def save(url: str | None, b64: str | None, out: Path) -> str:
    out.parent.mkdir(parents=True, exist_ok=True)
    if b64:
        data = base64.b64decode(b64)
    elif url:
        data = requests.get(url, timeout=180).content
    else:
        raise RuntimeError("返回里既没有 url 也没有 b64_json")
    # 中转站常见：声明 .jpg 但返回 PNG，或反过来。按魔数识别后转码成调用方
    # 指定的扩展名，避免 read_image / Remotion 因「扩展名与内容不符」报错。
    actual = None
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        actual, fmt = "PNG", "PNG"
    elif data[:3] == b"\xff\xd8\xff":
        actual, fmt = "JPEG", "JPEG"
    elif data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        actual, fmt = "WEBP", "WEBP"
    elif data[:6] in (b"GIF87a", b"GIF89a"):
        actual, fmt = "GIF", "GIF"
    else:
        actual, fmt = "?", None
    suf = out.suffix.lower()
    target = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG",
              ".webp": "WEBP", ".gif": "GIF"}.get(suf)
    note = ""
    if target and fmt and target != fmt:
        try:
            import io
            from PIL import Image
            im = Image.open(io.BytesIO(data))
            if target == "JPEG":
                im = im.convert("RGB")
            buf = io.BytesIO()
            im.save(buf, format=target)
            data = buf.getvalue()
            note = f", 已从 {fmt} 转码为 {target}"
        except Exception:
            out = out.with_suffix(".png" if fmt == "PNG" else ".jpg")
            note = f", 返回 {fmt}，改存 {out.name}"
    out.write_bytes(data)
    return f"{out} ({len(data)//1024} KB{note})"


# ---------- OpenAI 规范 ----------
GPT_ALLOWED = {"1024x1024", "1536x1024", "1024x1536", "auto"}


def openai_base(base_url: str) -> str:
    """中转站 base_url 三种写法归一成一个不带 /v1 的 origin。

      https://relay.com                      -> https://relay.com
      https://relay.com/v1                    -> https://relay.com
      https://relay.com/v1/images/generations -> https://relay.com
      ""                                     -> https://api.openai.com
    """
    b = (base_url or "https://api.openai.com").strip().rstrip("/")
    for suffix in ("/v1/images/generations", "/images/generations", "/v1"):
        if b.endswith(suffix):
            b = b[: -len(suffix)].rstrip("/")
            break
    return b or "https://api.openai.com"


def openai_size(size: str) -> str:
    """gpt-image-* 不认 1280x720；按方向映射到最接近的合法档。

    落盘是 3:2 (1536x1024)，要 16:9 得再中心裁，见 qa2/gpt/gen_gpt_bottoms.py。
    apimart 等异步中转站用比例字符串（"16:9" / "1:1"）而非像素，这类直接透传。
    中转站若支持 1280x720 等自定义尺寸，可在 relay.json 设 passthrough_size=true。
    """
    if size in GPT_ALLOWED:
        return size
    # "16:9" / "9:16" / "auto" 这类比例字符串：中转站自己认，别映射成像素
    if ":" in size and "x" not in size.lower():
        return size
    if size == "auto":
        return size
    try:
        w, h = (int(x) for x in size.lower().split("x"))
    except Exception:
        return "1536x1024"
    return "1536x1024" if w >= h else "1024x1536"


def extract_image(response: dict) -> tuple[str | None, str | None]:
    """兼容多类中转返回：data[0].url / b64_json、顶层 url / b64_json、
    Gemini 风格 candidates[].content.parts[].inlineData.data，
    以及 apimart 完成态 data.result.images[0].url（字符串或数组）。"""
    # apimart 异步任务完成态：data.result.images[0].url
    data0 = response.get("data")
    if isinstance(data0, dict) and isinstance(data0.get("result"), dict):
        imgs = data0["result"].get("images")
        if isinstance(imgs, list) and imgs and isinstance(imgs[0], dict):
            u = imgs[0].get("url")
            if isinstance(u, list):
                u = u[0] if u else None
            if u:
                return u, None
    data = response.get("data")
    if isinstance(data, list) and data:
        item = data[0] if isinstance(data[0], dict) else {}
        return item.get("url"), item.get("b64_json")
    if isinstance(data, dict):
        return data.get("url"), data.get("b64_json")
    if response.get("url"):
        return response["url"], None
    if response.get("b64_json"):
        return None, response["b64_json"]
    try:
        parts = response["candidates"][0]["content"]["parts"]
        for p in parts:
            if "inlineData" in p:
                return None, p["inlineData"]["data"]
    except (KeyError, IndexError, TypeError):
        pass
    return None, None


def task_submission(response: dict) -> tuple[str | None, str | None]:
    """识别「异步任务已提交」的返回，给出 (task_id, poll_url)。

    apimart 两种提交态：
      {"code":202,"data":{"id":"task_xxx","status":"pending","poll_url":"/v1/tasks/task_xxx"}}
      {"code":200,"data":[{"status":"submitted","task_id":"task_xxx"}]}
    同步返回（data[0].url / b64_json）不算任务。
    """
    data = response.get("data")
    if isinstance(data, dict) and (data.get("id") or data.get("task_id")) and \
            ("status" in data or "poll_url" in data):
        tid = data.get("id") or data.get("task_id")
        # 已经带结果就不算「待轮询」
        if not data.get("result"):
            return tid, data.get("poll_url")
    if isinstance(data, list) and data and isinstance(data[0], dict):
        it = data[0]
        if it.get("task_id") or (it.get("status") in ("submitted", "pending", "processing", "queued")):
            return it.get("task_id") or it.get("id"), it.get("poll_url")
    if response.get("task_id"):
        return response["task_id"], response.get("poll_url")
    return None, None


def poll_task(base: str, key: str, task_id: str, poll_url: str | None, cfg: dict) -> dict:
    """轮询 GET /v1/tasks/{task_id} 直到完成，返回完成态的完整 JSON。

    base 是不带 /v1 的 origin（如 https://api.apimart.ai）；
    apimart 的 poll_url 一般是 "/v1/tasks/xxx"（已含 /v1），直接接在 base 后面。
    """
    origin = base.rstrip("/")
    if poll_url:
        if poll_url.startswith("http"):
            url = poll_url
        elif poll_url.startswith("/v1"):
            url = origin + poll_url
        elif poll_url.startswith("/"):
            url = origin + "/v1" + poll_url
        else:
            url = origin + "/v1/" + poll_url
    else:
        url = f"{origin}/v1/tasks/{task_id}"
    headers = {"Authorization": f"Bearer {key}"}
    interval = float(cfg.get("poll_interval") or 2)
    tries = int(cfg.get("poll_max") or 90)
    for _ in range(tries):
        time.sleep(interval)
        g = requests.get(url, headers=headers, timeout=30)
        if g.status_code != 200:
            raise RuntimeError(f"轮询 {g.status_code} {g.text[:300]}")
        j = g.json()
        d = j.get("data") if isinstance(j.get("data"), dict) else j
        st = (d.get("status") or "").lower()
        if st in ("completed", "succeeded", "success") or (d.get("progress") == 100 and d.get("result")):
            return j
        if st in ("failed", "cancelled", "canceled", "error"):
            raise RuntimeError(f"生图任务失败: {json.dumps(d.get('error') or d, ensure_ascii=False)[:300]}")
    raise RuntimeError(f"轮询超时（{tries}×{interval}s），task_id={task_id}")


def gen_openai(prompt: str, out: Path, cfg: dict, key: str, model: str, size: str) -> str:
    base = openai_base(cfg.get("base_url") or "")
    url = f"{base}/v1/images/generations"
    # 中转站若支持任意尺寸（如 seedream / 自定义中转），设 passthrough_size=true 就不映射。
    # apimart 用比例字符串 "16:9"，openai_size() 已直接透传，不映射成像素。
    sz = size if cfg.get("passthrough_size") else openai_size(size)
    payload = {"model": model, "prompt": prompt, "n": 1, "size": sz}
    q = (cfg.get("quality") or "").strip()
    if q:
        payload["quality"] = q                       # low / medium / high（GPT 官方档）
    # apimart -ext / gpt-image-2 档：resolution 1K/2K/4K、version flare/sunburst
    if cfg.get("resolution"):
        payload["resolution"] = cfg["resolution"]
    if cfg.get("version"):
        payload["version"] = cfg["version"]
    # 有些中转要求响应里带图片，有些不接受 response_format；默认不带最稳。
    if cfg.get("response_format"):
        payload["response_format"] = cfg["response_format"]
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    r = requests.post(url, headers=headers, json=payload, timeout=cfg["timeout"])
    if r.status_code not in (200, 201, 202):
        raise RuntimeError(f"{r.status_code} {r.text[:400]}")
    j = r.json()
    # 异步中转（apimart 等）：提交只回 task_id，要轮询到完成态才有图
    tid, poll_url = task_submission(j)
    if tid:
        j = poll_task(base, key, tid, poll_url, cfg)
    u, b = extract_image(j)
    if not u and not b:
        raise RuntimeError(f"返回里找不到图片：{json.dumps(j, ensure_ascii=False)[:400]}")
    return save(u, b, out)


# ---------- 百炼 wanx ----------
def gen_dashscope(prompt: str, out: Path, cfg: dict, key: str, model: str, size: str) -> str:
    base = (cfg.get("base_url") or "https://dashscope.aliyuncs.com").rstrip("/")
    create = f"{base}/api/v1/services/aigc/text2image/image-synthesis"
    h = {"Authorization": f"Bearer {key}", "Content-Type": "application/json",
         "X-DashScope-Async": "enable"}
    params = {"size": size.replace("x", "*"), "n": 1, "prompt_extend": True}
    if cfg.get("seed") is not None:
        params["seed"] = int(cfg["seed"])
    payload = {"model": model, "input": {"prompt": prompt}, "parameters": params}
    r = requests.post(create, headers=h, json=payload, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"{r.status_code} {r.text[:400]}")
    task = r.json()["output"]["task_id"]
    for _ in range(90):
        time.sleep(2)
        g = requests.get(f"{base}/api/v1/tasks/{task}",
                         headers={"Authorization": f"Bearer {key}"}, timeout=30)
        st = g.json()["output"]
        if st["task_status"] == "SUCCEEDED":
            return save(st["results"][0]["url"], None, out)
        if st["task_status"] in ("FAILED", "CANCELED", "UNKNOWN"):
            raise RuntimeError(f"task {st}")
    raise RuntimeError("timeout")


# ---------- 火山方舟 seedream ----------
def gen_ark(prompt: str, out: Path, cfg: dict, key: str, model: str, size: str) -> str:
    base = (cfg.get("base_url") or "https://ark.cn-beijing.volces.com").rstrip("/")
    url = f"{base}/api/v3/images/generations"
    payload = {"model": model, "prompt": prompt, "size": size, "n": 1,
               "response_format": "url"}
    r = requests.post(url, headers={"Authorization": f"Bearer {key}",
                                    "Content-Type": "application/json"},
                      json=payload, timeout=cfg["timeout"])
    if r.status_code != 200:
        raise RuntimeError(f"{r.status_code} {r.text[:400]}")
    item = r.json()["data"][0]
    return save(item.get("url"), item.get("b64_json"), out)


PROVIDERS = {"openai": gen_openai, "dashscope": gen_dashscope, "ark": gen_ark}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("prompt", nargs="?")
    ap.add_argument("out", nargs="?")
    ap.add_argument("--provider")
    ap.add_argument("--model")
    ap.add_argument("--size")
    ap.add_argument("--key")
    ap.add_argument("--base-url")
    ap.add_argument("--seed", type=int)
    ap.add_argument("--quality", help="OpenAI only: low / medium / high")
    ap.add_argument("--resolution", help="apimart -ext 档: 1K / 2K / 4K（留空不传）")
    ap.add_argument("--version", help="apimart -ext 档: flare / sunburst（留空不传）")
    ap.add_argument("--check", action="store_true", help="打印解析后的配置与真实请求端点/key（不联网）")
    ap.add_argument("--probe", action="store_true",
                    help="真发一张最小提示词验证中转站连通（会花一次生图费用）")
    a = ap.parse_args()

    cfg = load_cfg()
    for k, v in (("provider", a.provider), ("model", a.model), ("size", a.size),
                 ("base_url", a.base_url), ("seed", a.seed), ("quality", a.quality),
                 ("resolution", a.resolution), ("version", a.version)):
        if v:
            cfg[k] = v

    # --check / --probe 都要先把配置打印出来；缺 key 时由各自分支给友好提示，
    # 而不是在 resolve_key 里直接退出（否则看不到端点/base_url 排错信息）。
    key = resolve_key(cfg, a.key, strict=not (a.check or a.probe))
    provider = cfg["provider"]
    if provider not in PROVIDERS:
        raise SystemExit(f"未知 provider: {provider}，可选 {list(PROVIDERS)}")

    if a.check or a.probe:
        masked = (key[:6] + "…" + key[-4:] if len(key) > 12 else ("***" if key else "(空)"))
        print(f"relay.json : {RELAY_PATH} ({'存在' if RELAY_PATH.exists() else '未填/不存在，走 config.json'})")
        print(f"provider   = {provider}")
        print(f"model      = {cfg['model']}")
        print(f"base_url   = {cfg.get('base_url') or '(官方默认)'} ")
        print(f"endpoint   = {openai_base(cfg.get('base_url') or '')}/v1/images/generations"
              if provider == "openai" else f"endpoint   = ({provider} 专用端点)")
        if provider == "openai":
            print(f"size       = {cfg['size']} -> "
                  f"{cfg['size'] if cfg.get('passthrough_size') else openai_size(cfg['size'])}")
        else:
            print(f"size       = {cfg['size']} ({provider} 原生)")
        print(f"quality    = {cfg.get('quality') or '-'}")
        print(f"resolution = {cfg.get('resolution') or '-'}   version = {cfg.get('version') or '-'}"
              f"   (apimart -ext 档；留空不传)")
        print(f"async_poll = 自动识别 task_id 并轮询 /v1/tasks/{{id}}"
              f"（间隔 {cfg.get('poll_interval')}s × 最多 {cfg.get('poll_max')} 次）")
        print(f"api_key_env= {cfg.get('api_key_env')}   key = {masked} ({len(key)} chars)")
        if a.check:
            if not key:
                print("\n⚠ api_key 还没填：填 qa2/gpt/relay.json 或跑 qa2/gpt/fill.ps1 / relay_form.py。")
            print("配置读取成功，未联网。真验证连通： python tools/img.py --probe")
            return
        if not key:
            raise SystemExit("api_key 为空，--probe 需要真 key。先填 relay.json。")
        # --probe：真出一张 1x1 级最小图，只验证中转站能不能通
        out = ROOT / "qa2/gpt/_probe.png"
        print(f"\n[probe] 真发一张最小提示词 -> {out}（会花一次生图费用）")
        print(PROVIDERS[provider]("一只简单的灰色圆形笑脸图标，白底，扁平矢量", out,
                                  cfg, key, cfg["model"], cfg["size"]))
        print("[probe] 通了。若返回格式被改过导致报错，把报错贴给我，我按该中转站调 extract_image()。")
        return

    if not a.prompt or not a.out:
        raise SystemExit("用法: python tools/img.py \"提示词\" out.jpg")

    print(PROVIDERS[provider](a.prompt, Path(a.out), cfg, key, cfg["model"], cfg["size"]))


if __name__ == "__main__":
    main()
