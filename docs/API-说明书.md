# API 说明书

本项目用到的三个外部接口。**除了这三个，其余（切帧、ASR、烧字幕、合成、渲染）都是本地 ffmpeg + 本地模型，不联网、不花钱。**

| # | 用途 | 服务 | 配置位置 | 状态 |
|---|---|---|---|---|
| 1 | 出图（复刻重画 / PPT 配图） | apimart 中转站 · `gpt-image-2` | `qa2/gpt/relay.json` | **在用** |
| 2 | 声音克隆 + 合成 | 阿里云百炼 · `qwen-audio-3.0-tts-flash` | `qa2/replica/voice.json` | **在用** |
| 3 | 文生视频 | 火山方舟 · `doubao-seedance` | 无（需自备 key） | 未接入、未实测 |

---

## 0. key 的三种给法（按优先级）

**代码里的解析顺序**（`tools/img.py:resolve_key` / `tools/replica_voice.py:92`）：

```
1. 命令行参数  --key sk-xxx          （仅该次生效）
2. 环境变量    OPENAI_API_KEY / DASHSCOPE_API_KEY   （覆盖配置文件）
3. 配置文件    relay.json / voice.json 的 api_key    （推荐，长期）
```

### 环境变量（临时）

```powershell
$env:OPENAI_API_KEY    = "sk-xxx"
$env:DASHSCOPE_API_KEY = "sk-xxx"
```

永久写入用户环境：

```powershell
[Environment]::SetEnvironmentVariable("OPENAI_API_KEY", "sk-xxx", "User")
```

### 配置文件（推荐）

`qa2/gpt/relay.json`：

```json
{
  "base_url": "https://api.apimart.ai/v1",
  "api_key":  "sk-xxx",
  "model":    "gpt-image-2",
  "provider": "openai",
  "size":     "16:9",
  "resolution": "1K"
}
```

`qa2/replica/voice.json`：

```json
{
  "provider":   "dashscope",
  "api_key":    "sk-xxx",
  "clone_model": "qwen-audio-3.0-tts-flash",
  "speak_model": "qwen-audio-3.0-tts-flash",
  "voice_id":   "qwen-audio-3.0-tts-flash-replica-xxxxxxxx",
  "sample_rate": 24000,
  "rate": 1.08
}
```

### 验证（不花钱）

```powershell
python tools\img.py --check            # 打印解析结果，不联网
python tools\replica_voice.py --check  # 同上
python tools\img.py --probe            # 真出一张（约 1 分钱）
```

---

## 1. 出图：apimart `gpt-image-2`

**中转站**，OpenAI 兼容路径 + 自建异步任务。**异步**是关键：提交只回 task_id，要轮询取图。

### 提交

```
POST https://api.apimart.ai/v1/images/generations
Authorization: Bearer sk-xxx
Content-Type: application/json
```

```json
{
  "model": "gpt-image-2",
  "prompt": "极简扁平矢量插画，暖米白背景，珊瑚橙 + 墨绿 + 暖灰三色点缀，16:9 横版，画面里绝对不要出现任何文字",
  "size": "16:9",
  "resolution": "1K",
  "n": 1
}
```

返回：

```json
{ "code": 0, "data": { "task_id": "tsk_xxxxxxxx" } }
```

### 轮询

```
GET https://api.apimart.ai/v1/tasks/{task_id}
Authorization: Bearer sk-xxx
```

```json
{
  "code": 0,
  "data": {
    "status": "completed",
    "result": { "images": [ { "url": ["https://.../xxx.png"] } ] }
  }
}
```

`status`：`pending` → `processing` → `completed`（失败是 `failed`）。

图片 URL 是**签名地址，约 24 小时失效** —— 拿到立刻落盘（`tools/img.py` 的 `save()` 会下载到本地）。

### 参数表

| 字段 | 值 | 说明 |
|---|---|---|
| `model` | `gpt-image-2` | 等价 `gpt-image-2-ext` |
| `size` | `16:9` / `9:16` / `1:1` | **中转站用比例字符串**，不是 `1280x720` |
| `resolution` | `1K` / `2K` / `4K` | 4K 贵 2.6 倍，1280×720 用 1K 够 |
| `quality` | **留空** | `gpt-image-2` 不认 `low/medium/high`，填了报错 |
| `response_format` | **留空** | 多数中转站不接受 |
| `n` | `1` | 批量就循环调用 |

### 价格（本机实测）

```
0.085–0.089 Credits / 张      1 Credit = ¥0.1
→ 约 0.9 分钱一张（1K，16:9）
```

余额查询：

```
GET https://api.apimart.ai/v1/user/balance
```

```json
{ "remain_balance": 8.5465, "remain_credits": 85.465,
  "used_balance": 1.4535, "used_credits": 14.535 }
```

`used_balance / used_credits = 0.1`，即 **1 Credit = ¥0.1**。

### curl 版

```bash
curl -X POST https://api.apimart.ai/v1/images/generations \
  -H "Authorization: Bearer sk-xxx" \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-image-2","prompt":"一只猫，扁平插画","size":"16:9","resolution":"1K","n":1}'
```

### 项目里的封装

```powershell
python tools\img.py --prompt "画面描述" -o out.png            # 单张
python tools\img.py --probe                                    # 连通性测试
python tools\replica_redraw.py --spec spec.json --only 0,2,7   # 批量重画指定屏
python tools\replica_redraw.py --spec spec.json --apply        # 全量重画并写回 spec
```

---

## 2. 声音克隆 + 合成：阿里云百炼 `qwen-audio-3.0-tts-flash`

**注意：这个不走裸 HTTP，走官方 SDK**（`dashscope >= 2.0`，2.0 才引入统一的 `Client`）。

```powershell
pip install "dashscope>=2.0"     # 1.x 没有 Client，会报 cannot import name 'Client'
```

### 三步链路

```python
from dashscope import Client
client = Client(api_key="sk-xxx")

# ① 建音色（声音复刻）—— 参考音频内联成 data URI，不需要公网 URL
voice = client.audio.voices.create(
    target_model="qwen-audio-3.0-tts-flash",
    prefix="replica",
    audio="data:audio/wav;base64,UklGR...",
)
voice_id = voice.output.voice_id

# ② 查状态，等 OK
status = client.audio.voices.get(voice_id)     # output.status == "OK"

# ③ 合成（WebSocket 流式，收 PCM）
session = client.audio.tts.connect(
    model="qwen-audio-3.0-tts-flash",
    voice=voice_id,
    format="pcm",
    sample_rate=24000,
)
session.send_text("看似拒绝，其实是偷偷喜欢你")
session.stop()
for event in session.events():
    ...  # bytes = 24kHz / 16bit / mono PCM，自己加 WAV 头
```

### 硬性约束（踩过的坑）

| 约束 | 说明 |
|---|---|
| **`clone_model == speak_model`** | 建音色时用 `qwen-audio-3.0-tts-flash`，合成也必须用它，混 plus/flash 会 `Model not exist` |
| **参考音频规格** | 单人、无 BGM、无混响、**3–30 秒**（推荐 10–20s）、≥16kHz、≤10MB |
| **`speech_rate` 无效** | 这个音色不认语速参数，实测 1.08/1.35/2.0 只差 4–9%（随机波动）→ 语速只能靠装配端 ffmpeg `atempo` 压 |
| **PCM 格式假设** | 按 24000Hz/16bit/mono 落 WAV 头；服务端若改格式要调 `sample_rate` |
| **建音色会计费且不自动删** | 创建成功后进账单，谨慎 `create` |

### 价格

```
合成：¥1 / 万字符（按输入字数，输出不计）
→ 392 段 / 3141 字 = ¥0.31
复刻（建音色）：按键计费，一般 < ¥1
```

### 项目里的封装

```powershell
python tools\replica_voice.py --check                          # 只看配置
python tools\replica_voice.py extract-ref segs.json ref.wav --src 原片.mp4
python tools\replica_voice.py create ref.wav --yes             # 建音色（花钱，需 --yes）
python tools\replica_voice.py wait <voice_id>
python tools\replica_voice.py speak spec.json qa2/replica/voice-out
python tools\replica_assemble.py --spec spec.json --voice-dir qa2/replica/voice-out -o voice.wav
```

### 解释器要求

`dashscope >= 2.0` 只装在独立 venv：

```
C:\Users\张宇\AppData\Local\venv-clone\Scripts\python.exe
```

⚠️ 跑网络脚本前**必须清代理**，否则 httpx 抛 `InvalidURL: Invalid port: ':1]'`（系统 `no_proxy` 尾部的 `[::1]` 被误解析）：

```powershell
foreach($n in @("HTTP_PROXY","HTTPS_PROXY","ALL_PROXY","http_proxy","https_proxy","all_proxy","NO_PROXY","no_proxy")){
  [System.Environment]::SetEnvironmentVariable($n,$null,"Process")
}
```

---

## 3. 文生视频（未接入）：火山方舟 `doubao-seedance`

**本机没有 key，未实测**，仅记录接口形态供接入参考。

### 提交

```
POST https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks
Authorization: Bearer $ARK_API_KEY
Content-Type: application/json
```

```json
{
  "model": "doubao-seedance-1-0-lite-t2v-250428",
  "content": [ { "type": "text", "text": "女生坐在咖啡馆看书的动态镜头，镜头缓慢推进 --ratio 9:16 --duration 5" } ],
  "ratio": "9:16",
  "duration": 5,
  "resolution": "720p"
}
```

### 轮询

```
GET https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks/{task_id}
```

`status`：`queued` → `running` → `succeeded`，视频地址在 `content.video_url`。

### 大致价格

720p / 5 秒 ≈ **¥0.3–0.5**（按 token 计，比静态图贵一个量级）。

### 什么时候才需要它

复刻线**不需要**——原片多是静态图文卡，出图 + ffmpeg 位移就够。
只有在「要真人/真人级运镜」或「原片本身是动态镜头」时才用得上，而后者在定稿口径里明确**不做**。

---

## 4. 成本速查

| 动作 | 单价 | 一条 10 分钟片的量 |
|---|---|---|
| 出图 | 0.9 分 / 张 | 163 张 ≈ **¥1.45** |
| 配音合成 | ¥1 / 万字符 | 3141 字 ≈ **¥0.31** |
| 声音复刻 | < ¥1（一次性） | ¥0.3–1 |
| ASR / 切帧 / 渲染 / 烧字幕 | ¥0 | **¥0**（全本地） |
| **合计** | | **≈ ¥1.8 / 条** |

---

## 5. 常见错误对照

| 报错 | 原因 | 修法 |
|---|---|---|
| `缺少生图 key` | 三处都没配 | 填 `relay.json` 的 `api_key` 或设 `OPENAI_API_KEY` |
| `cannot import name 'Client' from 'dashscope'` | dashscope 是 1.x | `pip install "dashscope>=2.0"` |
| `Model not exist` | clone/speak 模型不一致，或用了废弃的 realtime 音色名 | 两边统一 `qwen-audio-3.0-tts-flash` |
| `InvalidURL: Invalid port: ':1]'` | 代理环境变量污染 | 清 `HTTP_PROXY` / `NO_PROXY`（见 §2） |
| `ResourceNotExist`（voices.get） | 音色不在当前 key 名下 | 用当前 key 重新 `create` |
| `unsupported quality` | `gpt-image-2` 不认 quality | 留空 |
| 图片 URL 404 | 签名地址过期（约 24h） | 拿到即下载 |
| `WinError 206 文件名或扩展名太长` | ffmpeg 命令行超 32K | 缩路径 / 硬链短名（`replica_render.py` 已内建处理） |

---

## 6. 一句话总结

```
出图（apimart 异步轮询） → 本地 ffmpeg 合成 → 配音（百炼 SDK 流式）
                                    ↑
                        所有切帧/ASR/字幕/渲染都在本地，零成本
```
