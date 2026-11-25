# 剪映衔接（11.x 可编辑草稿）

> 目标：Remotion 负责"确定性画面"，剪映负责人手微调 —— 字幕样式、音效、关键帧推拉、BGM、花字。
> 不是"导出一个 mp4 再拖进去"，而是**直接生成剪映原生工程**（加密草稿，出现在首页列表）。

## 0. 五个命令，一个都不要记路径

全部在 `tools\` 下，换设备只跑第一条：

| 命令 | 干什么 | 什么时候用 |
|---|---|---|
| `python tools\jy_env.py --write-env` | 探测剪映安装目录 / 版本 / 草稿根 / skill 路径 → 写 `tools\jy.env` | **换设备第一步**，之后所有命令靠它 |
| `python tools\jy_env.py --check` | 打印探测结果并校验 `pyJianYingDraft` 是否可用 | 出问题先跑这个 |
| `tools\jy.cmd <子命令>` | 封装 `jyai.cli`（list / inspect / build / patch / repair / render / doctor…） | 看草稿、修草稿、导出 |
| `python tools\jy_draft.py <spec.json>` | spec（JSON）→ 剪映工程（多轨 + 关键帧 + 动画 + 转场 + 滤镜） | 手写时间轴或别的脚本产出 spec |
| `python tools\jy_from_film.py --spec-out qa2\x.json` | `film.json` → spec（底板/元素/字幕/配音全自动分轨） | **主力入口**：Remotion 排完片直接变剪映工程 |
| `python tools\jy_check.py <草稿目录>` | 回读草稿：版本、轨、每段时长/关键帧/引用数、素材统计 | 生成完立刻验 |

`jy.cmd` 读 `tools\jy.env` 里的 `APP_VERSION / DRAFTS_ROOT / SKILL_SCRIPTS / NEW_VERSION`，
导出 `JY_APP_VERSION / JY_DRAFT_NEW_VERSION` 后 `pushd` 到 skill 的 `scripts` 跑 `python -X utf8 -m jyai.cli`。

## 1. 环境事实（本机实测，换机由 `jy_env.py` 重新探测）

| 项 | 值 |
|---|---|
| 剪映安装 | `%LOCALAPPDATA%\JianyingPro` → **junction** → `E:\JianyingPro_Current_8.9` |
| 版本目录 | `Apps\11.6.0.14552\` 与 `Apps\8.9.0.13361\`（两份 `videoeditor.dll` sha1 相同 `F1A6C58F64E4`，72547608 字节） |
| 草稿根 | 权威来源是 `%LOCALAPPDATA%\JianyingPro\User Data\Config\globalSetting` 的 `currentCustomDraftPath` = `E:\剪映5.9版本免激活(1)\草稿\JianyingPro Drafts` |
| 首页登记 | `<草稿根>\..\root_meta_info.json`（`jyai` 自动登记，剪映才能在首页看到） |
| skill 后端 | `~\.dsh\skills\jianying-editor-11-5\skills\jianying-editor-11-5\scripts`（jjjane233 改编版；catalog 里注册的 `jianying-editor` 是 5.9 的 upstream，别用错） |
| 作者库 | `pip install pyJianYingDraft==0.3.1`（`$env:NO_PROXY="*"` 才通） |

两个环境变量的含义：

```
JY_APP_VERSION=11.6.0.14552     # 读哪个版本目录的 videoeditor.dll（加密/解密靠它）
JY_DRAFT_NEW_VERSION=110.0.0    # 草稿 schema 版本，必须 ≤ 剪映自己写的值，否则弹"版本较新"
```

## 2. 两条路线

### 路线 A：干净素材回剪映（零风险）

Remotion 导出无字幕版 + `subtitles.srt` + `voice.wav` + `shots/`，人手在剪映里加音效/花字。

适合：还没想清楚要不要改画面，只想加音效和手改字幕。

### 路线 B：直接生成可编辑工程（本文重点）

```powershell
# 一条命令：film.json → 剪映工程（底板 + 元素 + 字幕 + 配音）
& "E:\miniconda\envs\JupyterProject\python.exe" tools\jy_from_film.py --spec-out qa2\jy-spec-ep02.json

# 想先看 spec 不落盘
& ... tools\jy_from_film.py --dry-run

# 不要元素轨（只留底板 + 字幕）
& ... tools\jy_from_film.py --no-elements
```

输出（EP02 实测）：

```
轨 0 [video]  11 段   ← 底板，每段 scale 1.0→1.035 两个关键帧
轨 1 [text]   11 段   ← 元素1（每个 panel 的第 1 个元素）
轨 2 [text]   10 段   ← 元素2
轨 3 [text]    3 段   ← 元素3
轨 4 [text]   55 段   ← 字幕（白字 + 黑描边 42）
轨 5 [audio]   1 段   ← 配音（淡入 0.15 / 淡出 0.3）
duration=117.38s  new_version=110.0.0  issues=[]
```

## 3. spec 字段表

```jsonc
{
  "name": "EP02_剪映工程",          // 草稿名，首页显示
  "width": 1280, "height": 720, "fps": 30,
  "drafts_root": "E:\\剪映5.9版本免激活(1)\\草稿\\JianyingPro Drafts",
  "replace": true,                   // 同名覆盖；会丢该草稿里的手工改动
  "tracks": [ /* 见下 */ ]
}
```

### 轨道类型

| `type` | 用途 | 必需字段 |
|---|---|---|
| `video` | 底板 / 贴片 / 实拍 | `path`（图片也行，剪映当"照片"）、`start`、`duration`、可选 `source_start` |
| `text` | 字幕 / 大字卡 / 元素 | `text`、`start`、`duration`、`size`、`color`、`bold`、`align`、`border`、`bg`、`shadow` |
| `audio` | 配音 / BGM / 音效 | `path`、`volume`、`speed` |
| `sticker` | 贴纸 | `resource_id`、`start`、`duration` |
| `filter` | 滤镜 | `name`（`FilterType` 成员名，如 `清晰`）、`intensity` |
| `effect` | 特效 | `name`（`EffectType` 成员名）、`params` |

### 通用字段

| 字段 | 含义 | 范围 |
|---|---|---|
| `start` / `duration` | 时间轴起点 / 时长（秒） | — |
| `position` | `[x, y]`，画面中心 0 | −1 ~ 1 |
| `scale` / `alpha` / `rotation` | 缩放 / 不透明度 / 旋转 | 0.05~5 / 0~1 / 度 |
| `keyframes` | 见下 | — |
| `transition` | 转场名（`TransitionType`，如 `叠化`）+ `transition_ms` | 接下一段 |
| `anim_in` / `anim_out` | 入场/出场（视频用 `IntroType`/`OutroType`，文字用 `TextIntro`/`TextOutro`） | — |
| `loop_anim` | 循环动画（`GroupAnimationType` / `TextLoopAnim`） | — |
| `fade` | 音频淡入淡出 `{in, out}`（秒） | — |
| `mask` / `filter` / `mix_mode` / `background_fill` | 蒙版 / 片段滤镜 / 混合模式 / 背景填充 | — |

### 关键帧

```jsonc
"keyframes": [
  { "prop": "scale",      "t": 0.0, "v": 1.00 },   // t 是时间轴绝对秒
  { "prop": "scale",      "t": 6.0, "v": 1.10 },
  { "prop": "position_x", "t": 2.0, "v": 0.95 },   // 从右滑入
  { "prop": "position_x", "t": 2.6, "v": 0.52 },
  { "prop": "alpha",      "t": 2.0, "v": 0.0 },    // 淡入
  { "prop": "alpha",      "t": 2.4, "v": 1.0 }
]
```

`prop` 可用：`scale` `scale_x` `scale_y` `position_x` `position_y` `rotation` `alpha` `volume`。
曲线默认线性；要缓动得改底层 JSON 的 `curveType`。

### 文字

```jsonc
{
  "text": "周六下午，我带你去个地方",
  "start": 2.8, "duration": 3.0,
  "size": 9,                        // 剪映字号；1280×720 下 8~10 约等于字幕
  "color": "#FFE07A", "bold": true, "align": 1,
  "position": [0, -0.36],           // 底部字幕
  "border": { "color": "#000000", "width": 42, "alpha": 1.0 },
  "bg":     { "color": "#C8342B", "alpha": 1.0, "style": 1, "round_radius": 0.06 },
  "shadow": { "color": "#000000", "alpha": 0.7, "diffuse": 15, "distance": 5, "angle": -45 }
}
```

### 像素 → 剪映字号

`size ≈ 像素 / 4.2`（1280×720 实测标定）。`jy_from_film.py` 里是 `PX_TO_SIZE = 4.2`，
字幕固定 `SUB_SIZE = 9`、`SUB_Y = -0.36`（`position` 是相对画面中心的 −1~1）。

### 枚举名怎么查

```powershell
& ... tools\jy_draft.py --list-enums transition    # 451 个
& ... tools\jy_draft.py --list-enums filter        # 1042 个
# 可选：transition intro outro group text_intro text_outro loop filter mask mix effect
```

中文成员名直接写（`"叠化"`、`"清晰"`、`"动感放大"`），内部 `getattr(枚举类, 名字)`。

## 4. 三件必须记住的实现事实

1. **`tim()` 的单位是微秒，不是秒。**
   `pyJianYingDraft.tim(x)` 对 float 做 `int(round(x))` —— 传 `0.35`（意为 0.35 秒）会变成 **0 微秒**，
   动画/转场直接不可见。`jy_draft.py` 统一走 `us(秒) = int(round(秒*1e6))`，或直接传 `"0.35s"`。

2. **装饰必须写在 `add_segment()` 之前。**
   素材收集发生在 `ScriptFile.add_segment()` 内部（`_script_file_segments.py`：动画、淡化、滤镜、
   混合模式、蒙版、转场都在这一步 append 到 `materials`）。先加段再挂动画 → 只留悬空引用，
   `finalize()` 一剥，动画全丢。

3. **剪映同一轨道不允许片段重叠。**
   `SegmentOverlap: New segment overlaps with existing segment`。元素要"停留到屏尾"就必然重叠，
   所以 `jy_from_film.py` **按 panel 内序号分轨**（第 1 个元素 → 元素1，第 2 个 → 元素2…），
   不同屏时间不重叠，同一条轨可以跨屏复用。

## 5. film.json → 剪映 的映射规则（`jy_from_film.py`）

| film.json | 剪映 |
|---|---|
| `panels[].bg` | 视频轨一段（`start`/`end` / 时长），`scale 1.0→1.035` 两关键帧，屏间硬切 |
| `panels[].elements[]` | 文字轨，按 panel 内序号分「元素1…N」，`alpha 0→1`（0.27s 淡入） |
| `element.kind=label` | 白字 + 红底块（`bg`） |
| `element.kind=bubble` | 黑字 + 白底块 + 黑描边 6 |
| `element.kind=num` | 大红字 |
| `element.kind=icon` | emoji 映射：✕ ✓ 📱 🏠 👨‍👩‍👦 ⏰ 💰 ↑ ↓ → |
| `element.kind=dot` | 小号黑字 |
| `lines[]`（非 panel 句） | 字幕轨，白字粗体 + 黑描边 42，`y=-0.36` |
| `voice` | 音频轨，淡入 0.15 / 淡出 0.3 |

元素尺寸同样 `像素/4.2`；`x/y` 百分比 → `pct(v) = (v-50)/50`。

## 6. 生成后怎么在剪映里精修

| 档 | 能改什么 | 对应时间轴 |
|---|---|---|
| 免费 | 字幕文字/字体/颜色/描边/气泡/花字、BGM、音效、片段顺序、裁切、音量 | 文字轨、音频轨 |
| 免费 | 每段的缩放/位移/旋转/透明度**关键帧**（拖曲线、改缓动） | 任意片段 |
| 受限 | 画面内部元素（panel 里的卡通人物、道具）不能单独选中——它是渲染好的一张图 | 视频轨 |

设计原则：**能预见的画面变化都交给 Remotion；留给剪映的必须是"按片段/按文字"就能改的东西。**

## 7. 已知坑（都踩过）

| 现象 | 原因 | 解法 |
|---|---|---|
| 打开弹「草稿版本较新，是否升级」 | `new_version` 写成 11.5 的 `187.0.0`，比 11.6 自己写的 `110.0.0` 高 | `tools\jy.env` 里 `NEW_VERSION=110.0.0`；换设备就看现有草稿的 `draft_content.json` |
| `FileNotFoundError ... 11.5.0.14471` | skill 里硬编码 11.5 的 DLL 目录 | 跑 `jy_env.py --write-env`，`jy.cmd` 自动带 `JY_APP_VERSION` |
| `片段引用不存在的素材` | pyJianYingDraft 基类给每个段塞了 `speed` 引用，但 `add_segment` 只给 video/audio 登记 speed | `jy_draft._make_segment` 文字段里直接摘掉 speed id；`finalize()` 再兜底清 |
| `SegmentOverlap` | 同轨片段重叠 | 元素按 panel 内序号分轨；或缩短前一段 |
| 动画/转场看不见 | `tim()` 把秒当微秒 | 用 `us()` 或 `"0.35s"` |
| 动画挂上了但打开没有 | 装饰写在 `add_segment` 之后 | 先装饰再加段 |
| `Unexpected UTF-8 BOM` | PowerShell `Set-Content -Encoding UTF8` 带 BOM | spec 存 UTF-8 无 BOM，读时用 `utf-8-sig` |
| `'JianYing' 不是内部或外部命令` | `.cmd` 用 LF 换行 + 中文注释 | CRLF + 纯 ASCII 注释 |
| 手工改过的草稿被覆盖 | `replace: true` | 精修阶段换新名字重跑 |

## 8. 已验证 / 未验证

已验证：视频/文字/音频轨、图片当照片、分段裁剪、缩放·位移·旋转·透明度关键帧、
入场/出场/循环动画、转场、滤镜、音频淡入淡出、蒙版、背景填充、加密草稿 + 首页登记 + 回读校验。

未验证：贴纸（`StickerSegment` 需要 `resource_id`，本地贴纸库怎么取还没摸）、
特效参数的取值域、`jyai render` 原生导出（skill 自称"不提供全保真导出"）。

要用哪一条，先做单点验证再批量。

## 9. 什么时候不该用剪映

- 要批量出 20 条、参数完全一致 → Remotion 更快更稳
- 画面里元素要跟着语音变化 → 剪映做不了，得回 Remotion
- 只要字幕不同步修一下 → 改 `align` 重跑，比在剪映里拖快

## 10. 自问自答：这版工程为什么"像，但有瑕疵"

不是凭感觉，每一条都有实测数字。**问 → 证据 → 根因 → 状态**。

| # | 问 | 实测证据 | 根因 | 状态 |
|---|---|---|---|---|
| 1 | 117 秒里有多少秒**有画面**？ | EP02：panel 只占 **51.0s（44%）**，其余 **66.3s 全是黑场**（12 段，最长 17.4s） | `jy_from_film` 只映射 `panels[].bg`；非 panel 的 30 条卡片句（copy/section/board/stat/slides/outro）**没有任何视频段** | ✅ 已修：卡片静帧垫底 |
| 2 | 元素在正确的**高度**吗？ | `元素1` y=26% 被写成 `transform_y=-0.48`（画面下方） | 剪映 **y 轴向上为正**（证据：`pyJianYingDraft.import_srt` 默认 `ClipSettings(transform_y=-0.8)` 就是"字幕在底部"）。原 `pct(v)=(v-50)/50` 把 top% 直接当 y，**整体垂直镜像** | ✅ 已修：`pct_y(v)=(50-v)/50` |
| 3 | 一句话会不会**横贯全屏**？ | 气泡"周六下午，我带你去个地方"铺满整行 | 剪映没有"定宽文本框"，只有 `max_line_width`（占屏宽比例），默认 **0.82** | ✅ 已修：按 `el.w/1280` 折算，缺省 0.24 |
| 4 | 换屏/换卡时**黑闪**吗？ | 句子间静音 0.15–0.5s 被照搬 → 41 处黑缝 9.4s | 逐段照抄 `line.start/end`，没补缝 | ✅ 已修：`_fill_across()` 跨轨延长前一段 |
| 5 | 元素弹入**有声音**吗？ | 音频轨只有 1 条配音，音效 **0 条** | 从没建音效层 | ⬜ 待修（§13） |
| 6 | 图标是凯哥那种**矢量图形**吗？ | ✕ ✓ 📱 是 emoji，剪映渲成系统彩色表情，字重/风格随系统变 | 用文字承载图形 | ⬜ 待修（落 PNG） |
| 7 | 改一句话字幕要动多少？ | 字幕轨 55 段独立片段 | 有意为之：分句边界是资产（改一句不牵动邻居）。改**统一样式**要框选整轨 | ✅ 说明（§14 第 5 步） |
| 8 | 五步循环的 **teacher/board/wrong** 进得去吗？ | board×2、wrong×2 只以静帧进，能看不能改字 | 卡片是 Remotion 渲的图 | ⬜ 半修（§15 边界表） |
| 9 | 凭什么说"像凯哥"？ | 之前**没有验收标准**，全靠肉眼看 | 缺可执行清单 | ✅ 补 §14 |

## 11. 已修的三处，代码在哪

| 修的是什么 | 文件 | 关键改动 |
|---|---|---|
| 黑场 → 卡片静帧铺满 | `tools/jy_cards.py`（新）＋`jy_from_film.py` 的「卡片」轨 | 渲 `DataFilmNoSub` → 按句中点抽 PNG → `public/cards/l{序号}.png` → 视频轨每句一段，`scale 1.0→1.02` |
| 垂直镜像 | `jy_from_film.py: pct_y()` | `round((50 - v) / 50, 3)` |
| 元素换行失控 | `jy_from_film.py` 元素项 | `auto_wrapping: true` + `max_line_width = clamp(el.w/1280, 0.16, 0.46)`，缺省 0.24 |
| 句子间黑缝 | `jy_from_film.py: _fill_across()` | 底板+卡片两轨合并排序，前一段延长到下一段起点（≤1.0s 才补） |
| 黑场不再靠肉眼 | `tools/jy_check.py` | 新增「画面覆盖」段：视频层并集、逐处列出黑场与总占比 |

重新生成（一条链）：

```powershell
# 1) 抽卡片静帧（首次要 --render 出无字幕成片）
& $py tools\jy_cards.py --render
# 2) 出 spec + 建草稿
& $py tools\jy_from_film.py --name "EP02_剪映工程" --spec-out qa2\jy-spec-ep02.json
# 3) 验收：必须看到 "✓ 无黑场"
& $py tools\jy_check.py "<草稿目录>"
```

实测结果：41 段视频（11 底板 + 30 卡片）、黑场 **0.00s / 117.4s**、`issues=[]`。

## 12. 还没修的四件事，按收益排序

| 优先 | 缺口 | 为什么值得修 | 成本 |
|---|---|---|---|
| 1 | **音效层** | 凯哥的"贵"一半来自声音打点：元素一弹、屏一切，都有极短的点。没有音效，画面再对也像 PPT | 低：加一条 audio 轨，素材从剪映音效库挑 |
| 2 | 图标 PNG 化 | emoji 在不同系统/剪映版本变样，且无法统一描边 | 中：Remotion 渲 10 个 icon 透明 PNG，替换 emoji |
| 3 | 卡片文字化 | board/wrong/stat 现在只能看不能改字 | 高：等于把卡片布局搬进剪映，两套版式必然漂移 |
| 4 | 实拍素材层 | 凯哥的可信度来自实拍对比图/截图/解剖图，我们全是 AI 卡通 | 高：要采素材 + 做前后对比版式 |

结论：**先做 1，2 跟着做，3 不做（认了静帧），4 单独立项。**

## 13. 音效怎么加（spec 写法 + 参数）

规则（对齐凯哥的"点"，不是铺 BGM）：

| 时刻 | 音效 | 音量 | 时长 |
|---|---|---|---|
| 元素弹入 | 短促"啪 / 叮"（click、pop、whoosh-short） | −18 ~ −14 dB | 60–120ms |
| 换屏 / 换卡 | 轻 whoosh | −20 dB | 200–300ms |
| 数字出现（num） | 单音"叮" | −16 dB | 150ms |
| 结论句 / 收尾 | 低频 hit（很轻） | −22 dB | 400ms |
| 全片铺底 BGM | **不加**（凯哥原片实测无 BGM） | — | — |

spec 里就是多一条 audio 轨，每个音效一个段：

```jsonc
{ "type": "audio", "name": "音效", "items": [
  { "path": "…/pop.wav", "start": 3.66, "duration": 0.12, "volume": 0.45 }
]}
```

`jy_from_film.py` 里加：遍历 `panels[].elements[].at` → 每条元素一个音效段，
`panels[].start` → 每个换屏一个 whoosh。**先只做这两类**，别一次全上。

## 14. 验收清单（2 分钟跑完，别靠"看着还行"）

1. `python tools\jy_check.py <草稿>` → 必须出现 **✓ 无黑场**，`issues=[]`
2. 抽 8 帧看位置：`ffmpeg -ss T -i 成片 -frames:v 1 x.png`，重点看**元素在不在它该在的象限**（元素全在右下 = y 符号又反了）
3. 时间轴三条轨数对得上：底板 **11** / 卡片 **30** / 元素 **24**（11+10+3）/ 字幕 **55** / 音频 **1**
4. 播到 **40s**（换屏点）听/看有没有黑闪
5. 字幕轨框选全选 → 改一次样式 → 确认 55 段一起变（改不了说明不是同一轨）

## 15. 五步循环在剪映里的可编辑边界

凯哥的结构是 `讲师提问 → 黑板编号 → 学员演错 → 解剖图讲原理 → 手把手`。落到剪映：

| 环节 | 在我们工程里的形态 | 剪映能改 | 必须回 Remotion |
|---|---|---|---|
| 讲师提问 | `teacher` 卡（静帧） | 位置、时长、缩放 | 换文案、换剪影 |
| 黑板编号 | `board` 卡（静帧） | 同上 | 改编号内容、改逐条入场 |
| 学员演错 | panel 底板 + 元素文字轨 | **元素文字、位置、入场** | 换底图、换人物动作 |
| 解剖/标注 | `annotate` 卡（静帧） | 位置、时长 | 改标注点、改线稿 |
| 手把手 | panel + 元素 | 同"学员演错" | 同上 |

一句话：**panel 段是"可编辑的"，卡片段是"可摆放的"。** 想让卡片也可编辑，就得把版式搬进剪映——那等于维护两套设计，不做。

## 16 字幕去重：哪些句子不该有白色字幕

开头最容易翻车：卡片上已经是「兄弟们，先说个扎心的」大字，底部又飘一行一样的白字，
观众第一眼的观感是"打字机卡了"。凯哥没有这个问题，因为他的大字卡本身**就是**字幕。

规则写进 `scripts/build_film.py` 的 `NO_SUB`：卡片大字与语音高度重合的类型 → `lines[].sub = false`。

| 卡型 | 字幕 | 理由 |
|---|---|---|
| `copy` `hook` | 不出 | 卡片大字就是这句话（"兄弟们，！先说个扎心的"） |
| `section` | 不出 | 只显示 `01 太客气`，语音是"第一个，你太客气了"，重复度高 |
| `wrong` | 不出 | 卡片文案与语音几乎一字不差 |
| `list` | 不出 | 条目与语音同序同词 |
| `outro` `stat` | 不出 | 大字/大数字已承载信息，再叠一行变三层文字 |
| `slides` | **出** | 卡片只有图，没字幕整屏无字 |
| `board` `no-list` | **出** | 条目是提炼词，语音是完整句子，不重复 |
| panel 句 | **出** | 屏内只有底板+元素，文字全靠字幕 |
| `image` `cmd` `quote` `brow` `posture` `color` `teacher` `annotate` | **出** | 卡片文字与语音不同 |

EP02 实测：55 句里 **21 句不出字幕**（copy 12 / section 3 / wrong 2 / stat 2 / list 1 / outro 1），
剪映字幕轨 55 段 → **34 段**；黑场仍为 0.00s。

改完要跑的三步（`film.json` 变了，卡片静帧不用重抽）：

```powershell
& $py lbr-promo\scripts\build_film.py lbr-promo\scripts\script-ep02.json ep02
& $py tools\jy_from_film.py --name "EP02_剪映工程" --spec-out qa2\jy-spec-ep02.json
& $py tools\jy_draft.py qa2\jy-spec-ep02.json
```

判断某个卡型该不该出字幕，只有一个标准：**把卡片上的字读一遍，和语音是不是同一句话**。
同一句话 → 删字幕；不同 → 留。

## 17 画面语义对齐：先问"这句话需要什么画面"

第一版 EP02 的 11 块底板是**先有 12 张图、再往上套句子**，于是出现"讲周末在家躺着、画面却在面馆吃面"
这种错位。凯哥的做法反过来：**这句话需要什么画面，就去生成什么**。

对齐判据只有一句：**把底板遮住，只听语音，你能猜出画面里的人在干什么吗？** 猜不出 = 错位。

EP02 重排后的映射（每张底板全片只用一次，语义一对一）：

| 屏 | 时间 | 底板 | 这句话 | 为什么是这张 |
|---|---|---|---|---|
| p1 | 3.7–8.8 | `mirror-air` | 我见过太多这样的兄弟，一米八，工作稳定，就是单着 | 正面全身站姿＝"条件摊开给你看" |
| p2 | 20.6–25.8 | `sofa-air` | 在女生眼里，这叫没有生活 | 窝沙发刷手机＝没有生活 |
| p3 | 28.3–32.6 | `metro-air` | 你随叫随到，她凭什么珍惜 | 抓吊环赶过去＝随叫随到 |
| p4 | 37.6–42.6 | `bed-air` | 问你周末干嘛，你说在家躺着 | 靠床头＝在家躺着 |
| p5 | 42.9–48.6 | `office-air` | 你的一天里，没有一件值得讲的事 | 只有一台笔记本 |
| p6 | 50.3–55.4 | `noodle-air` | 哪怕只是城郊一家面馆 | 面馆 |
| p7 | 60.0–64.8 | `night-air` | 聊了两周，还在问在干嘛 | 夜里对着屏幕瞎聊 |
| p8 | 69.0–73.8 | `street-air` | 你怕被拒绝，所以一直不给答案 | 低头走路＝犹豫 |
| p9 | 81.0–85.1 | `gym-air` | 不是冷落，是你真的在忙 | 在练＝真的忙 |
| p10 | 102.5–106.9 | `wardrobe-air` | 你把自己放在没人看得见的位置 | 衣柜角落＝被塞起来 |
| p11 | 108.9–111.5 | `door-air` | 你只要把那三个东西拿掉 | 站在门口＝要走出去 |

`cafe-air` 因此空出来 —— 它右侧那把藤椅会在画面里变成一块突兀的棕色方块，本来就该淘汰。

改完要重跑的四步（底板变了，卡片静帧不用重抽）：

```powershell
& $py lbr-promo\scripts\build_film.py lbr-promo\scripts\script-ep02.json ep02
# 渲染 DataFilm（带字幕）→ out/ep02-bg.mp4
& $py tools\jy_from_film.py --name "EP02_剪映工程" --spec-out qa2\jy-spec-ep02.json
& $py tools\jy_check.py "E:\剪映5.9版本免激活(1)\草稿\JianyingPro Drafts\EP02_剪映工程"
```

新写稿时，**先列 11–14 个"这句话在什么场景"**，再按场景去生图，别反过来。