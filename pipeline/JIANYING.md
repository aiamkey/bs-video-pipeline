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
