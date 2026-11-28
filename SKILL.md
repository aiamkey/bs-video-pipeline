---
name: bs-video-pipeline
description: 「男生变帅」口播短视频流水线（对标抖音凯哥恋爱说）。唯一真源是 lbr-promo/pipeline/config.json；一条命令按 配音→对齐→合成数据→渲染→混音→质检 跑完，渲染前先用 audit.py 做排布体检。当要出男生变帅/形象管理类横屏口播片、改脚本或卡片、调语速/时长/卡型、用 panel（一屏多句+元素累加）排片、加卡通底板素材、把 film.json 转成剪映工程、排查字幕不同步/闪白/静止过长/元素排布像PPT/黑场/音色问题时使用。Use when producing or tuning the boys-looksmaxxing talking-head video pipeline.
---

# 男生变帅号 · 视频流水线

工程 `C:\Users\张宇\OneDrive\Desktop\video\lbr-promo`（Remotion 4.0.484 / Node 22）。
对标：抖音「凯哥恋爱说」52327471915，1280×720 横屏，底部分段进度条，白字黑边字幕。

> 目录名 `lbr-promo` 是历史遗留，**只服务男生变帅**，不再做 LBR。

---

## 0.0 三十秒速查

```powershell
$py = "E:\miniconda\envs\JupyterProject\python.exe"
$env:NO_PROXY = "dashscope.aliyuncs.com"
& $py lbr-promo\pipeline\env.py                                   # ⓪ 换机器先看这个：9 项路径全自动解析
& $py lbr-promo\pipeline\selftest.py                                # ⓪ 30 秒冒烟：链路还是好的吗
& $py lbr-promo\pipeline\audit.py                                   # ① 排布体检（FAIL 就别渲染）
& $py lbr-promo\pipeline\run.py all ep02 scripts\script-ep02.json   # ② 一条片
& $py lbr-promo\pipeline\check.py ep02                              # ③ 成片 11 项体检
```

**四份查表文档（别在 677 行里翻）：**

| 我想知道 | 看 |
|---|---|
| 该调哪个工具 / 每个工具怎么用 / **什么不该做** | `pipeline/TOOLS.md` |
| 出问题了先查什么 | `pipeline/TROUBLES.md` |
| 一条片多少钱、多少时间 | `pipeline/COST.md` |
| 剪映版本支持什么、spec 字段 | `pipeline/JIANYING.md` · `pipeline/SPEC.md` · `pipeline/jy_versions.json` |

三条不可违的铁律：

1. **改参数只改 `pipeline/config.json`**，代码和文档不写死数字。
2. **一屏 2–4 句**（panel），底板不动、元素逐句弹入；不是一句换一张图。
3. **入场透明度用 0.15**，不要 0（0 会在切点闪白）；每张图 1.000→1.035 微推（治静止占比）。

### 改了什么 → 重跑哪几步

| 你改了 | 必须重跑 | 为什么 |
|---|---|---|
| 文案（`script-*.json` 的 `text`） | `align` → `build` → `render` → `mix` | 句子变了，时间轴全变 |
| 卡片内容（`card` 字段） | `build` → `render` → `mix` | 只影响画面 |
| panel 元素（`el` / `x` / `y`） | `audit` → `build` → `render` → `mix` | 元素位置在读 film.json 时定 |
| `config.voice.rate` / `voice` | `voice` → `align` → `build` → `render` → `mix` | 配音从头来 |
| 字幕字号/位置（`config.video.subtitle`） | `render` → `mix` | 纯渲染层 |
| 响度（`config.video.lufs` / `true_peak`） | `mix` | 只混音 |
| 卡型组件（`Cards.tsx` / `Panel.tsx`） | `render` → `mix` | TSX 变了要重编译 |

> **渲染前跑 `audit.py`**：它只读 `film.json`，10 秒出结果。有 FAIL 就不许渲染——EP02 第一版就是跳过这步，
> 结果 25 个元素 92% 挤在 x=74 一列，白渲染两遍。

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

> 每个工具"什么时候用、怎么调、有什么坑"在 **`pipeline/TOOLS.md`**。这里只列"有什么"。

| 文件 | 管什么 |
|---|---|
| `pipeline/config.json` | 全部参数（改这里） |
| `pipeline/TOOLS.md` | **工具索引 + 负面清单 13 条** |
| `pipeline/TROUBLES.md` | **故障对照 30 条** |
| `pipeline/COST.md` | 成本与时间预算（一条片 ≈1.8 元 / 1.5–2 小时） |
| `pipeline/env.py` | **路径唯一解析层**：环境变量 → config.json → 自动探测；换机器/换盘符只改这层 |
| `pipeline/sfx.py` | **音效挂点生成**（换屏/元素/数字/结论 → `src/data/sfx.json`，不铺 BGM） |
| `tools/check_assets.py` | **素材缺口体检**（稿子引用的图在不在，缺了给三种补法） |
| `pipeline/selftest.py` | **30 秒冒烟自检**（不联网不渲染） |
| `pipeline/jy_versions.json` | **剪映版本能力表**（new_version / placeholder / 已验证能力） |
| `pipeline/run.py` | 六个阶段 + plan + all |
| `pipeline/audit.py` | **film.json 排布体检**（元素跨区 / label / 单镜中位 / 素材复用，FAIL 拦渲染） |
| `pipeline/check.py` | 11 项成片体检 |
| `pipeline/README.md` | 怎么用、改一个小点改哪里 |
| `pipeline/SPEC.md` | 方法论 + 文稿/动画/素材规格 |
| `pipeline/ANIMATION.md` | **动画怎么长**（六动作 + 转场 + 五步循环 + 卡通幻灯片） |
| `pipeline/library.json` | 素材库清单（场景 × 状态，`have` / `missing`） |
| `pipeline/assets.json` | 已入素材登记（`id / scene / file / used_in`） |
| `pipeline/CARTOON.md` | 卡通素材规格（数量 / 来源 / 衔接 / 留白） |
| `scripts/script-*.json` | 文稿（每句带 card，或 panel + el） |
| `src/bs/Cards.tsx` | 卡型组件（18 种卡片） |
| `src/bs/Panel.tsx` | **panel 层**（底板 + 7 种元素逐句弹入） |
| `src/bs/DataFilm.tsx` | 渲染入口（读 `film.json`，卡片层 + panel 层；`DataFilmNoSub` 供抽卡片静帧） |
| `src/data/film.json` | 生成物：lines + panels + 时间轴 |
| `tools/img.py` | 生图（openai / dashscope / ark + `--seed`） |
| `tools/stock.py` | 图库检索（bing / commons / openverse / pexels） |
| `tools/assets.py` | 素材登记与复用检查（list / check / add） |
| `tools/build_lib.py` | 按 library.json 补缺口（`--dry-run` / `--only`） |
| `tools/cosy_chapter.py` | 按章配音 |
| `tools/align_v2.py` | whisper 词级对齐 → timeline |
| `pipeline/JIANYING.md` | **剪映衔接**（两条路线 + spec + 三件实现事实 + 9 条坑 + §17 可迁移） |
| `tools/jy_env.py` | 探测剪映安装/版本/草稿根/skill 路径 → 写 `tools/jy.env`（换设备第一步） |
| `tools/jy.cmd` | 封装 `jyai.cli`（list / inspect / build / patch / repair / render） |
| `tools/jy_draft.py` | spec(JSON) → 剪映工程（多轨 + 关键帧 + 动画 + 花字；`--validate` 契约校验） |
| `tools/jy_from_film.py` | **film.json → 剪映工程**（底板/元素/字幕/配音自动分轨） |
| `tools/jy_check.py` | 回读草稿校验（版本 / 轨 / 关键帧 / 素材数 / **黑场 / 素材本地化**） |
| `tools/jy_localize.py` | **素材本地化**：素材复制进草稿 `assets/` + 路径改剪映占位符相对形式 → 草稿可整目录搬走 |
| `tools/jy_beauty.py` | 人像美化（skin/shape/body/肤色/妆容）：写 `materials.effects` type=figure |
| `tools/jy_cards.py` | 抽卡片静帧（垫满非 panel 段，否则一半黑场） |
| `pipeline/jy_beauty_catalog.json` | 美颜滑杆 ↔ resource_id 对照（skin 8 / shape 13 / body 12 / makeup 54 / skin_tone 2） |
| `pipeline/jy_text_effects.json` | 花字目录 1673 条（免费 94 条），`text_effect` 字段按中文名查 |
| `pipeline/REPLICA.md` | **复刻需求规格定稿**（输入口径 / 保真定义 / 80% 验收 / 交付物） |
| `tools/replica.py` | **复刻编排器**：`extract` / `shots` / `validate` / `jianying` / `auto` |
| `tools/replica_extract.py` | 参考片 → `spec.json`（事实层 + 归类层，本地不花钱） |
| `tools/analyze_ref.py` | **事实层核心**：探针 / 转写 / 镜头切点 / 版式量测（replica 依赖它，缺了就 ImportError） |
| `tools/replica_shots.py` | 按屏抽代表帧 → `assets[]`（进剪映图片轨） |
| `tools/replica_voice.py` | 声音克隆（百炼 voice-enrollment / jcaigc 备用） |
| `tools/jy_from_spec.py` | `spec.json` → 剪映工程（图片轨 + 字幕轨 + 配音轨） |
| `tools/spec.schema.json` | spec 契约（required：`meta` / `subs` / `scenes`） |

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

### 2.5 一条片从零到交付（九步，按顺序走）

| 步 | 做什么 | 产物 / 命令 | 卡住时的症状 |
|---|---|---|---|
| 0 选题 | 从高赞标题里挑**男生自己会承认**的痛点 | 一句话选题 | 选题没痛点 → 后面怎么剪都平 |
| 1 写稿 | `scripts/script-XX.json`，5–6 章 × 8–12 句，单句 ≤18 字 | 55 句 / 630 字 ≈ 117s | 超 25 字 → 字幕换行难看 |
| 2 估时 | `run.py plan XX` | 只看时长/字数，不花钱 | 估 105s 实出 103s（误差 2%）属正常 |
| 3 分屏 | 把连续同空间的句子标成同一 `panel`，写 `bg` + `el` | 每屏 2–4 句 | 分不出来 → 说明稿子没"场景感" |
| 4 配图 | 每屏一张 `-air` 底板；每卡一张素材 | `public/textures/lib/*.jpg` | 找不到就 `img.py` 生成，别硬凑 |
| 5 配音 | `run.py voice XX` | `public/audio/XX.wav` | 断触 → 检查是不是按章合成 |
| 6 对齐 | `run.py align XX` | `src/data/XX-timeline.json` | 字符匹配 <100% → 稿子有错字 |
| 7 合成 | `run.py build XX scripts/script-XX.json` | `film.json`（会打印 panel 列表） | 打印里 panel 数是 0 → `panel` 字段写错 |
| 8 渲染 | `run.py render XX` | `out/XX-raw.mp4` | 404 图片 → 路径是相对 `public/` |
| 9 混音质检 | `run.py mix XX` + `check.py XX` + 盲听盲看 | `out/XX-final.mp4` | 见 §7 / §7.5 |

`run.py all XX scripts/script-XX.json` 一次跑 5–9 步；**但第 3、4 步永远是人做的**。

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

> `panel` **不是卡型**，是 `lines[].panel` 字段（见 §5.6）。同一屏的句子不出卡片，只出字幕 + 元素。

---

## 5. 动画（只讲方法，实现交工具）

细节在 `ANIMATION.md`，四条硬规矩先记住：

1. 单镜 2.5–3.0s，最长 4.0s；连续静止 ≤ 3s。
2. 入场起点透明度用 **0.15**，不要 0（0 会在切点闪白）。
3. 转场 85% 是硬切；fade 只用在章节之间和"错误→原理"那一步。
4. 一屏 ≤ 3 个元素（panel 屏内元素另算，见 §5.6「排布三规则」）；大字卡每行 ≤ 9 字，只标红 1–2 处。

卡通素材**不是动画，是图**：一张停 1.2–2.0s，硬切翻页，每张 1.000→1.035 微推（顺带把静止占比压到 0）。

### 5.5 「屏」（panel）：凯哥真正的手法，我们之前理解错了

实测 `qa2\ref\v1-shuaishuai.mp4` 200–212s（2fps，24 帧，分区帧差）：

```
3.5–4.0s  diff 27→53   整屏硬切
5.0s      diff 0.13    完全静止
5.5s      diff 93.6    整屏硬切
6.5–7.0s  mid 62 / top 0.08  ← 只有中间在变，整屏没切
8.0–8.5s  diff 0.11    完全静止
9.0–11.0s bot/mid 涨、top 很小  ← 局部元素在动
9.5s      diff 75     整屏硬切
```

**结论：他的"动"分两层**——① 整屏硬切（diff 50+，约每 3–4s 一次）；② **层内元素变化**（只有某一块 diff 高，其余 <5）。中间还会**故意死静 1–1.5s** 让人读字。

所以正确单位不是"句"，是"**屏**"：

| 概念 | 规格 | 我们的现状 |
|---|---|---|
| 一屏（panel） | **2–3 句，7–8 秒**，背景固定 | ✗ 我们一句一镜，2–3s 就整屏换 |
| 层 1 背景 | 全屏 1.000→1.03 缓推（同向） | ✓ 已有（1.028） |
| 层 2 前景 | **反向** translateX 10–16px（背景右，前景左） | ✗ 完全没有 |
| 层 3 元素 | 大字/红叉/截图**弹入**（scale 1.15→1，4 帧）+ 音效 | ✗ 只有整卡切换 |
| 死静 | 允许 1–1.5s（读字时间） | 我们现在是"一直微动" |

**"PPT 感"的真因不是图不够，是动效只在一层**（整屏切 + 全屏同向微推 = 一张图在平移）。
加上"前景反向"和"元素弹入"两层，同样的素材立刻有纵深。

> 音效侧实测：高频瞬态密度 凯哥 111 次/分 vs 我们 94.5 次/分——差距不大，音效不是主要缺口，**画面层级才是**。

---

### 5.6 Panel（一屏多句，默认排法）

**这是凯哥真正的手法，比"一句一镜"更高一级。**

实测：`v3-pinlv.mp4` 280–287s 男主画面**连续 8 秒没换**，283s 只插 0.5s 女生反应图；492–499.5s 粉色底板不动，元素逐个长出来（对话框→房子→一家三口→箭头）。帧差：286s 边缘差 0.57 / 主体差 0.27——**像素级静止**。

所以"衔接好"不是生成质量，是**根本没换画面**。

#### 写法（script json）

```json
{"text": "你以为这叫真诚。", "panel": {"id": "p2", "bg": "textures/lib/sofa-air.jpg"},
 "el": {"kind": "bubble", "text": "我在等她回", "x": 74, "y": 26, "w": 300, "size": 30}},
{"text": "在女生眼里，这叫没有生活。", "panel": "p2",
 "el": {"kind": "label", "text": "没有生活", "x": 74, "y": 50, "size": 32}},
{"text": "你把她当回事，她不把你当回事。", "panel": "p2",
 "el": {"kind": "num", "text": "0", "x": 76, "y": 70, "size": 150}}
```

- 同 `panel` 值的**连续句子**合成一屏，底板固定，字幕仍按句走
- 屏内句子**不要再写 card**（写了会被忽略）
- 一屏 2–4 句 = 5–9 秒；超过 4 句就换屏

#### 一句出多个元素（`els`）

同一句要先后弹两个元素时，别拆句子，写列表：

```json
{"text": "你以为这叫真诚，在女生眼里，这叫没有生活。", "panel": "p2",
 "els": [{"kind": "bubble", "text": "我在等她回", "x": 70, "y": 20, "w": 300, "size": 30},
        {"kind": "label",  "text": "没有生活",   "x": 28, "y": 66, "size": 32}]}
```

`build_film.py` 按列表顺序给 `at` 累加 **0.35s**（第一个对齐句首，第二个晚 0.35s 弹入）。
合并句子时特别有用：两句并一句会丢掉后一句的 `el`，用 `els` 把它挂回来，元素一个不少。

#### 元素（7 种）

| kind | 用途 | 关键参数 |
|---|---|---|
| `bubble` | 对话气泡（白底黑框带尾巴） | `text` `w` `size` |
| `label` | 标签块（默认红底白字） | `text` `size` `color` |
| `num` | 超大数字（默认红） | `text` `size` |
| `icon` | 线性图标 | `name` `size` `color` |
| `arrow` | 长箭头 | `size` `color` |
| `dot` | 红点 + 文字 | `text` `size` |
| `box` | 结论块：有 `text` = 深底（`rgba(18,16,13,.86)`）白字 + 左侧红条；无 `text` = 虚线框高亮 | `text` `size` `w` `color` |

`icon.name`：`check` `cross` `house` `family` `clock` `phone` `money` `up` `down` `arrow`

坐标 `x/y` 是百分比（元素中心），已做 12–88% / 12–84% 钳制，不会出画。**y 不要超过 74%**（会和字幕撞）。

#### 排布三规则（不做就是"PPT 列表"）

写完第一版 panel 我统计了 25 个元素：**x 只有 74 和 76 两个值，全在右边缘一列**；
`label` 占 40%。看片的感觉是"右边挂了个信息栏"，不是"画面在演"。

| 规则 | 具体要求 | 反例 |
|---|---|---|
| 1 禁一列 | 同屏 ≥3 元素时，x 必须跨 **2 个以上区域**（左 20–35 / 中 45–55 / 右 65–80 各选） | 三个元素全 74，竖排 |
| 2 label ≤ 1 | 每屏最多 1 个 `label`，其余必须是 `bubble`（具体台词）或 `icon`（状态） | "没有生活""需要争取""怕被拒绝" 连贴三屏 |
| 3 可压人物 | 元素允许半压人物（凯哥的对话框经常压到脸边），只要不遮眼睛 | 全部躲在最右侧空白处 |

y 建议分档 **24 / 48 / 70**，三个元素错开；超过 74 会撞字幕。

> 记住凯哥的元素是**在讲故事**：`她：哦`（气泡）→ `3`（数字）→ 房子+一家三口（图标）。
> 不是"关键词列表"。写元素前先问：**这个元素是在演，还是在复读？**

**这三条不靠自觉，靠 `pipeline/audit.py` 卡**（见 §7.0）。EP02 第一版就是规则写在这里、
一句没执行，实测 3 屏挤成一列、label 占 40%。跑一次 audit 会直接列出来。

#### 哪些句子该进 panel

不是所有句子都能并屏。判据按顺序：

1. **同一空间、同一动作链**（都在沙发上 → 可以并）
2. **口语上是一口气**（逗号结尾、或者后句是前句的补充 → 可以并）
3. **中间没有换卡型的必要**（section / board / wrong / stat / outro 一律独立，不进 panel）
4. 一屏 **2–4 句 / 5–9 秒**；超过 4 句就断屏，否则元素挤成一片

理想比例：**一集 55 句 → 11–14 屏覆盖 60–70% 时长**，剩下 30–40% 给章节标题、黑板、红叉、大字、outro。

#### 底板必须"留白"

元素要放在空白处，所以底板不能人物占满。生图提示词必须包含：

```
人物位于画面左侧三分之一处，画面右侧三分之二是干净的空墙
```

成品底板存 `public/textures/lib/{scene}-air.jpg`（`-air` 后缀 = 留白版）。
没有留白的图只能做"整屏卡片"，不能做 panel。

#### 真人底图（`photo`）：panel 的第二种底板

卡通底板讲抽象概念，真人照片讲"处境"。同一种 panel，只换底板来源：

```json
{"text": "你不是不会聊，是不敢开口。", "panel": {
  "id": "p5", "photo": "textures/real/coffee-left.jpg", "text_zone": "right"},
 "el": {"kind": "box", "text": "不敢开口", "x": 72, "y": 46, "size": 34}}
```

| 字段 | 取值 | 作用 |
|---|---|---|
| `photo` | 相对 `public/` 的路径 | 有则**替代** `bg`，走真人分支；没有就回落卡通底板 |
| `text_zone` | `right`（默认）/ `left` | 文字放哪侧 |

真人分支自带三件事，不用在 script 里写：

1. **Ken Burns 缓推**：`scale` 1.08 → 1.14 线性走完本屏，`transformOrigin: 50% 35%`（锁头部）
2. **反向微移**：`text_zone=right` 时画面向左推（`translateX -1% → +1%`），把人物"让"给文字侧；`left` 反过来
3. **文字侧压暗**：从 42% 处开始渐变，58% 到 `rgba(8,6,4,.78)`，100% 到 `.88`——保证白字在亮背景上也压得住

`build_film.py` 的 `panel_photo()` / `panel_zone()` 把这两个字段写进 `film.json` 的 panel 对象（`Remotion` 侧 `Panel.tsx` 读）。

**素材硬要求**：真人照必须"人物偏一侧 + 另一侧干净"。人物居中、脸占满屏的图，压暗区没地方落字，只能整屏当背景板（那就别用 panel，用 `card.type=photo` 之外的普通镜头）。

> 判断标准：`text_zone` 那一侧的 40% 宽度里，**没有脸、没有手、没有主体动作**。有就换图，别指望压暗遮住——压暗到 .88 会把人拍黑。

#### 验收

抽 2 帧（同屏首句、末句），比**画面边缘 10% 区域**的平均色差：
- <12 → 底板稳定，合格
- 12–25 → 轻微漂移，可接受
- >25 → 换图了，检查是不是写错 panel id


## 6. 素材

### 6.0 他到底有没有素材库（实测，别再猜）

拿 4 集、每 2s 抽帧共 1316 帧，筛出卡通 997 帧，算 16×16 dHash 两两比：

| | 抽帧 | 卡通帧 | 跨集近重复 (d≤12) |
|---|---|---|---|
| v1 锐评变帅 654s | 327 | 250 | — |
| v2 朋友圈 698s | 349 | 238 | — |
| v3 聊天频率 632s | 316 | 302 | — |
| v4 土纯风 648s | 324 | 207 | — |
| 合计 | 1316 | **997** | **0 对** |

**结论一：他没有买公共素材包**——997 张跨 4 集一对重复都没有，公共包必然撞图。

**结论二：但角色是固定的**——v3/v4 的男主是同一人（黑衬衫、黑乱发、细长眼、粗描边），v4 还配了固定的粉发女配。

**结论三：同集内几乎不复用**——按"间隔 ≥6s"过滤（排除同镜停留的假重复）：

| | 跨镜复用 | 最长间隔 |
|---|---|---|
| v1 | 0 处 | — |
| v2 | 0 处（79 对都在同一镜停留段内） | — |
| v3 | 7 处 | 164s |
| v4 | 2 处 | 24s |

所以他的"素材库"是 **角色 + 提示词模板**，不是图片库：定 1 个男主（+ 可选女配），每集按脚本现做 20–40 张新图，一集里基本一张只用一次。

> 对我们意味着：**别囤图，囤"角色设定 + 12 张 air 底板"**。
> 36 张库不是"一集用完"，是"两周不用补"。

**顺手否掉的另两个猜测**（都有反证）：
- `7210` 水印不是素材商编号——真人镜头也盖着它，是成片后统一打的团队/防搬运编号。
- 配音不是 AI——F0 中位 163Hz、p10 104 / p90 262（跨度 158Hz）、RMS 动态 7.1dB，AI 男声跨度普遍 60–100Hz。而且"没有气口"是**剪气口**的结果，不能反推 AI。

### 6.1 形态铁律：卡通为主，字幕常驻

凯哥的片子**不是"文字卡 + 偶尔插画"，是"卡通图铺底 + 底部字幕"**。抄形态就抄这一条：

| 项 | 规格 |
|---|---|
| 卡通（含 slides 卡） | **占全片 50–65% 时长**（EP02 实测 39%，偏低） |
| 底部字幕 | 34–40px，距底 90–110px，黑边 5；**卡片大字与语音同句时不出**（见下表） |
| 画面大字 | **只在需要"钉一句"时用**（每 8–10 句一次），且**不得与字幕重复**（重复=废信息） |
| 其余画面 | 黑板 / 清单 / 红叉 / 对比 / 实拍局部 / 长文卡，合计 35–50% |
| 单镜 | 2.5–3.0s，卡通一张停 1.2–2.0s |

**字幕去重（`build_film.py` 的 `NO_SUB`）**：卡片大字读出来和语音是同一句话 → 删字幕。
`copy/hook/section/wrong/list/outro/stat` 不出；`slides/board/no-list/image/cmd/brow/posture/color/teacher/annotate` 与 panel 句照常出。
EP02 实测 55 句 → 21 句无字幕，剪映字幕轨 55 → 34 段。开头三张大字卡删掉白字后立刻干净，这是"第一眼观感"的开关。

> 判断是否抄对：静音看一遍。如果画面本身在"讲事"（人物在做事），对；如果画面只是把字幕放大，错。

### 6.2 素材从哪来（四层，按顺序走）

> **顺序陷阱**：不要"先攒一批图再往句子上套"。EP02 第一版就是这么干的，结果讲「周末在家躺着」画面在面馆吃面、讲「聊两周还在问在干嘛」画面是咖啡馆空椅子。
> 正确顺序：**先列 11–14 句"这句话在什么场景"，再按场景去出图**。判据一句话——把底板遮住只听语音，能猜出画面里的人在干什么才算对。

```
① 本地素材库 → ② 网络检索 → ③ AI 生成 → ④ 复用（受限）
```

| 层 | 动作 | 工具 | 什么时候跳过 |
|---|---|---|---|
| ① 本地库 | 先查已有什么，避免重复买/重复生成 | `public\textures\{cartoon,slides,stock}\` + `assets.json` | 从不跳过 |
| ② 网络检索 | 关键词 = **主体+动作+场景+风格**（中文比英文准） | `tools\stock.py`（bing / commons / openverse / pexels） | **命中率 < 30% 立刻转 ③**，不要硬凑 |
| ③ AI 生成 | 身份串 + 固定 seed，锁同一个人 | `tools\img.py` | 场景必须精确但图库没有时，直接用这层 |
| ④ 复用 | 只在同场景相邻句用，跨场景禁止 | `assets.json` 查使用记录 | — |

**实测结论（别盲信检索）**：`cn.bing.com` 对分镜级描述命中很低——搜"男生 卡通 沙发 玩手机"出来的是证件照和写真；搜英文会被强制中文化成"Flat 乐谱 App"。所以检索是"捡便宜"，**主力永远是 ③ AI 生成 + ① 沉淀**。

检索命令（必须先 preview 再决定下载哪张）：

```powershell
& $py tools\stock.py search "男生 瘫坐 沙发 看手机 扁平插画" --n 12 --json qa2\q-sofa.json
& $py tools\stock.py preview --json qa2\q-sofa.json --out qa2\q-sofa.jpg   # 12 张拼一张，肉眼过
& $py tools\stock.py save 2 7 --json qa2\q-sofa.json --out lbr-promo\public\textures\stock --name sofa
```

### 6.3 "对上"三问（不过就换图，不许"差不多"）

对每一句，逐条问：

1. **主体**在吗？——这句话说的是沙发、地铁、面馆、镜子，图里就得有那个东西。
2. **动作/状态**对吗？——"瘫坐"不能配"站直"，"低头"不能配"抬头"。
3. **情绪**对吗？——"丧/被拒/将就"不能配"自信微笑"。

三问全过才算对上。**宁可多生成 3 张挑 1 张，也不要 1 张图配 5 句话。**

### 6.4 复用矩阵（防"一张图贴全片"）

| 规则 | 数值 |
|---|---|
| 一张图在一集内出现 | ≤ **2 次** |
| 同场景连用 | ≤ **3 句**（4–8s），之后必须换机位或换场景 |
| 同一张图两次出现的最小间隔 | ≥ **40s** |
| 跨章复用 | **禁止**（本章的图只服务本章） |
| 跨集复用 | 允许，但换集要换姿势/换机位，不能原样搬运 |

登记表 `lbr-promo\pipeline\assets.json`（每张图一行）：

```json
{"id":"sofa-01","scene":"客厅沙发","tags":["瘫坐","刷手机","丧"],
 "file":"textures/slides/u13b.jpg","used_in":["ep02#12","ep02#14"],"source":"ai:wanx seed20261124"}
```

新增素材必须登记；排片前查 `used_in`，同一集里已用 2 次的图直接排除。

### 6.5 排布（一条 2 分钟片的骨架）

```
序（5 句）      卡通 2–3 张 + 1 张钩子大字
每章（10–12 句）卡通 4–6 张 + 黑板 1 + 清单/红叉 1 + 大字 1–2
收尾（6–7 句）  卡通 1–2 张 + 大字 + outro
```

同场景连用示例（这才是"衔接自然"）：

```
#12 u13b 沙发-瘫坐刷手机   ← 中景
#13 u14b 沙发-仰头叹气     ← 同场景换姿势
#14 u15b 深夜-手机光照脸   ← 换时间/机位
```

三张都是同一个人、同一件白 T，动作递进，观众感觉"他在演"，不是"在翻 PPT"。

### 6.6 生图（锁人配方，务必照抄）

```powershell
$id="亚洲男生，二十岁出头，单眼皮，眉毛平直，鼻梁不高，脸型偏瘦，不戴眼镜，短黑发微乱，穿纯白圆领T恤和深灰长裤"
$base="扁平矢量卡通插画，同一个人物：$id，中景，简洁粗黑描边，低饱和暖色调，画面右侧留白，无文字"
& $py tools\img.py "$base，瘫坐在沙发上盯着手机，屏幕发出冷光" lbr-promo\public\textures\slides\u13b.jpg --seed 20261124
```

- **换 provider / 换 seed 一定漂脸**；只用 `wanx2.1-t2i-turbo` + `--seed 20261124`。
- 别写"帅气/英俊"这类词，会漂成另一个人；只写可核对的物理特征。
- 每张图配一句"这张代表哪句话"，写进 `assets.json` 的 `tags`。

已有素材：实拍 `public\textures\bs\`（brow/hair/mirror/posture/skin/wear）；卡通 `public\textures\slides\`（`u3b u4b u5b u6b u7b u8b u11b u12b u13b u14b u15b` + 旧风格 `s1–s5`，**新旧不混用**）。


---

## 7. 质检（`check.py`）

11 项：文件大小 / 成片时长 / 总字数 / 句数 / 整体字秒 / 单镜中位 / 最长单镜 / 语速异常句 / 最长静止段 / 静止占比 / LUFS / dBTP。

硬指标（FAIL 才退 1）：文件大小、时长、响度、真峰值。风格指标记 WARN。
**短样片（< 30s）自动把大小与字秒降为 WARN**，方便 cardtest。
**注意**：响度只有跑 `*-final.mp4`（混过音）才有意义；拿 raw 喂 check 会显示 −23 LUFS，那不是缺陷，是你跑错文件。

已知基线：EP01 v6 103.2s / 525 字 / 5.09 字秒；EP02 v3 117.5s / 630 字 / 5.36 字秒 / 静止 10% / 卡通 39%。
单镜中位 1.9–2.5 属正常（一句一镜必然偏短），别为这条改稿。

> **静止不是缺点**。凯哥原片 0–30s 有一段连续 5 秒画面完全不动（11.5–16.5s），全段静止占 43%。
> 我们一度把 49% 当 bug 去压，压到 23% —— 这不是改进，只是换了个风格。别为这条指标改稿。

### 7.0 排布体检（`audit.py`，渲染之前跑）

`check.py` 看成片，量不到"构图像不像 PPT"；`audit.py` 只读 `film.json`，10 项构图与节奏判定，**有 FAIL 就别渲染**。

```powershell
& $py lbr-promo\pipeline\audit.py          # 默认读 src/data/film.json
& $py lbr-promo\pipeline\audit.py --json   # 机器可读
```

| 项 | FAIL 线 | WARN 线 |
|---|---|---|
| 同屏 ≥3 元素时 x 跨度 | < 25 个百分点（挤成一列） | — |
| 每屏 label 数 | > 1 | — |
| 元素 y | > 74（撞字幕） | — |
| label 占全部元素 | — | > 30% |
| icon/arrow 占比（剪映里会变 emoji） | — | > 25% |
| panel 一屏时长 | — | 最短 < 4.0s |
| 卡片句单镜中位 | — | < 2.3s（凯哥 2.75） |
| 卡片句 < 1.5s 的短镜 | — | 有 |
| slides 图片复用 / 底板复用 | — | 出现 2 次以上 |
| 音效条数 | — | 0（还没做音效层） |

EP02 实测（2026-11-25，元素重排后）：**FAIL 0 · WARN 4** —— 3 屏挤成一列已修（元素改为按底板人物位置分两侧，p2/p3/p5/p9/p10 重排）、label 占比 40%→29%（三处 `label` 换 `box` 结论块）、icon/arrow 28%→25%、`u12b.jpg` 重复已换 `u8b.jpg`。剩余 WARN 全是风格项：panel 最短 2.6s（p11 收尾只 2 句）、卡片单镜中位 2.14s、5 句 <1.5s、音效 0——这三项要动稿子重配音，不是改 json 能解决的。

改元素只改 `script-ep02.json` 里的 `el.x/el.y/el.kind`，然后 `build_film.py` → `audit.py`，两步十秒，不用渲染。**每张底板人物位置不同，锚点要按图定**：人物偏左就全走右侧 + 左下角，人物居中就左右分两侧（实测 `metro` 人物正中、`office` 人物贴左缘、`sofa` 人物占左三分之二）。

### 7.5 素材专项验收（人工，3 分钟）

跑完片必须自己过一遍这五条，任一不过就回炉：

1. **盲听**：关掉画面听一遍，讲得通吗？（讲不通=稿子问题，不是素材问题）
2. **盲看**：静音看一遍，画面在"演事"还是在"复读字幕"？（复读=素材没对上）
3. **数卡通**：卡通时长占比是否 ≥ 50%？（用 `shot_stats.py` 或目测）
4. **查复用**：有没有同一张图在一集里出现第 3 次？有没有跨章复用？
5. **抽 6 帧**：随机抽 6 帧拼图，每帧都能说出"这句在讲什么"吗？


### 7.6 自评五维（给自己打分，别自我感觉良好）

跑完片按这五项打分，**任一项 < 60 就要回炉**：

| 维度 | 及格线 | 怎么量 | EP02 v4 实测 |
|---|---|---|---|
| 结构 | panel 覆盖 **≥ 60%** 时长 | 读 `film.json` 求和 | **43%**（51s/117s）→ 55 分 |
| 素材 | 每屏独立底板，人物宽 ≤ 45% | 目测 + 抽帧 | 有 12 张 air，人物仍占 ~50% → 75 分 |
| 元素 | label ≤1/屏；同屏 x 跨 ≥2 区域 | 脚本统计 | **x 只有 74/76，label 占 40%** → 40 分 |
| 节奏 | 整屏切换中位 2.6–3.0s | 统计 start 差 | 2.44s（偏密）→ 50 分 |
| 声音 | 5.0–5.5 字秒，0 异常 | `check.py` | 5.36 / 0 异常 → 95 分 |
| **整体** | | | **60 分** |

一段统计脚本（复制即用）：

```python
import json
d = json.load(open(r'lbr-promo/src/data/film.json', encoding='utf-8'))
ps = d['panels']
els = [e for p in ps for e in p['elements']]
cov = sum(p['end'] - p['start'] for p in ps)
print(f"panel {len(ps)} 屏 / {sum(p['count'] for p in ps)} 句 / 覆盖 {cov/d['totalSeconds']*100:.0f}%")
print("x:", sorted({e.get('x') for e in els}))
print("label 占比:", round(sum(1 for e in els if e['kind'] == 'label') / max(1, len(els)) * 100), "%")
cuts = sorted([l['start'] for l in d['lines'] if not l.get('panel')] + [p['start'] for p in ps])
import statistics as st
print("切换中位:", round(st.median([b - a for a, b in zip(cuts, cuts[1:])]), 2), "s")
```

---

## 8. 踩过的坑

**完整故障对照在 `pipeline/TROUBLES.md`（五类 30 条）**，按"最先想到的"排序。这里只留最高频的 6 条：

| 症状 | 先查 | 修法 |
|---|---|---|
| 打开剪映工程一半是黑 | `jy_check` 的「画面覆盖」 | 跑 `jy_cards.py --render` 垫卡片静帧 |
| 元素跑到下半屏 | `pct_y` 符号 | 剪映 **y 轴向上为正**，`top:26%` → `+0.48` |
| 一句话横贯全屏 | `max_line_width` | 按 `el.w/1280` 折算，默认 0.82 太宽 |
| 改了新稿渲染出旧片 | `run.py build xx` 漏第 3 参数 | 永远写全：`build xx scripts/script-xx.json` |
| 声音断触 | 逐句拼接过 | 按章合成 + 轻削静音 |
| 草稿换机器全黑 | 素材是绝对路径 | `jy_localize`（默认开），看 `jy_check` 的「素材本地化」 |

其余症状速查（详见 TROUBLES）：`切点闪白`=opacity 从 0 起；`怪声`=用了 atempo；`Permission denied .wav`=TEMP 没指到工程内；`ProxyError`=设 `NO_PROXY`；`404 textures/lib`=图还在 `slides/`；`panel 打印 0 屏`=首句没给 `bg`；`NameError`=here-string 吃了引号。

---

## 8.5 剪映衔接（想手工微调时走这里）

**什么时候值得进剪映**：加音效/花字、手动改字幕断句与样式、拖关键帧曲线。
**什么时候别去**：批量出片、元素要跟语音变化、只是字幕不同步（改稿重跑更快）。

两条路线（细节见 `pipeline/JIANYING.md`）：

- **A 干净素材回剪映**：Remotion 导无字幕版 + `subtitles.srt` + `voice.wav` + `shots/`。
- **B 直接出可编辑工程**（推荐）：`python tools\jy_from_film.py` 把 `film.json` 变成剪映草稿，
  底板 / 元素 / 字幕 / 配音自动分轨，打开就是工程。

```powershell
# 换设备第一步（探测安装目录 / 版本 / 草稿根 / skill 路径）
& $py tools\jy_env.py --write-env
& $py tools\jy_env.py --check

# 卡片静帧（把 copy/section/board/stat/slides/outro 这些非 panel 句垫满，否则一半黑场）
& $py tools\jy_cards.py --render

# film.json → 剪映工程
& $py tools\jy_from_film.py --spec-out qa2\jy-spec-ep02.json
& $py tools\jy_check.py "E:\剪映5.9版本免激活(1)\草稿\JianyingPro Drafts\EP02_剪映工程"
```

三条会毁掉整条工程的事实（`JIANYING.md` §4 有完整说明）：

1. `tim()` 单位是**微秒**，传 `0.35` 会变 0；用 `us()` 或 `"0.35s"`。
2. 装饰（动画/转场/滤镜/蒙版/淡入）必须写在 `add_segment()` **之前**，否则素材没登记、只留悬空引用。
3. 剪映**同一轨道片段不能重叠**；元素要"停留到屏尾"就按 panel 内序号分轨。

另外三处**最容易出"看着不对但说不清"的瑕疵**（`JIANYING.md` §10 有实测证据）：

4. **只映射 panel 会有一半黑场**。EP02 实测 panel 只占 51s/117s，其余 66s 全黑 → 必须跑 `jy_cards.py` 垫卡片静帧。
5. **剪映 y 轴向上为正**，`top:26%` 要写 `transform_y=+0.48` 不是 −0.48；写反了整层元素垂直镜像（元素全跑到下半屏）。
6. **剪映没有定宽文本框**，只有 `max_line_width`（默认 0.82）；不按 `el.w/1280` 折算，一句话会横贯全屏。

ep02 实测（修完）：视频轨 41 段（底板 11 + 卡片 30）/ 元素 24 个 / 字幕 55 段 / 配音 1 段，
`new_version=110.0.0`、**黑场 0.00s**、`issues=[]`。验收看 `jy_check` 的「画面覆盖」段落。

**草稿可迁移（默认已开）**：`jy_draft.build()` 在 `script.save()` 之后自动跑 `jy_localize.localize()`
——素材复制进 `<草稿>/assets/`，路径改成剪映的占位符相对形式
`##_draftpath_placeholder_0E685133-18CE-45ED-8CB8-2904A212EC80_##/assets/xxx`，`config.material_save_mode=1`。
**不这么做，草稿写的是绝对路径，换机器/发给别人全片变黑。**
ep02 实测：42 个素材进 assets（13.26 MB），`jy_check` 显示 `素材本地化：✓ 草稿内 42 个 / 外部绝对路径 0 个`。
配套坑：`jyai\repair.py` 的 `validate()` 原来用 `os.path.isfile(path)` 判素材，遇占位符必报「素材丢失」——
已加 `resolve_material_path()` 解析占位符（`JIANYING.md` §17 有全文）。

**人像美化 / 花字**（capcut-mate 的 metadata 搬运）：

```powershell
# 美颜写在 spec 顶层 beauty 字段
# "beauty": {"skin": {"smooth": 40, "even": 30}, "shape": {"slim": 25}, "tint": "暖白:60:20", "look": "中国妆:80"}
& $py tools\jy_beauty.py --list                      # 有哪些滑杆
# 花字写在 item 里："text_effect": "白字红边立体字"
```

机制：每条非 0 滑杆 → `materials.effects` 一条 `type=figure` + 挂到片段 `extra_material_refs`，
并**必须同时补一条 `makeup-root`**；滑杆 0 = 不写（等价剪映里"关闭"）。花字走 `TextSegment.add_effect(id)`，
同样必须在 `add_segment()` 之前调。

---

## 8.6 复刻一条新参考片（replica 链路）

**场景**：别人给一条动画式视频（图文卡 / 聊天气泡 / 大字卡 / 文档页 / 卡通角色 / 进度导航），
要照着它的结构做一条同构视频。**换片只换第一个参数，不改代码。**

### 一条命令

```powershell
$PY = "E:\miniconda\envs\JupyterProject\python.exe"   # 见下方「解释器」小节，别用错
& $PY tools\replica.py auto "D:\ref\新参考片.mp4" --name 新片_自动复刻
# 只想要 spec、不要草稿： 加 --no-jianying
# 只分析前 3 分钟：       加 --dur 180
```

产物三件：

| 产物 | 位置 | 说明 |
|---|---|---|
| `spec.json` | `qa2\replica\out\<片名>.spec.json` | 结构事实：meta / subs / scenes / sections / voice |
| `assets\` | 同上目录 | 每屏代表帧 `p000.jpg…` + `voice.wav`（原片音轨） |
| 剪映草稿 | `…\JianyingPro Drafts\<name>\` | **图片轨 + 字幕轨 + 配音轨**，直接打开就能改 / 导出 |

### 分步（要单步调参时）

```powershell
& $PY tools\replica.py extract --video REF.mp4 -o out\ref.spec.json   # 或直接跑 replica_extract.py
& $PY tools\replica_shots.py --spec out\ref.spec.json                  # 每屏抽帧 → assets[]
& $PY tools\replica.py validate --spec out\ref.spec.json               # 本地可判项体检
& $PY tools\replica.py jianying --spec out\ref.spec.json --name 片名   # 出剪映草稿
```

### 实测（2026-11-28，两条不同片子）

| 源片 | 分析窗 | 字幕 | 屏 | 章 | validate | 草稿 |
|---|---|---|---|---|---|---|
| 女生想和你处对象…6个问题 | 547.36s 全片 | 313 段 | 61 | 6 | PASS（diff 0.18s） | `Q6_自动复刻_v3` |
| v3-pinlv | 180s | 126 段 | 38 | 3 | PASS（diff 0.02s） | `V3_自动复刻` |

手工标注版是 58 屏 / 313 字幕，自动版 61 屏 —— 屏数差 5%，字幕数完全一致。

### 它怎么判的（三层，前两层在本机跑完，不联网不花钱）

1. **事实层**：ffmpeg 探针 + faster-whisper 转写 + 帧差切点 + 每镜中点帧的逐像素版式量测
2. **归类层**：`1 shot = 1 屏`（见坑 2）；每屏按 `rows/cols/bright/contrast/sub_density` 判
   `chat / title / doc / scene` 四型；字幕超 24 字才二次切；章节先按 ≥1.15s 停顿切，
   切不够就按目标章数（约 90s 一章，3–8 章）等分
3. **语义层（未接）**：每屏 prompt 目前是「版式事实 + 占位描述」。要重画就把
   `scenes[].assets[].file` 换成 GPT 出的图、`voice.wav` 换成克隆音，**下游一个字都不用改**

### 解释器（踩过两次，照抄）

| 解释器 | faster-whisper | pyJianYingDraft | 能干什么 |
|---|---|---|---|
| `E:\miniconda\envs\JupyterProject\python.exe` | ✅ 1.2.1 | ✅ | **全链路**（ASR + 建草稿） |
| `D:\pythons\python3.12\python.exe` | ❌ | ❌ | 只能 `extract --segs`（复用现成字幕）+ `shots`，出不了草稿 |

`replica.py auto` 用 `--python` 指定子脚本解释器，默认跟随当前解释器。

### 坑（都在这条链路上真实踩过）

1. **`frame_profile` 的 `bright` / `contrast` 是 0–1 量纲，不是 0–255。**
   按 0–255 写阈值（`bright>=140`）永远为假，会把全片判成一个类型。
2. **屏边界来自「画面内容变化」，不是「版式差异」。** 这类片子整片版式指纹几乎不变
   （61 帧相邻距离中位 0.028，最大 0.049），拿指纹聚类会把 61 屏合成 1 屏。
   `analyze_ref` 的 shots 已经按内容变化切好了，**直接 1 shot = 1 屏**，只清理
   <0.3s 抖动与 <0.8s 的同型碎屏。
3. **`--dur` 只分析片段时，`meta` 时长要取窗口终点**（`start+dur`），
   否则末屏会被拉到整片时长、validate 直接报字幕越界。
4. **剪映导出的契约是 `scenes[].assets[].{slot, file}`（数组），不是 `asset.path`。**
   同 `slot` 进同一条视频轨，`file` 相对 spec 目录解析；每项自动挂 1.0→1.035 慢推。
5. **配音走 `spec.voice.wav`** → audio 轨「配音」；不填就没有配音轨（不报错，只提示）。
6. **`qa2\refanalysis\<片名>\facts.json` 是事实层缓存**，改代码后要 `--refresh` 才重跑；
   正常复用是秒级。
7. **静态文档页 / 长页滚动 / 卖课页会留下一整块超长屏**（帧差抓不到边界）。
   实测一条 607s 片：11 屏超 8s，最长 **31.67s 覆盖 17 句**。
   `split_long_screens()` 会按字幕句边界补切（切点落在句间空隙中点，不切断任何一句），
   修完 149 屏 → 163 屏、最长屏 8.0s、超 8s 屏 0 个。
8. **`assets/` 必须按片分区**（`assets/<spec 名>/pNNN.jpg`）。早先所有 spec 共用
   `out/assets/p000.jpg…`，后跑的片会把先前片的 p000+ 覆盖掉 —— 草稿因为已本地化看不出来，
   但重导旧草稿就会拿到错的画面。现已按 spec 名分目录，旧 spec 需重跑一次 `replica_shots`。

### 8.6.1 换画面：`replica_redraw.py`（把别人的截图换成自己的插画）

结构级复刻用的还是原片截图；要交自己的片子，画面得重画。这一步就是干这个的：
**按每屏的字幕语义生成一张插画，替换该屏的 `assets[].file`**，其余（屏位/字幕/章节/时长）不动。

```powershell
# 先小样 6 屏看风格对不对（花 6 张的钱）
python tools\replica_redraw.py --spec "qa2\replica\out\<片名>.spec.json" --only 0,2,7,11,16,21
# 满意后全量（163 屏约 40–110 分钟，后台跑）
python tools\replica_redraw.py --spec "qa2\replica\out\<片名>.spec.json" --apply
# 后悔了
python tools\replica_redraw.py --spec ... --revert
```

- **通道**：`qa2/gpt/relay.json`（apimart 中转，`model=gpt-image-2`，异步 task → 轮询 → 取 `url[0]`）。
  `tools/img.py` 的 `gen_openai()` 已经把这套封好了（`size="16:9"`、`resolution=1K`）。
- **风格是一条常量** `STYLE`（极简扁平矢量、暖米白底、珊瑚橙+墨绿+暖灰、大量留白、**画面里不要任何文字**），
  按 `mode` 再分模板（scene=日常场景 / title=符号化图形 / chat=两人对话气泡留空 / doc=清单横线代替文字）。
  要换画风改这一处，别逐屏改。
- **语义来源是字幕**：`screen_texts()` 把该屏所有字幕拼成 ≤60 字的主题，塞进模板。
  所以反过来说——**字幕切分质量直接决定画面质量**，§8.6 的 `--sub-chars 24` 别乱调大。
- **`--apply` 每 10 屏增量存盘**：全量要跑一两个小时，中途断了不会白跑，重跑会覆盖同名。
- 落盘：`qa2/replica/out/assets/<片名>/redraw/pNNN.jpg`（原帧 `pNNN.jpg` 保留，随时可回退）。
- **交付前必须人眼过一遍**：即使 prompt 写了「不要文字」，模型仍会偶发写出标题字/乱码，
  `--only` 挑那几屏重画即可。
- **`--apply` 并发跑会互相覆盖 spec。** 单张慢到 60s+ 时可以开三路 `--only` 提速
  （如 55–90 / 91–126 / 127–162），三条线确实并行出图；但每路都是
  「读整份 spec → 改自己那几屏 → 整份写回」，后写的把先写的覆盖掉
  （实测 163 屏最后只有 86 屏真的指向 `redraw/`）。收尾要么串行补 `--apply`，
  要么事后统一重定向：遍历 `scenes`，`redraw/pNNN.jpg` 存在就改 `assets[0].file`。

### 8.6.2 换声音：`replica_voice.py` + `replica_assemble.py`（声音克隆）

五步，缺一步都不出声：

```powershell
# 1) 从原片挑 10–20s 最干净的人声当参考（本地 ffmpeg，不花钱）
python tools\replica_voice.py extract-ref "qa2\replica\segs-<片名>.json" "qa2\replica\ref.wav" --src "<原片>"
# 2) 建克隆音色（计费、且不会自动删除）
python tools\replica_voice.py create "qa2\replica\ref.wav" --yes
# 3) 等部署 OK
python tools\replica_voice.py wait
# 4) 逐句合成（392 段约 90 分钟，断点续跑：已存在的 wav 会跳过）
python tools\replica_voice.py speak "qa2\replica\out\<片名>.spec.json" "qa2\replica\voice-out" --yes
# 5) 按原片时间轴把分段铺回整条
python tools\replica_assemble.py --spec "qa2\replica\out\<片名>.spec.json" --voice-dir "qa2\replica\voice-out" -o "qa2\replica\voice.wav"
```

三个必须知道的硬约束（都真实踩过）：

1. **要带 `Client` 的 dashscope 2.x。** `voices.create / audio.tts.connect` 是 2.0 才有的接口，
   本机 conda 环境里那把 1.26.4 没有 `Client`。**别动 conda 环境**，建个独立 venv 最干净：
   ```powershell
   D:\pythons\python3.12\python.exe -m venv C:\Users\<你>\AppData\Local\venv-clone
   & "$venv\Scripts\python.exe" -m pip install dashscope==2.1.2 requests -i https://pypi.tuna.tsinghua.edu.cn/simple
   ```
   venv **别放 OneDrive 目录**（pip 装包会被同步拖到十分钟以上，实测卡死）。
2. **跑之前清 proxy 环境变量。** 系统 `no_proxy` 里带 `::1,[::1]` 会让 httpx 抛
   `InvalidURL: Invalid port: ':1]'`，而且 PowerShell 里 `NO_PROXY`/`no_proxy` 双份键会让
   `Get-ChildItem env:` 直接报「same key already added」。稳的写法：
   ```powershell
   foreach($n in @("HTTP_PROXY","HTTPS_PROXY","ALL_PROXY","http_proxy","https_proxy","all_proxy","NO_PROXY","no_proxy")){
     [System.Environment]::SetEnvironmentVariable($n,$null,"Process") }
   ```
3. **语速调不动，只能靠装配端压。** 这个克隆音色忽略 `speech_rate`（1.08 与 2.0 的段长只差 4%），
   而抖音原片语速很快（实测 5.2 字/秒），所以逐句合成会有大半超格。
   `replica_assemble.py` 对超格段用 ffmpeg `atempo` **保音高**压缩：
   `--max-tempo 1.6` 实测 36 段超格里修好 34、只截断 2；1.35 会截 7 段，2.0 只多修 1 段但听感变糙。
   `--fit raw` 不压（段会盖住下一句开头，只适合先听整体），`--fit trim` 硬切（丢字）。
   报告落在 `voice-out/assemble-report.json`，每段的窗长/段长/处理方式都在里面。

两个接口坑：

- `speak` 的输入**必须是 spec.json**（它有 `subs`）。直接喂裸 segs 数组会 `'list' object has no attribute 'get'`。
- `extract-ref` 的**第一个位置参数是 segs.json，不是视频**；视频走 `--src`。

### 8.6.3 出片：`replica_render.py`（spec 直接渲 MP4，不绕剪映/Remotion）

交付要一条 MP4。spec 里已经有渲片需要的全部事实（每屏起止 + 代表图、每句字幕、音轨），
ffmpeg 就够，不必绕 Remotion（那是「自己写剧本」那条线的引擎，数据格式不一样）。

```powershell
python tools\replica_render.py --spec "qa2\replica\out\<片名>.spec.json" `
    -o "qa2\replica\out\<片名>.mp4" --voice "qa2\replica\voice.wav"
# 只要画面不要字幕：加 --no-subs；画质：--crf 18（默认 20）
```

- 屏按 `scenes[].s / e` 铺，屏间空档自动用米白占位补满；缺图也走占位，不会断片。
- 字幕从 `subs[]` 生成 SRT 再用 `subtitles` 滤镜烧上去（`Microsoft YaHei` 22 号、白字黑边、`MarginV=28`）。
- 音轨用 `-af apad -shortest -t <总时长>` 钉死长度，避免音轨比画面短导致尾帧被砍。
- 实测：607.11s 片 → 163 屏 / 392 字幕 / 1280x720 / 30fps，成片 **10:07.11**，与原片时长**零误差**。

**四个坑（全是同一个病根：ffmpeg 的 cwd 被指到临时目录）**

1. **concat 列表里的图片必须写绝对路径。** 相对路径是相对 `list.txt` 所在目录解析的，
   而 list.txt 在临时目录 → 一定 `Impossible to open`。用 `im.resolve().as_posix()`。
2. **输出文件也要绝对路径**，否则 `Error opening output file`。
3. **末项要再写一遍 `file`**，concat demuxer 会吞掉最后一帧（已知怪癖）。
4. **别用 `tempfile.TemporaryDirectory()`**：退出时立刻删目录，而 ffmpeg 的 cwd 还指着它就报错。
   改 `mkdtemp` 并把现场（list.txt / sub.srt）留着，出问题能直接看。

**交付前必须全量重画**。没重画的屏用的还是原片截图，**原片自带的字幕会跟我们烧的字幕叠在一起**
（实测 300s 处能看到两层字）。`replica_redraw.py` 全量跑完再 `replica_render.py`，才是干净片子。

### 8.6.4 一条龙：新片进来怎么跑

按顺序七步，每步都能单独停、单独查：

1. **结构**　`python tools\replica.py auto "新片.mp4" --name 新片_复刻`
   → `spec.json`（屏/字幕/章节/时长）+ 原帧 `assets/` + 剪映草稿。先看 `validate` 是不是 PASS。
2. **定风格**　`replica_redraw.py --only 0,2,7,11,16,21`（6 屏小样，花 6 张的钱）。
   不满意改 `STYLE` 常量重跑，**不要逐屏调**。
3. **画全量**　`replica_redraw.py --apply`（并发提速的坑见 §8.6.1 末条）。
4. **克隆音**　`replica_voice.py extract-ref` → `create` → `speak --spec ...`（§8.6.2，
   要 `dashscope>=2.0` 的 `Client`，独立 venv 最省事）。
5. **铺音轨**　`replica_assemble.py --spec ... `（超格段 atempo，默认上限 1.6）。
6. **出片**　`replica_render.py --spec ... -o 成片.mp4 --voice voice.wav`。
7. **换草稿素材**　`replica.py jianying --spec ... --name 新片_复刻`（草稿指向重画图，可编辑交付）。

**实测耗时（607s 片 / 163 屏 / 392 字幕）**：结构 3min（ASR 占大头，有缓存就秒级）、
重画 1.5h（并发）、配音 5min、装配 1min、渲染 6min → **全流程约 2 小时**，
其中 90% 是等出图。

---

## 9. 现状

**已完成**

- 引擎：`build_film.py` 支持 `panel`（一屏多句 + 元素累加）；`Panel.tsx` 7 种元素，
  底板两通道：卡通 `bg` 与真人 `photo`（Ken Burns 缓推 + 文字侧压暗，见 §5.6）；
  `DataFilm.tsx` 卡片层与 panel 层共存，另有 `DataFilmNoSub`（无字幕母版）；`Enter` 全片 1.028 慢推。
- 素材：12 张 `-air` 留白底板（sofa/noodle/door/bed/metro/cafe/office/gym/street/wardrobe/mirror/night）；
  11 张旧风格卡通（`slides/u*b`）；6 张实拍（`textures/bs/*`）；`library.json` 36 条清单。
- 工具：`run.py`（plan/voice/align/build/render/mix/check/all）、`check.py`（11 项硬/软分级）、
  `preflight.py`（依赖自检 + `--install`）、`img.py`（三 provider + `--seed`）、
  `stock.py`（bing/commons/openverse/pexels + preview）、`assets.py`（list/check/add）、`build_lib.py`（缺口→批量生成）。
- 成片：EP01 v6 103.1s；EP02 v3 117.5s（卡通 39%）；EP02 panel 版 117.5s（panel 覆盖 43%，自评 60 分）。
  演示：`cardtest-final.mp4`、`slides-final.mp4`、`panel-final.mp4`。
- 剪映：`jy_env.py / jy.cmd / jy_draft.py / jy_from_film.py / jy_check.py / jy_cards.py` 六个入口打通，
  `film.json → 剪映工程` 一次成功（EP02：7 轨 121 段、关键帧/动画/转场/滤镜/淡入全保留、
  `new_version=110.0.0` 可被剪映 11.6 正常打开、黑场 0.00s）；换设备只需 `python tools\jy_env.py --write-env`。
- 质检：`check.py`（成片 11 项）+ `audit.py`（film.json 10 项构图/节奏，FAIL 即拦）。
- 仓库：<https://github.com/aiamkey/bs-video-pipeline>（MIT）。

**下一步（按优先级）**

1. **元素排布**：按 §5.6 三规则重排 EP02 的 25 个元素（禁一列 / label≤1 / 可压人物）——不花 API 时间，收益最大。
   改完必须 `audit.py` 归零 FAIL 才算完。
2. **卡片句合并**：相邻同类型卡片合成一镜，把单镜中位 2.14s 拉到 2.5+，消掉 5 句 <1.5s 的短镜。
3. **音效层**：按 §13（`JIANYING.md`）给元素弹入与换屏挂点。
4. **图标 PNG 化**：10 个 icon/arrow 现在是 emoji，剪映渲成系统彩色表情。
5. **A/B/A 插入**：主屏中途插 0.5–1.0s 反应图（凯哥 283s 的做法），目前完全没有。
6. `teacher` 剪影换 shotcraft `brand-ink-open`；补 `wrong`/`anatomy` 实拍素材。
7. 凯哥剩余 49 条作品待采集（13/62）。

---

## 10. 能力边界：哪些能修，哪些修不了

这一节是为了**别再归因错**。出问题时先在这里对号，别急着换模型或换工具。

| 现象 | 归类 | 说明 |
|---|---|---|
| 元素挤一列、label 过多 | **执行漏洞** | 规则写了没执行，`audit.py` 能抓住 |
| 单镜偏碎、卡片句 <1.5s | **排片问题** | 合并同类型卡片即可 |
| 音效 0 条、图标是 emoji | **没做** | 有规则、有工具，差执行 |
| 话和图对不上 | **顺序问题** | 先攒图后套句子必然错；改成先列场景再出图（§6.2） |
| 卡通只有单姿势、没有对手戏 | **生图能力上限** | `wanx2.1-t2i-turbo + seed` 只能"同一个人换场景"，做不到连续动作/双人对戏。换文案模型不解决，要换 image-edit 通道 |
| 文案不够敢说 | **模型能力** | 换更强的文本模型确实会好，这是真实差距，骨架已量化但"那口气"还在 |
| 没有真人出镜 | **半可解** | panel `photo` 通道能上真人**静态照**（§5.6），解决"处境感"；但真人连续动作/对戏仍做不到——那是拍摄，不是渲染 |
| 剪映里元素不能单独选中 | **工具边界** | 剪映数据结构所限；改字要回 Remotion 重生成（§15 `JIANYING.md`） |
| 剪映导出必须手点 | **工具边界** | 第三方库拿不到官方全保真导出 |

一句话：**结构和工程能到 80 分，剩下 20 分里一半是素材生成能力的天花板、一半是我没执行到位的规则。**

