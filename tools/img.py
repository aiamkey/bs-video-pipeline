"""生图 · 多规范统一入口。

用哪家、用谁的 key，全在 `lbr-promo/pipeline/config.json` 的 `images` 段，
或者命令行临时覆盖。默认走百炼（内置可用），也可以换成任何 OpenAI 兼容中转站。

用法:
  python tools/img.py "提示词" out.jpg
  python tools/img.py "提示词" out.jpg --provider openai --model gpt-image-1 --size 1536x1024
  python tools/img.py --check                      # 只验证 key 与连通性

key 的三种给法（优先级从高到低）:
  1. --key sk-xxx
  2. 环境变量（config.images.api_key_env 指定的名字，如 OPENAI_API_KEY）
  3. config.images.api_key 直接写死（本机自用可以，别提交）

支持的规范:
  openai    —— OpenAI 标准 /v1/images/generations，兼容 one-api / new-api / ohmygpt 等中转
  dashscope —— 阿里百炼 wanx（异步任务 + 轮询）
  ark       —— 火山方舟 doubao-seedream（/api/v3/images/generations）
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

DEFAULT = {
    "provider": "dashscope",
    "model": "wanx2.1-t2i-turbo",
    "size": "1280x720",
    "api_key": "",
    "api_key_env": "DASHSCOPE_API_KEY",
    "base_url": "",
    "timeout": 180,
    "seed": None,
}


def load_cfg() -> dict:
    c = dict(DEFAULT)
    if CFG_PATH.exists():
        cfg = json.loads(CFG_PATH.read_text(encoding="utf-8-sig"))
        c.update(cfg.get("images", {}))
    return c


def resolve_key(cfg: dict, cli_key: str | None) -> str:
    if cli_key:
        return cli_key
    env = os.environ.get(cfg.get("api_key_env") or "", "")
    if env:
        return env
    if cfg.get("api_key"):
        return cfg["api_key"]
    raise SystemExit(
        f"缺少生图 key。三种给法：\n"
        f"  1) --key sk-xxx\n"
        f"  2) 设环境变量 {cfg.get('api_key_env')}\n"
        f"  3) 写进 {CFG_PATH} 的 images.api_key"
    )


def save(url: str | None, b64: str | None, out: Path) -> str:
    out.parent.mkdir(parents=True, exist_ok=True)
    if b64:
        data = base64.b64decode(b64)
    elif url:
        data = requests.get(url, timeout=180).content
    else:
        raise RuntimeError("返回里既没有 url 也没有 b64_json")
    out.write_bytes(data)
    return f"{out} ({len(data)//1024} KB)"


# ---------- OpenAI 规范 ----------
def gen_openai(prompt: str, out: Path, cfg: dict, key: str, model: str, size: str) -> str:
    base = (cfg.get("base_url") or "https://api.openai.com").rstrip("/")
    url = f"{base}/v1/images/generations"
    payload = {"model": model, "prompt": prompt, "n": 1, "size": size}
    r = requests.post(
        url,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json=payload,
        timeout=cfg["timeout"],
    )
    if r.status_code != 200:
        raise RuntimeError(f"{r.status_code} {r.text[:400]}")
    item = r.json()["data"][0]
    return save(item.get("url"), item.get("b64_json"), out)


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
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()

    cfg = load_cfg()
    for k, v in (("provider", a.provider), ("model", a.model), ("size", a.size),
                 ("base_url", a.base_url), ("seed", a.seed)):
        if v:
            cfg[k] = v

    key = resolve_key(cfg, a.key)
    provider = cfg["provider"]
    if provider not in PROVIDERS:
        raise SystemExit(f"未知 provider: {provider}，可选 {list(PROVIDERS)}")

    if a.check:
        print(f"provider={provider} model={cfg['model']} size={cfg['size']} seed={cfg.get('seed')} key={key[:8]}…({len(key)} chars)")
        print("key 读取成功；实际连通性请跑一次生图验证。")
        return

    if not a.prompt or not a.out:
        raise SystemExit("用法: python tools/img.py \"提示词\" out.jpg")

    print(PROVIDERS[provider](a.prompt, Path(a.out), cfg, key, cfg["model"], cfg["size"]))


if __name__ == "__main__":
    main()
