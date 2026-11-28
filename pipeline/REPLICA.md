# 需求规格 · 定稿 v2

> 老板需求（用户 m11415 原话口径）：**给你一个视频 → 提取文案 / 提取素材 / 提取制作方式 → 用 GPT image 生成对应素材、声音走克隆 → 复刻 80%+ → 交付 MP4 + 剪映可编辑工程。**
> 本文档是两轮问答后的**锁定版**，取代 [能力评估与改造清单.md](能力评估与改造清单.md) 里的默认假设（那版按「扒原声 + 素材兜底」写）。评估清单保留作现状与 P0–P3 背景。
> 定稿日 2026-11-28。

---

## 0. 锁定口径（不再变）

| 项 | 定值 |
|---|---|
| 输入 | 本地 mp4，**仅动画式**：图文卡 / 聊天截图 / 大字卡 / 文档页 / 卡通角色 / 气泡流 / 进度导航。**真人实拍、需要 seedance 出动态镜头的一律不进** |
| 时长 | **仿原片**，容差 `≤2% 或 ±5s 取大`；不预先设固定时长 |
| 拆解 | 固定四步 → 汇成**一份** `spec.json`：① 提取文案 ② 提取素材清单（每个画面位需要什么 + 参考描述）③ 提取制作方式（版式几何 / 节奏 / 分段 / 动效）④ 生成对应版本 |
| 素材 | **GPT image（中转站 gpt-image 系列）为主路径**生成画面；SVG / 代码层只保留必须严格听话的图形（气泡、徽标、导航、字幕、对错标、留白） |
| 保真 | **结构照抄 + 画面 GPT 重画**：文案 / 分段 / 时长 / 版式几何 / 字幕位置照原片复刻；画面按识别出的描述用 GPT 生成自己的一版。**不追求像素级形似、不搭定妆照一致性链路** |
| 语音 | **声音克隆**：参考音频从原片自动挑一段最干净的口播，克隆出专属音色，念提取出来的文案 |
| 交付 | `deliver/<片名>/` = **MP4 成品 + 剪映可编辑草稿**（本地化 `assets/` + 画面轨 + 字幕轨 + 配音轨）+ `REPORT.md` + 素材清单 + `spec.json` |
| 80% 验收 | 时长差≤2% / 字幕覆盖100% / 版式几何对齐≥80% / 叙事分段对齐 / 音频对位。**不含人脸像素级一致、不含真人出镜** |
| 剪映「可编辑」 | 轨级 / 片段级（换素材、调时长、加花字音效、改关键帧）；改字走渲染层重生成 |

---

## 1. 与上一版评估的 3 处实质变化

| # | 上一版 | 本版 | 影响 |
|---|---|---|---|
| 1 | 凯哥 / 男生变帅版式当模板 | **只当方法样本，去掉硬绑**；通用「给片→拆解→重建」 | `spec.json` 不带任何题材字段，恋爱教学 / 变帅只作参考实现 |
| 2 | 素材以 36 张 SVG 兜底为主 | **GPT image 升为主路径**，SVG 降级为「听话图形」层 | `P2 #11` 从「二选一」改成「GPT 优先、SVG 补图形」 |
| 3 | 语音默认扒原片原声 | **改声音克隆**（用户选定） | 新增整条 `voice` 链路，见 §3；`spec.voice` 段结构变了 |
| 附 | 「任意视频」 | **收窄到动画式** | 可行性反而更高，正好落在能稳定 80%+ 的那一档 |

---

## 2. 两个通道 / 两个待填位

| 通道 | 配置文件 | 状态 | 你要给的 |
|---|---|---|---|
| 生图 | [qa2/gpt/relay.json](../gpt/relay.json) | ✅ 已就绪，干净空模板 | `base_url` + `api_key` + `model`（+可选 `quality`） |
| 声音克隆 | [qa2/replica/voice.json](voice.json) | ✅ 本轮新建，可填模板 | 走哪条 + `api_key`；或填已有 `voice_id` 直接复用 |

生图侧已处理的兼容点（沿用上一轮）：base_url 三种写法归一、`data[0].url|b64_json` / 顶层 / Gemini 四种返回、扩展名按魔数转码、key 打码、`gen_gpt_bottoms.py` 自动继承。

本机已探明的克隆通道（两条，选一）：

- **jcaigc 语音网关**（[qa2/cms-voice-clone.md](../cms-voice-clone.md)）：`POST https://api.jcaigc.cn/v1/audio/voices` multipart 建音色 → `GET .../voices/{id}` 等 `OK` → `POST /v1/audio/speech` 合成。默认 `cosyvoice-v3.5-plus`，**复刻 9.9 元/个**（创建成功即扣），合成 `-plus` 1.5 元/万字符 / `-flash` 0.8 元/万字符；每账号最多 10 个音色；**用哪个模型建就必须用哪个模型合成**。
- **百炼 qwen3-tts-vc**：`tools/pylibs/dashscope/examples/01_atomic_capabilities/audio/voice_clone.py` 默认 `qwen-audio-3.0-tts-flash`（需参考音频 HTTPS 地址）；本机 [tools/_tts_vc_probe.py](../../tools/_tts_vc_probe.py) 已实测过 realtime 合成通道 `model=qwen3-tts-vc-realtime-2025-11-27`、`voice_id=qwen-tts-vc-ep01voice-voice-20261124151028273-7319`（EP01 音色，可直接复用参考）。

---

## 3. 声音克隆链路（本轮新增，评估文档里没有）

```
原片 mp4
  └─ replica.py voice
       ├─ extract_ref   ffmpeg 按 ASR 词级时间戳挑 10–20s 单人无 BGM 段 → ref.wav
       ├─ voice_create  POST /v1/audio/voices（multipart file+model+name）→ voice_id
       ├─ voice_wait    GET .../voices/{id} 轮询 DEPLOYING → OK（UNDEPLOYED 换段重试）
       ├─ voice_speak   按章节/分段合成，原生 rate 调速，不用 atempo（防金属感）
       ├─ align         词级时间戳对齐到 spec.subs，写 spec.voice.segments
       └─ → 配音轨 wav 进剪映 spec + 混进 MP4
```

- 参考音频硬要求：**单人、无背景音乐、无混响、3–30 秒、≤7.5MB**，推荐 10–20 秒（`qa2/cms-voice-clone.md:36`）。从原片自动挑，取 ASR 段里「能量稳、无重叠、语速正常」的最长干净窗。
- 章节合成沿用 `tts-service` 的教训（`scripts/tts.py script` 模式）：按章拼 N 次，不逐句拼，避免断触与电平跳变；`rate` 用原生参数，禁用 `atempo`。
- 计费如实写进 REPORT：复刻 9.9 元/个 + 合成按字符；`UNDEPLOYED` 不退款，挑段前先把控质量。
- **一致性红利**：克隆音色天然锁同一个人，这一层不像 GPT 生图会漂脸，是整条链里最稳的一环。

---

## 4. `spec.json` 骨架（MP4 与剪映共用同一份）

```json
{
  "meta": {
    "src": "参考片.mp4", "src_duration": 547.36,
    "target_duration": 547.36, "tolerance": "max(2%, 5s)",
    "fps": 30, "w": 1280, "h": 720, "kind": "animated"
  },
  "voice": {
    "provider": "jcaigc", "clone_model": "cosyvoice-v3.5-plus",
    "speak_model": "cosyvoice-v3.5-plus", "voice_id": "",
    "ref_audio": "auto", "rate": 1.08,
    "segments": [{ "s": 0.0, "e": 2.92, "text": "…", "wav": "voice/000.wav" }]
  },
  "subs":   [{ "s": 0.0, "e": 2.92, "text": "…", "style": "white-black-stroke" }],
  "sections": [{ "id": "hook", "s": 0.0, "e": 21.62, "role": "钩子" }],
  "scenes": [{
    "s": 21.62, "e": 93.44, "mode": "chat",
    "layout": { "col": [365, 917], "nav_y": 676, "sub_y": 640,
                "badge": [4, 4, 349, 119], "bg": "rgb(213,213,213)" },
    "assets": [{ "slot": "couple", "prompt": "…识别出的画面描述…",
                 "provider": "gpt-image", "file": "assets/scene03.png" }],
    "graphics": ["bubble:green", "bubble:gray-error", "mark:red-x"],
    "msgs": [], "head": "", "bullets": []
  }],
  "jianying": { "tracks": ["video", "text", "audio", "sticker"], "draft_root": "auto" },
  "acceptance": { "duration_diff": "≤2%", "sub_cover": "100%",
                  "layout_align": "≥80%", "sections_align": true, "audio_align": true }
}
```

> 与现状的差别：`q6.json`（scenes/subs）和 `film.json`（lines/panels）是两套结构，剪映只认后者。定稿后**只有一份 spec**，渲染与剪映都读它，`jy_from_spec.py` 负责分轨。

---

## 5. 改造清单增量（在评估文档 P0–P3 上追加 / 改写）

| 层 | 原条目 | 本版改动 |
|---|---|---|
| **P0** | `replica.py` / `spec.schema.json` / `jy_from_spec.py` / 拆 `jy_from_film.py` 纯函数 | **新增** `replica.py voice` 子命令 + `tools/replica_voice.py`（挑参考段→建音色→等 OK→章节合成→对齐）；`jy_from_spec.py` 配音轨接克隆 wav 而非原声 |
| **P1** | 探针 / 转录通用化 / 版式量测 / 记忆层模板 | `ref_asr.py:42` 去掉写死的「恋爱教学」`initial_prompt`；**新增**「挑干净参考音频段」输出（供 §3 用）；素材清单生成器把每个画面位写成 GPT prompt |
| **P2** | 参数化 `Render.tsx` / 抽 Chars 零件 / 素材二选一 | **改为** 素材层默认走 `relay.json` 的 GPT image，SVG 仅渲染气泡/徽标/导航/字幕；动画式版式库显式枚举（chat / scene / title / doc / progress），拒绝实拍类 |
| **P3** | `replica_verify` / `deliver/` / `replica` skill | REPORT **新增**「音色一致性 / 参考音频来源 / 复刻与合成计费」一项；`deliver/` 里 `voice/` 与 `assets/` 一并本地化 |

顺序仍按 **P0 → P1 → P3 → P2**，把最难的参数化渲染放最后。

---

## 6. 仍然排除（边界，如实对老板）

1. 真人出镜、需 seedance 动态镜头 → 用户已明确不考虑。
2. 复杂 3D / 粒子 / 重转场 → 成本高于重拍。
3. 剪映里元素不能单独选中改字；改字回渲染层重生成。
4. 剪映导出 MP4 必须手点 —— **对我们无影响**，MP4 由 Remotion 直出（已知成功路径 `Q6Mute --muted` + ffmpeg 混流，绕开音频预处理 `Permission denied`）。
5. GPT image **无 seed**，多张脸会漂 —— 本版保真口径是「结构照抄 + 画面重画」，主动放弃像素级形似，所以不搭定妆照链路；若以后要「形似优先」再补。

---

## 7. 决策已锁定（两轮问答全部答完，2026-11-28）

| 决策 | 定值 | 落点 |
|---|---|---|
| 语音方式 | **声音克隆**（非扒原声、非 TTS 音色选优） | §3 整条 `voice` 链路 |
| 保真口径 | **结构照抄 + 画面 GPT 重画**（不搭定妆照一致性链路） | §0 / §6.5 |
| 克隆对象 | **原片那个人**（参考音频从原片自动挑 10–20s 干净段，克隆出的音色念提取出的文案） | `voice.json: ref_audio=auto` |
| 克隆通道 | **中转站只管生图，克隆单独给**（独立语音网关 `https://api.jcaigc.cn/v1` + 单独一把 key，不与生图共用） | `voice.json: provider=jcaigc / base_url` |

> 四个决策全部落在已铺好的默认里：`voice.json`（`ref_audio=auto` / `provider=jcaigc`）与 `relay.json` **配置无需改动**。

**只剩两项待你给（是信息，不是待拍板）**：

1. 生图 → `relay.json` 填 `base_url` + `api_key` + `model`。
2. 克隆 → `voice.json` 填独立网关的 `api_key`；或填现成 `voice_id` 跳过 `create`（零复刻费，先把链路跑通）。

给齐即按 §8 跑第一份端到端；没给齐也能先按 **P0 搭编排器骨架**（`replica.py` / `spec.schema.json` / `jy_from_spec.py`，纯本地、不联网、不花钱）。

---

## 8. 第一步（拿到两个 key 就跑）

先拿现成的六问片 / `q6.json` 当第一份输入，跑通端到端：**提取 → GPT 重画画面 → 克隆配音 → Remotion 出 MP4 → `jy_from_spec.py` 出剪映工程 → REPORT**，给老板看双交付实物；再按 P0→P1→P3→P2 补成 `replica` skill。

---

## 附：文件索引

- 本定稿：[需求规格-定稿.md](需求规格-定稿.md) · 声音克隆配置：[voice.json](voice.json)
- 现状与 P0–P3：[能力评估与改造清单.md](能力评估与改造清单.md)
- 生图配置：[../gpt/relay.json](../gpt/relay.json) · 用法 [../gpt/HOWTO-中转站.md](../gpt/HOWTO-中转站.md)
- 克隆通道实测：[../cms-voice-clone.md](../cms-voice-clone.md) · [../../tools/_tts_vc_probe.py](../../tools/_tts_vc_probe.py)
- 已跑通实证：[../ref/RECREATION.md](../ref/RECREATION.md) · [../../lbr-promo/pipeline/JIANYING.md](../../lbr-promo/pipeline/JIANYING.md)
- 剪映 spec→草稿：[../../tools/jy_draft.py](../../tools/jy_draft.py) · film→剪映：[../../tools/jy_from_film.py](../../tools/jy_from_film.py)
- 转录：[../ref_asr.py](../ref_asr.py) · 全自动流水线：[../../lbr-promo/pipeline/run.py](../../lbr-promo/pipeline/run.py)
