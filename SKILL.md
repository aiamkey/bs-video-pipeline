---
name: bs-video-pipeline
description: 「男生变帅」口播短视频流水线（对标抖音凯哥恋爱说）。唯一真源是 lbr-promo/pipeline/config.json；一条命令按 配音→对齐→合成数据→渲染→混音→质检 跑完。当要出男生变帅/形象管理类横屏口播片、改脚本或卡片、调语速/时长/卡型、加卡通幻灯片素材、排查字幕不同步/闪白/静止过长/音色问题、或想知道某个动画该长什么样时使用。Use when producing or tuning the boys-looksmaxxing talking-head video pipeline.
---

# 男生变帅号 · 视频流水线

工程 `C:\Users\张宇\OneDrive\Desktop\video\lbr-promo`（Remotion 4.0.484 / Node 22）。
对标：抖音「凯哥恋爱说」52327471915，1280×720 横屏，底部分段进度条，白字黑边字幕。

> 目录名 `lbr-promo` 是历史遗留，**只服务男生变帅**，不再做 LBR。

---

## 0.5 依赖自检（新环境第一步）

**先跑体检，别直接开跑。** 缺什么它会直接给安装命令：

```bash
python pipeline/preflight.py            # 只检查
python pipeline/preflight.py --install  # 缺的自动装（npm ci / pip install -r requirements.txt）
```

必需项（缺任一都跑不起来）：

| 依赖 | 版本 | 谁需要它 |
|---|---|---|
| Python | ≥3.10 | 全部脚本 |
| `requests` `numpy` `dashscope` | — | 配音 / 对齐 / 生图 / 质检 |
| Node.js | 18 / 20 / 22 | Remotion 渲染 |
| `npx` | 随 Node | `remotion render` |
| ffmpeg | 6+ | 混音、抽帧、静止段检测 |
| `remotion/package.json` + `npm ci` | Remotion 4.0.484 | 渲染引擎 |
| `DASHSCOPE_API_KEY` | — | cosyvoice-v2 配音、wanx 生图 |

可选项（缺了只是少能力，不阻塞）：`remotion/public/textures/bs/*.jpg`（实拍图卡）、
`remotion/public/textures/slides/*.jpg`（卡通幻灯片）、`video-shotcraft` 卡库（找灵感用）。

**为什么不做成自动下载**：Node 与 ffmpeg 是系统级安装（要选版本、改 PATH），
静默下载安装包在 CI 和本地都不安全；所以这里做成"**检测 + 给命令 + 可选自动装 pip/npm**"，
系统级依赖由人确认一次。

## 0. 唯一真源

**改参数只改 `lbr-promo/pipeline/config.json`。** 代码和文档都不写死数字，全部读这里。

```
project  ep / script / composition
paths    python / ffmpeg / 工程根
text     句长 字数 标点 人称 禁忌
voice    provider voice rate gap silence_keep 语速区间 响度
video    分辨率 fps crf duration{mode,target_sec} 单镜 字幕 进度条
card     配色 字号 行数 红字数 stagger 入场
images   provider model size base_url api_key_env   ← 生图 key 归使用者
check    文件大小 静止阈值 采样帧率
```

---

## 1. 目录地图

| 文件 | 管什么 |
|---|---|
| `pipeline/config.json` | 全部参数（改这里） |
| `pipeline/run.py` | 六个阶段 + plan + all |
| `pipeline/check.py` | 11 项体检 |
| `pipeline/README.md` | 怎么用、改一个小点改哪里 |
| `pipeline/SPEC.md` | 方法论 + 文稿/动画/素材规格 |
| `pipeline/ANIMATION.md` | **动画怎么长**（六动作 + 转场 + 五步循环 + 卡通幻灯片） |
| `scripts/script-*.json` | 文稿（每句带 card） |
| `src/bs/Cards.tsx` | 卡型组件 |
| `src/bs/DataFilm.tsx` | 渲染入口（读 `src/data/film.json`） |
| `src/data/film.json` | 生成物：一句一镜 + 时间轴 |
| `tools/img.py` | 生图（openai / dashscope / ark 三规范） |
| `tools/cosy_chapter.py` | 按章配音 |
| `tools/align_v2.py` | whisper 词级对齐 → timeline |

---

## 2. 命令

```powershell
$py = "E:\miniconda\envs\JupyterProject\python.exe"
$env:NO_PROXY = "dashscope.aliyuncs.com"          # 必设，否则 requests 走代理报 ProxyError

& $py lbr-promo\pipeline\run.py plan  ep01          # 只估算时长/字数，不花钱
& $py lbr-promo\pipeline\run.py all   ep01          # 全流程
& $py lbr-promo\pipeline\run.py all   cardtest scripts\script-cardtest.json   # 临时换稿
& $py lbr-promo\pipeline\run.py voice ep01          # 单阶段：voice/align/build/render/mix/check
& $py lbr-promo\pipeline\check.py ep01 [mp4路径]
```

产物：`out/<name>-raw.mp4`（渲染）→ `out/<name>-final.mp4`（loudnorm −16 LUFS）。

`render` 阶段会自己把 `TEMP/TMP` 指到 `lbr-promo\.tmp-remotion`，**不要手动跑 npx 忘了这一步**（会报 `Permission denied ... remotion-audio-mixing\0.wav`）。

---

## 3. 文稿

`lbr-promo/scripts/script-XX.json`，`chapters[].lines[].{text,gap,card}`。

- 长度：`config.text`。当前基线 **38 句 / 525 字 / 103s / 5.1 字秒**。
- 时长：`video.duration.mode = auto`（跟稿子）或 `target`（`target_sec` ± `tolerance_pct`，反推字数）。
- 句子 ≤ 18 字，逗号:句号 ≈ 3:1，一条 3–5 个问号。
- 禁忌六条见 `SPEC.md §2.8`：广告腔 / 三连排比 / 抽象名词 / 超 25 字 / 结尾总结 / 自问自答超 2 次。

---

## 4. 卡型（`card.type`）

`copy` `section` `list` `no-list` `stat` `image` `quote` `chips` `brow` `posture` `color` `cmd` `outro`
`teacher`（讲师提问）`board`（墨绿黑板编号）`wrong`（红叉错误示范）`annotate`（实拍红点标注）
**`slides`（卡通图当幻灯片，2–4 张/句）**

每句可指定转场：`"transition": "cut|fade|slideL|slideR|zoom|slam"`，不写默认 `fade`。
`slides` 字段：`frames[]` `hold`(秒/张) `text` `push` `fit` `paper` `captions[]`。

---

## 5. 动画（只讲方法，实现交工具）

细节在 `ANIMATION.md`，四条硬规矩先记住：

1. 单镜 2.5–3.0s，最长 4.0s；连续静止 ≤ 3s。
2. 入场起点透明度用 **0.15**，不要 0（0 会在切点闪白）。
3. 转场 85% 是硬切；fade 只用在章节之间和"错误→原理"那一步。
4. 一屏 ≤ 3 个元素；大字卡每行 ≤ 9 字，只标红 1–2 处。

卡通素材**不是动画，是图**：一张停 1.2–2.0s，硬切翻页，每张 1.000→1.035 微推（顺带把静止占比压到 0）。

---

## 6. 素材

七类：讲师 / 黑板 / 学员卡通 / 真人局部 / 解剖线稿 / 长文卡 / 大字卡（占屏比见 `SPEC.md §4.1`）。

生图：

```powershell
& $py tools\img.py "<角色描述>，<动作>" lbr-promo\public\textures\slides\s1.jpg
& $py tools\img.py "..." out.jpg --provider openai --model gpt-image-1 --size 1536x1024 --seed 20261124
& $py tools\img.py --check
```

key 三种给法：`--key` → `images.api_key_env` 环境变量 → `images.api_key`。
**换 provider 会漂脸**：锁 seed + 写死六个角色特征（发长/发色/上衣/裤色/描边/背景）。

已有实拍图：`public\textures\bs\`（brow/hair/mirror/posture/skin/wear）。卡通图：`public\textures\slides\s1–s5`。

---

## 7. 质检（`check.py`）

11 项：文件大小 / 成片时长 / 总字数 / 句数 / 整体字秒 / 单镜中位 / 最长单镜 / 语速异常句 / 最长静止段 / 静止占比 / LUFS / dBTP。

硬指标（FAIL 才退 1）：文件大小、时长、响度、真峰值。风格指标记 WARN。
**短样片（< 30s）自动把大小与字秒降为 WARN**，方便 cardtest。

已知基线（EP01 v6）：103.2s / 525 字 / 5.09 字秒 / 单镜中位 2.46（WARN）/ 最长镜 4.76（WARN）/ **静止占比 49%（WARN，未修）**。

---

## 8. 踩过的坑（故障对照）

| 症状 | 根因 | 修法 |
|---|---|---|
| 切点闪白 | 卡片 opacity 从 0 起 | `card.opacity_start` 保持 0.15 |
| 字幕与语音错位 | 改文案没重跑 align | 改稿必须 `align` 再 `build` |
| 声音断触 | 逐句合成，静音堆积 | 按章合成（`cosy_chapter`）+ 轻削静音 |
| "怪声"金属感 | atempo 加速 | 用原生 `speech_rate` |
| 渲染报 `Permission denied .wav` | TEMP 在 %TEMP% | TEMP/TMP 指向工程内 |
| `KeyError: DASHSCOPE_API_KEY` | 脚本直接读 env | `run.py` 已代为注入（env → config → tts-service 配置） |
| `ProxyError` 调百炼 | 系统代理 | `$env:NO_PROXY="dashscope.aliyuncs.com"` |
| 画面与语音对不上 | 多句绑一张卡 | 改"一句一镜"（`film.json` 驱动） |
| 静止占比过高 | 卡片是死图 | 每张 1.000→1.035 微推 |

---

## 9. 现状

- EP01：`out\EP01-变帅5件事-v6.mp4`（103.1s，已发版级）。
- 新卡 4 张已跑通：`out\cardtest-final.mp4`（8.1s，质检全绿）。
- 卡通幻灯片已跑通：`out\slides-final.mp4`（7.4s，静止占比 0%）。
- 待办：把微推用到 EP01 全部卡片（消掉 49% 静止）；`teacher` 剪影太糙，可换 shotcraft `brand-ink-open`；凯哥剩余 49 条作品待采集（13/62）。
