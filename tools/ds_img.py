"""百炼文生图（wanx2.1-t2i-turbo / wanx2.1-t2i-plus）：异步任务 + 轮询 + 落盘。

用法:
  python tools/ds_img.py "<提示词>" <out.jpg> [size] [model]
  size 默认 1280*720；model 默认 wanx2.1-t2i-turbo
"""
import json
import os
import sys
import time

import requests

BASE = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis"
KEY = os.environ.get("DASHSCOPE_API_KEY", "")


def gen(prompt, out, size="1280*720", model="wanx2.1-t2i-turbo"):
    h = {"Authorization": "Bearer " + KEY, "Content-Type": "application/json",
         "X-DashScope-Async": "enable"}
    p = {"model": model, "input": {"prompt": prompt},
         "parameters": {"size": size, "n": 1, "prompt_extend": True}}
    r = requests.post(BASE, headers=h, json=p, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"create {r.status_code} {r.text[:300]}")
    task = r.json()["output"]["task_id"]
    url = "https://dashscope.aliyuncs.com/api/v1/tasks/" + task
    for _ in range(90):
        time.sleep(2)
        g = requests.get(url, headers={"Authorization": "Bearer " + KEY}, timeout=30)
        st = g.json()["output"]
        if st["task_status"] == "SUCCEEDED":
            u = st["results"][0]["url"]
            data = requests.get(u, timeout=120).content
            open(out, "wb").write(data)
            return f"{out} ({len(data)//1024} KB)"
        if st["task_status"] in ("FAILED", "CANCELED", "UNKNOWN"):
            raise RuntimeError(f"task {st}")
    raise RuntimeError("timeout")


if __name__ == "__main__":
    prompt = sys.argv[1]
    out = sys.argv[2]
    size = sys.argv[3] if len(sys.argv) > 3 else "1280*720"
    model = sys.argv[4] if len(sys.argv) > 4 else "wanx2.1-t2i-turbo"
    print(gen(prompt, out, size, model))
