# 故障对照

> 从 SKILL §8 抽出来的独立文件：**症状 → 先查什么 → 修法**。按"最先想到的"排序，不按严重性。
> 每条都实际踩过，不是抄的。

## 一、声音与字幕

### 声音"断触""电平一跳一跳"

- **先看**：是不是逐句合成的？`ffmpeg -i voice.wav -af silencedetect=noise=-40dB:d=0.05 -f null - 2>&1 | findstr silence_end`
- **判据**：静音段占比 > 5% 或 ≥20 段 50ms 以上静音 = 逐句拼接的锅
- **修**：改**按章合成**（`tools\cosy_chapter.py`）+ 轻削静音（`stop_duration=0.30:stop_threshold=-42dB`）
- **参考值**：凯哥原声静音占比 0.1%（2 段）；我们 103s 版 47.6%（169 段）→ 修后正常

### 声音"怪"、有金属感

- **先看**：是不是用了 `atempo` 加速？
- **修**：`atempo` 会产生金属感。改用原生 `speech_rate`（cosyvoice-v2 支持），1.0–1.2 区间自然
- **注意**：`qwen3-tts-flash` 的 `speech_rate` **不生效**（同参数下 Ethan 98.8s / Ryan 120.6s），要变速只能换 provider

### 字幕和语音对不上

- **先看**：timeline 是 `align_v2.py` 生成的还是手写的？老 `align_timeline.py` 按字数比例线性映射，误差很大
- **修**：`tools\align_v2.py`（whisper 词级 + difflib 字符级映射），验收看它打印的"匹配字符数/总字符数"，**525/525、异常 0** 才算过
- **需设**：`HF_ENDPOINT=https://hf-mirror.com`（否则 whisper 模型下载卡住）

### 字幕和卡片大字重复（开头尤其明显）

- **判据**：把卡片上的字读一遍，和语音是不是**同一句话**
- **修**：`build_film.py` 的 `NO_SUB = {hook, copy, section, wrong, list, outro, stat}` 不出字幕；panel 句、`slides`、`board`、`no-list` 保留
- **参考**：EP02 55 句 → 21 句不出字幕 → 剪映字幕轨 55→34 段

## 二、画面

### 打开剪映工程一半是黑的

- **先看**：`jy_check.py` 的「画面覆盖」段落，黑场几处、合计几秒
- **根因**：`jy_from_film` 只映射 `panels[].bg`，非 panel 的卡片句没有视频段
- **修**：`tools\jy_cards.py --render` 抽卡片静帧 + `jy_from_film` 的 `卡片` 轨 + `_fill_across()` 补缝
- **参考**：EP02 修前 12 处 / 66.3s（56%），修后 0.00s

### 元素全跑到下半屏 / 整层垂直镜像

- **根因**：剪映 **y 轴向上为正**，`top:26%` 要写 `transform_y = (50-26)/50 = +0.48`，写成 −0.48 就是镜像
- **铁证**：`pyJianYingDraft.import_srt` 默认 `ClipSettings(transform_y=-0.8)`（字幕贴底）
- **修**：`jy_from_film.pct_y(v) = round((50-v)/50, 3)`

### 一句话横贯全屏

- **根因**：剪映**没有定宽文本框**，只有 `max_line_width`（占屏宽比例，默认 0.82）
- **修**：`max_line_width = clamp(el.w/1280, 0.16, 0.46)`，配合 `auto_wrapping: true`

### 元素全挤在右边一列（像信息栏）

- **先看**：`audit.py` 的"元素跨区"项，FAIL 会点名哪几屏
- **修**：同屏 ≥3 元素时 x 必须跨 ≥2 区（左 20–35 / 中 45–55 / 右 65–80）；`label` ≤1/屏
- **关键**：**每张底板人物位置不同，锚点要按图定**（`metro` 人物正中 → 分两侧；`office` 贴左缘 → 元素去右上；`sofa` 占左三分之二 → 右侧 + 左下角）

### 卡片上的字读不清 / 压在深色图上看不见

- **修**：`SlidesCard` 底部加 300px 渐变遮罩 `rgba(12,10,8,0.72)`→透明，文字纯白 + `textShadow`
- `box` 元素同理：有 `text` 时走深底（`rgba(18,16,13,.86)`）白字 + 左侧红条，不要空心虚线框

### 页面切点闪白 / 一闪而过

- **根因**：spring 入场从 `opacity: 0` 开始，切点瞬间是空白
- **修**：所有卡片 `opacity: 0.15 + s*0.85`（不从 0 起），字幕淡入 7 帧 → 4 帧

### 静态帧太多、看着像 PPT

- **判据**：`check.py` 的静止占比。**注意：静止不是缺点**（凯哥 43%）
- **真要改**：给底板/卡片加 `scale 1 → 1.035` 慢推，静止占比直接掉（slides 演示片 49% → 0%）

## 三、剪映工程

### 剪映弹「软件版本需要升级 / 草稿版本较新」

- **根因**：`draft_content.json` 的 `new_version` 写高了（比如给 11.6 写了 11.5 的 `187.0.0`）
- **修**：用该版本**自己存盘的值**（11.6 = `110.0.0`）。现在由 `pipeline/jy_versions.json` 管，不再硬编码
- **验证**：`jy_env.py --check` 会打印版本是否登记过

### `FileNotFoundError ... Apps\11.5.0.14471`

- **根因**：skill 的 `native_crypto.py` 硬编码 `VERIFIED_VERSION`
- **修**：已改成读 `JY_APP_VERSION`；`tools\jy.cmd` 从 `tools\jy.env` 注入

### `片段引用不存在的素材: <id>` / `static_valid: false`

- 两种来源：① 装饰写在 `add_segment()` 之后（素材没登记）② 文字段被塞了 `speed` 引用但 speeds 没登记
- **修**：装饰提前；`jy_draft._make_segment` 的文字分支已摘掉 speed id；`finalize()` 兜底剥悬空 ref

### `Unexpected UTF-8 BOM`

- **根因**：PowerShell `Set-Content -Encoding UTF8` 写 spec 会带 BOM
- **修**：读用 `encoding="utf-8-sig"`，写用 `utf-8` 且 `newline="\n"`

### `.cmd` 报 `'JianYing' 不是内部或外部命令`

- **根因**：`.cmd` 用 LF 换行 + 中文注释
- **修**：CRLF + 纯 ASCII 注释

### 草稿换机器全黑

- **根因**：素材是绝对路径
- **修**：`jy_localize`（`jy_draft` 默认开），`jy_check` 会显示「草稿内 42 个 / 外部 0 个」

### `SegmentOverlap: New segment overlaps with existing segment`

- **根因**：剪映同轨不能重叠
- **修**：元素按 panel 内序号分轨；字幕与花字分轨

## 四、素材与生图

### `404 http://localhost:3000/public/textures/...`

- **根因**：图不在 `public/` 下，或者放在 `slides/` 而代码引用 `lib/`
- **修**：按 `pipeline/library.json` 的 `file` 名对齐目录；`lib/` 是运行时要用的那套

### 生图人物每张脸都不一样

- **修**：`--seed` 固定 + 提示词里把人物特征写死（脸型/眉眼/发型/服装），一次写 6 条以上
- **上限**：`wanx2.1-t2i-turbo` 只能出"单场景单姿势"，**要对手戏/连续动作必须换 image-edit 通道**

### 底板右侧没有留白，元素压脸

- **修**：提示词加 `人物位于画面左侧三分之一处，画面右侧三分之二是干净的空墙`
- **验收**：右侧 35% 区域空白率 > 85%（EP02 实测 86.7–100%）

## 五、环境

### `KeyError: 'DASHSCOPE_API_KEY'`

- **修**：`run.py` 已内置取值链：环境变量 → `config.keys` → `~/.dsh/skills/tts-service/config.local.json`

### `ProxyError('Unable to connect to proxy')` / 代理相关

- **修**：`$env:NO_PROXY="dashscope.aliyuncs.com"`（requests 会读）
- **但 TUN 模式下无效**：TUN 是网络层劫持。要在 Clash 的 **Rules 增强**文件里加 `DOMAIN-SUFFIX,...,DIRECT`（订阅里改会被覆盖，Merge 的 `prepend-rules` 本机不展开）

### `npx` 找不到（`WinError 2`）

- **修**：`run.py` 已改 `shutil.which("npx")`；还不行就是 Node 不在 PATH

### Python 里写多行中文匹配文件内容 → `AssertionError`

- **改法**：别用 `python -c` 做长字符串替换，改用 `edit` 工具按行匹配
- 同理：PowerShell here-string（`@"..."@`）会吃掉 Python 代码里的引号 → 写临时 `.py` 再执行
