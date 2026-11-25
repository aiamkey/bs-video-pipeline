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

## 6. 素材

### 6.1 形态铁律：卡通为主，字幕常驻

凯哥的片子**不是"文字卡 + 偶尔插画"，是"卡通图铺底 + 底部字幕"**。抄形态就抄这一条：

| 项 | 规格 |
|---|---|
| 卡通（含 slides 卡） | **占全片 50–65% 时长**（EP02 实测 39%，偏低） |
| 底部字幕 | 全程常驻，34–40px，距底 90–110px，黑边 5 |
| 画面大字 | **只在需要"钉一句"时用**（每 8–10 句一次），且**不得与字幕重复**（重复=废信息） |
| 其余画面 | 黑板 / 清单 / 红叉 / 对比 / 实拍局部 / 长文卡，合计 35–50% |
| 单镜 | 2.5–3.0s，卡通一张停 1.2–2.0s |

> 判断是否抄对：静音看一遍。如果画面本身在"讲事"（人物在做事），对；如果画面只是把字幕放大，错。

### 6.2 素材从哪来（四层，按顺序走）

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

已知基线：EP01 v6 103.2s / 525 字 / 5.09 字秒；EP02 v3 117.5s / 630 字 / 5.36 字秒 / 静止 10% / 卡通 39%。
单镜中位 1.9–2.5 属正常（一句一镜必然偏短），别为这条改稿。

### 7.5 素材专项验收（人工，3 分钟）

跑完片必须自己过一遍这五条，任一不过就回炉：

1. **盲听**：关掉画面听一遍，讲得通吗？（讲不通=稿子问题，不是素材问题）
2. **盲看**：静音看一遍，画面在"演事"还是在"复读字幕"？（复读=素材没对上）
3. **数卡通**：卡通时长占比是否 ≥ 50%？（用 `shot_stats.py` 或目测）
4. **查复用**：有没有同一张图在一集里出现第 3 次？有没有跨章复用？
5. **抽 6 帧**：随机抽 6 帧拼图，每帧都能说出"这句在讲什么"吗？


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
| 素材配不上句子 | 先按"风格"找图，再套句子 | 反过来：先读句子，列 3 个必须出现的东西，再找图 |
| 一张图贴了半集 | 没登记复用 | 建 `assets.json`，`used_in` ≥2 就排除 |
| 卡通人物不像一个人 | 换 provider / 换 seed / 词太虚 | 固定 `wanx2.1-t2i-turbo` + `--seed 20261124` + 身份串 |
| 检索出来的图全不对 | cn.bing 对分镜描述命中极低 | 只当捡便宜，命中率 <30% 直接转 AI 生成 |

---

## 9. 现状

- EP01：`out\EP01-变帅5件事-v6.mp4`（103.1s）。
- EP02：`out\EP02-你条件不差为什么一直单着.mp4`（117.5s，卡通 39%）。
- 卡型全部跑通：`out\cardtest-final.mp4`、`out\slides-final.mp4`。
- **待办**：① 把卡通占比从 39% 提到 50%+（补 5–6 个场景图）② 建 `pipeline\assets.json` + `tools\assets.py`（登记/查重/统计次数）③ 把 `stock.py` 的 preview 流程纳入出片 SOP ④ `teacher` 剪影换 shotcraft `brand-ink-open` ⑤ 凯哥剩余 49 条作品待采集（13/62）。
