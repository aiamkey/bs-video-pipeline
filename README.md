# 男生变帅 · 口播短视频流水线

一套可复现的「**文稿 → 配音 → 逐句卡点 → 渲染 → 质检**」流水线，用来生产 90–120 秒的横屏知识口播片（1280×720，底部分段进度条，逐句字幕）。

对标抖音「凯哥恋爱说」的形态，但**方法论、参数、素材规格全部显式化**，不靠手感。

也能反向用：给一条别人做好的**动画式参考片**，自动拆出结构、对齐时长、出可编辑剪映工程 —— 见「[复刻一条参考片](#复刻一条参考片反向用法)」。

---

## 30 秒上手

```bash
# 0 环境自检：路径 / ffmpeg / python 全部自动发现，哪项缺会指出来
python pipeline/env.py

# 1 体检（缺什么会直接告诉你装什么）
python pipeline/preflight.py

# 2 缺依赖就一键装
python pipeline/preflight.py --install

# 3 复制一份自己的配置（config.json 不进 git）
cp pipeline/config.example.json pipeline/config.json

# 4 看素材缺哪些（成图不进 git，这一步会列出缺口与生成命令）
python tools/check_assets.py

# 5 跑一条
python pipeline/run.py all ep02 scripts/script-ep02.json
```

产物在 `remotion/out/ep02-final.mp4`。

> 换自己的片子：复制 `scripts/script-ep02.json` 改文案与卡片，改 `pipeline/config.json` 里的参数，重跑。

### 环境变量（都不设也能跑，会自动探测）

| 变量 | 作用 | 不设时 |
|---|---|---|
| `LBR_ROOT` | 工程根（含 `pipeline/ tools/ scripts/`） | 脚本所在位置推出来 |
| `LBR_PROMO` | 视频工程（含 `remotion/ public/`） | `config.json` 的 `paths.promo` → 自动探测 |
| `FFMPEG` | ffmpeg 可执行文件 | `config.json` → PATH → `imageio-ffmpeg` 自带那份 |
| `PYTHON` | 指定解释器 | `config.json` → 当前解释器 |
| `DASHSCOPE_API_KEY` | 配音 / 生图 | `config.json` 的 `keys` → `~/.dsh/skills/tts-service/config.local.json` |
| `VIDEO_SHOTCRAFT` | 卡库（找灵感，可选） | 自动找同级 `video-shotcraft` |

**没有一处写死机器路径**：所有工具都 `import pipeline/env.py`，换设备、换盘符只改环境变量或 `config.json`。

> 换自己的片子：复制 `scripts/script-ep02.json` 改文案与卡片，改 `pipeline/config.example.json` 里的参数，重跑。

---

## 复刻一条参考片（反向用法）

手上有一条别人做的动画式视频（图文卡 / 聊天气泡 / 大字卡 / 文档页 / 卡通角色 / 进度导航），
要照它的结构做一条同构的。**换片只换第一个参数，不改代码**：

```bash
python tools/replica.py auto "D:\ref\任意新片.mp4" --name 新片_自动复刻
# 只拆结构不要草稿： 加 --no-jianying；只分析前 3 分钟：加 --dur 180
```

| 产物 | 位置 | 说明 |
|---|---|---|
| `spec.json` | `qa2/replica/out/<片名>.spec.json` | 结构事实：`meta` / `subs` / `scenes` / `sections` / `voice` |
| `assets/` | 同上目录 | 每屏代表帧 `p000.jpg…` + `voice.wav`（原片音轨） |
| 剪映草稿 | `…\JianyingPro Drafts\<name>\` | **图片轨 + 字幕轨 + 配音轨**，打开即可改 / 导出 |

实测：547s 片 → 313 字幕 / 61 屏 / 6 章；180s 片 → 126 字幕 / 38 屏 / 3 章，`validate` 全 PASS（时长差 0.02–0.18s）。

事实层（转写 / 切点 / 版式量测）全在本机跑，**不联网不花钱**。两条增强已接线，都是按张 / 按次花钱的：

**换画面**——把原片截图换成自己生成的插画，画面语义按该屏字幕生成：

```bash
python tools\replica_redraw.py --spec "qa2/replica/out/<片名>.spec.json" --only 0,2,7 --apply  # 先小样看风格
python tools\replica_redraw.py --spec "qa2/replica/out/<片名>.spec.json" --apply              # 满意后全量
```

**换声音**——克隆音色 → 逐句合成 → 按原片时间轴铺回整条：

```bash
python tools\replica_voice.py extract-ref "qa2\replica\segs-<片名>.json" "qa2\replica\ref.wav" --src "<原片>"
python tools\replica_voice.py create "qa2\replica\ref.wav" --yes   # 建音色，计费且不会自动删
python tools\replica_voice.py wait
python tools\replica_voice.py speak "qa2\replica\out\<片名>.spec.json" "qa2\replica\voice-out" --yes
python tools\replica_assemble.py --spec "qa2\replica\out\<片名>.spec.json" --voice-dir "qa2\replica\voice-out"
```

两者都只改 `scenes[].assets[].file` 与 `voice.wav`，**下游一个字不用改**；重跑 `replica.py jianying` 就是新版本。

两个硬约束（不满足会直接跑不起来）：声音克隆要**带 `Client` 的 dashscope 2.x**（conda 环境里那把 1.26.4 没有），
以及**先把 proxy 环境变量清干净**（系统 `no_proxy` 里的 `[::1]` 会让 httpx 抛 `Invalid port`）。
另外这个克隆音色**忽略 `speech_rate`**，语速只能靠装配端 `atempo` 保音高压缩（默认 `--max-tempo 1.6`）。
细节见 [`SKILL.md` §8.6.1 / §8.6.2](SKILL.md)。

分步用法、四型判定规则、解释器对照与 6 条坑见 [`SKILL.md` §8.6](SKILL.md)；输入口径与 80% 验收见 [`pipeline/REPLICA.md`](pipeline/REPLICA.md)。

> `qa2/`、`deliver/` 都是产物目录，不进 git（跑一次就重建）。

---

## 依赖（像 pip 一样，缺了 preflight 会说）

| 类别 | 需要 | 说明 |
|---|---|---|
| Python | 3.10+ | `requests` / `numpy` / `dashscope` |
| Node | 18 / 20 / 22 | Remotion 4.0.x 的要求 |
| ffmpeg | 6+ | 混音、抽帧、测静止段 |
| Remotion | 4.0.484 | `remotion/package.json` 已锁版本，`npm ci` 装 |
| API key | 阿里云百炼 | 配音 `cosyvoice-v2`、生图 `wanx2.1-t2i-turbo` |

`python pipeline/preflight.py` 会逐项检查并给出安装命令；`--install` 直接执行 `npm ci` 和 `pip install -r requirements.txt`。

---

## 目录

```
pipeline/
  config.example.json   所有可调参数（复制成 config.json 再改；config.json 不进 git）
  env.py                统一环境发现：路径 / ffmpeg / python / 剪映 / tts 配置（换机器只改这层）
  run.py                一条命令跑完：voice → align → build → render → mix → check
  audit.py              渲染前排布体检（元素位置 / label 占比 / 时长 / 音效密度）
  check.py              11 项成片质检（响度只看 *-final.mp4）
  sfx.py                film.json → 音效事件（换屏 whoosh / 元素 pop / 数字 sparkle / 结论 impact）
  preflight.py          依赖自检 / 自动安装
  selftest.py           10 项冒烟：不联网不渲染，30 秒回答"这条链还是好的吗"
  README.md             怎么用、改哪个字段
  TOOLS.md              工具索引（我在做什么 → 调哪个）+ 反面清单
  TROUBLES.md           30 条故障对照（按"最先想到的"排序）
  COST.md               一条片多少钱、多少时间；哪些付费能力值得接
  SPEC.md               内容 / 文稿 / 动画 / 素材 / 流程的完整规格
  ANIMATION.md          动画与转场的"看起来该是什么样"
  CARTOON.md            卡通素材的数量、节拍与衔接六法
  JIANYING.md           film.json → 剪映工程（含明文降级、可迁移素材、美颜花字）
  REPLICA.md            复刻需求规格定稿（输入口径 / 保真定义 / 80% 验收 / 交付物）
  jy_versions.json      剪映版本能力表（哪版验证过、new_version 该写多少）
scripts/
  script-*.json         逐句文稿 + 每句的画面卡
  build_film.py         文稿 + 时间轴 → film.json
tools/
  cosy_chapter.py       按章合成配音（cosyvoice-v2）
  align_v2.py           whisper 词级对齐 → timeline.json
  img.py                文生图（多 provider，支持 --seed 锁角色）
  mk_icons.py           11 个图标 PNG（check/cross/house/clock/phone/…）
  check_assets.py       素材体检：稿子引用的图在不在，缺了怎么补
  shot_stats.py         测镜头密度 / 静止占比
  jy_env.py / jy_draft.py / jy_from_film.py / jy_check.py / jy_localize.py / jy_beauty.py
                        film.json → 剪映工程（可选，见 JIANYING.md）
  analyze_ref.py        事实层：探针 / 转写 / 镜头切点 / 逐像素版式量测（复刻链路的地基）
  replica.py            复刻编排器：extract / shots / validate / jianying / auto
  replica_extract.py    参考片 → spec.json（事实层 + 归类层，本地不花钱）
  replica_shots.py      按屏抽代表帧 → assets[]
  replica_voice.py      声音克隆（百炼 voice-enrollment，key 走环境变量）
  jy_from_spec.py       spec.json → 剪映工程（图片轨 + 字幕轨 + 配音轨）
  spec.schema.json      spec 契约（required: meta / subs / scenes）
remotion/
  src/bs/Panel.tsx      一屏多句 + 元素累加（7 种元素）
  src/bs/Cards.tsx      19 种卡片组件
  src/bs/DataFilm.tsx   渲染入口（读 film.json；DataFilmNoSub 不带字幕，用来抽卡片帧）
  src/Root.tsx          composition 注册
```

### 素材为什么不进 git

`remotion/public/textures/slides/`（卡通场景，约 11 MB）与 `lib/`（留白底板，约 8 MB）是 **AI 生成的成图**，
体积大且可按 `pipeline/library.json` 重新生成，所以不随仓库分发。clone 之后：

```bash
python tools/check_assets.py        # 列出缺哪些、按提示补
```

缺图时流水线仍能跑（对应位置是底色块），只是画面不完整——用来先验证节奏是够的。

---

## 常用命令

```bash
python pipeline/run.py plan  ep02 scripts/script-ep02.json   # 只估算时长，不花钱
python pipeline/run.py voice ep02 scripts/script-ep02.json   # 只配音
python pipeline/run.py render ep02                            # 只渲染（改卡片后）
python pipeline/run.py mix   ep02                             # 只混音
python pipeline/check.py ep02                                 # 只质检
```

---

## 参数怎么调

**只改 `pipeline/config.local.json`，不要动脚本。**

| 想要 | 改哪个字段 |
|---|---|
| 说话快慢 | `voice.rate`（1.08 ≈ 5.3 字/秒） |
| 章节间停顿 | `voice.gap_between_chapters` |
| 时长固定 / 随稿 | `video.duration.mode` = `target` / `auto` |
| 字幕位置字号 | `video.subtitle.*` |
| 卡片配色字号 | `card.*` |
| 质检阈值 | `check.*` |

改 `card.*` 或 `video.*` → 只需 `render` + `mix`；改 `voice.*` → 从 `voice` 重跑。

---

## 质检基线（2 分钟片）

| 项 | 目标 |
|---|---|
| 时长 | 90–120s |
| 字数 | 500–700 |
| 语速 | 5.0–5.5 字/秒 |
| 单镜中位 | 2.5–3.0s |
| 最长单镜 | ≤4.0s |
| 最长静止 | ≤3.0s |
| 静止占比 | ≤40% |
| 响度 | −16 LUFS / 真峰值 ≤ −2 dBTP |

---

## 方法论

- [`pipeline/SPEC.md`](pipeline/SPEC.md)：内容方法论 + 文稿规格 + 素材规格 + 8 步流程
- [`pipeline/ANIMATION.md`](pipeline/ANIMATION.md)：六个入场动作、转场规则、五步循环
- [`pipeline/CARTOON.md`](pipeline/CARTOON.md)：卡通素材数量换算与衔接六法
- [`SKILL.md`](SKILL.md)：给 Agent 用的执行手册（含依赖自检与故障对照）

## 说明

- 动画实现依赖 [Remotion](https://www.remotion.dev/)（MIT）。可选的镜头卡库 [video-shotcraft](https://github.com/vincentwei1021/video-shotcraft)（Apache-2.0）只做参考，本仓库未包含其代码。
- 仓库不含任何 API key、模型权重、成片或参考视频。
