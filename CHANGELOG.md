# 变更记录

只记**会影响怎么做**的改动（新能力、口径变化、踩坑修正）。参数以 `lbr-promo/pipeline/config.json` 为准。

## 2026-11-25（上午）

## 2026-11-25（下午）

### 节奏：合并 5 对碎句 + 支持一句多元素

- EP02 稿子 55 → **50 句**（字数 630 不变），合并的 5 对：p2「你以为这叫真诚 / 没有生活」、p4「有什么爱好 / 这不是错」、p7「她等你约 / 两个人一起耗」、p11「不用变成另一个人 / 只要把那三个东西拿掉」、以及「成不成是她的事 / 给不给是你的事」合一张 copy 卡（两行字）。
- `build_film.py` 新增 `els`：一句可挂多个元素，第二个起自动 +0.35s 弹入。合并句子必然会丢掉后一句的 `el`，用 `els` 挂回去后元素总数仍是 24。
- 结果：卡片句 <1.5s 的短镜 **5 → 3 句**；卡片句单镜中位 2.14 → **2.24s**；panel 最短 2.6 → **2.8s**；成片 **118.1s**、5.33 字/秒、最长单镜 3.92s、静止 26%、LUFS −16.15 / −1.93 dBTP。
- 合并后重新配音 + 对齐 + 渲染 + 混音（`voice` 用 `longcheng_v2`，同一音色，逐章合成）。

### 剪映：图标尺寸算错 2.8 倍

- `jy_from_film.py` 原来按 `scale = 像素 / 720` 算图标，把 84px 的图标压成 30px。剪映的 scale 是相对**素材原始像素**（底板 1280×720 在 scale 1.0 正好铺满画布，可证），所以正确公式是 `scale = 像素 / 图片边长`（图标 PNG 是 256）。现在 84/74/90/230px 与 Remotion 一致。
- 顺带把 `jy_cards.py` 的 `npx` 改成 `shutil.which('npx') or 'npx.cmd'`——Windows 上直接写 `npx` 会 `FileNotFoundError: [WinError 2]`。

### 体检脚本两处修

- `tools/check_assets.py` 现在也检查**图标 PNG**（`el.kind=icon/arrow/dot` → `textures/icons/<name>.png`），缺图时先提示 `python tools/mk_icons.py`。工作树 32/32 就位，仓库 0/31（图与图标都不进 git）。
- `pipeline/audit.py`「音效条数」原来把 level 写死成 `WARN`，即使达标也显示 `·`；现在按判定给 `OK/WARN`。


### 可迁移性：把"作者机器"从代码里彻底拿掉

- 新增 `pipeline/env.py`：**所有路径的唯一解析层**，优先级「环境变量 → `config.json` 的 `paths.*` → 自动探测 → 报错给修法」。
  导出 `root/promo/scripts/tools/public/data/ffmpeg/python/shotcraft/tts_config` + `summary()`；`python pipeline/env.py` 打印 9 项 ✓/✗ 与修法。
- 六个硬编码作者路径全部改掉：`tools/align_v2.py`（`ROOT`/`FFMPEG`）、`tools/cosy_chapter.py`（`ROOT`/`TMP`/`FFMPEG`）、
  `tools/shot_stats.py`（`FF`）、`tools/stock.py`（`FFMPEG`）、`pipeline/preflight.py`（shotcraft 卡库）、`pipeline/run.py`（tts 配置）——
  统一改成 `import env`，且在仓库布局（`dsh-bs-video/`）与工作树布局（`video/`）下都能定位。
- `tools/jy_env.py` 的版本表定位改为向上查找 `pipeline/jy_versions.json`，不再假定固定层级。
- 新增 `tools/check_assets.py`：稿子引用的图在不在（`card.img`/`card.frames[]`/`panel.bg`+`library.json`/`assets.json`），
  缺图按目录分组打印三种补法；`--soft` 只提示不失败（给 selftest 用）。
- `pipeline/config.example.json` 与工作树对齐：`video.duration` = `target_sec 150 / tolerance 20% / preferred_sec [120,180] / auto_bounds [30,1200]`，
  `text.auto_bounds [60,4000]`，`paths` 增 `shotcraft`/`tts_config`，新增 `version: 2`。

### 剪映桥降级：没有 `jyai` 也能出草稿

- `tools/jy_draft.py`：`load_env()` 不再因缺 `jyai` 退出（返回 `have_bridge`）；`finalize(plain=)` 自动回落明文模式
  （写 `material_save_mode=1`、同步 `Timelines/`、修 `draft_meta_info.json` 的草稿路径）；`--plain` 可强制。
- 启动行改成一眼可辨的形态：`桥接 jyai（加密+登记）｜无（明文草稿）`。

### 声音层：音效 + 图标真正落地

- 新增 `pipeline/sfx.py`：`film.json` → `src/data/sfx.json`。换屏 `whoosh-fast -20dB`、元素 `pop -18dB`、
  数字 `sparkle -16dB`、结论 `impact-cine -22dB`、章节 `transition-snap -19dB`；`DEBOUNCE 0.20s` 去重取更响；
  **全片不铺 BGM**（凯哥原片实测无 BGM）。EP02 实测 28 条 / 2.5 条每屏 / 14.3 条每分钟。
- `tools/mk_icons.py`：11 个图标 PNG（check/cross/house/family/clock/phone/money/up/down/arrow/dot），
  统一 256px、16px 描边、墨绿/红/近黑三色，与 `Panel.tsx` 的 SVG 同形状。
- `tools/jy_from_film.py`：`kind=icon/arrow/dot` 的元素改走**图标 PNG 轨**（video 轨 + alpha/scale 关键帧，`scale = 像素/720`），
  不再用 emoji 文字；新增**音效轨**（同轨去重叠：压到就裁尾、间隔 <0.04s 后推）。
  EP02 现在是 **9 轨 127 段**，`jy_check` 报 `videos 47 / audios 29 / 无黑场 / 素材本地化 76 个内嵌 0 个外链`。
- `pipeline/audit.py`：「音效条数」判据改为读 `src/data/sfx.json`（每屏 ≥1 条且密度 ≤20 条/分钟），
  并新增「不铺 BGM 只有点状音效」一项；icon 判据文案改为「走 PNG 轨，不是 emoji」。

### 冒烟自检布局无关

- `pipeline/selftest.py` 改用 `env` 的路径，10 项：`envresolve / config / assets / film / audit / spec / env / audio / draft`；
  仓库空布局实测 `3 通过 / 0 失败 / 6 跳过`（跳过项都是生成物未产生），工作树实测 `10 通过 / 0 失败`。


### 结构：把"一个巨大 SKILL"拆成能查的东西

- 新增 `pipeline/TOOLS.md`：工具索引（我在做什么 → 调哪个）+ 每个工具的命令/产物/坑 + **负面清单 13 条**（每条都踩过）
- 新增 `pipeline/TROUBLES.md`：故障对照，按"最先想到的"排序，五类 30 条
- 新增 `pipeline/COST.md`：一条 2 分钟片 ≈ **1.8 元 / 1.5–2 小时**；可选付费能力逐项判断（声音复刻暂不接、云端 ASR 值得、文生视频太贵）
- `SKILL.md` 从 685 行瘦身，故障表与工具表改成指向上面三份

### 新增 `pipeline/selftest.py`：30 秒冒烟自检

```powershell
& $py lbr-promo\pipeline\selftest.py
# 8 项：config / film.json / audit / spec 生成 / spec 契约 / 剪映版本表 / 配音 / 最近草稿
```

不联网、不渲染、不花钱。改完任何代码先跑这个。

### 新增 `pipeline/jy_versions.json`：剪映版本能力表

原来 `new_version=110.0.0`、占位符 UUID、`VERIFIED_VERSION` 散在四处硬编码。现在集中成一张表：

| 版本 | new_version | 状态 | 已验证 |
|---|---|---|---|
| `11.6.0.14552` | `110.0.0` | verified | 9 项（含本地化、美颜、花字、关键帧） |
| `8.9.0.13361` | `110.0.0` | installed-not-tested | — |

`jy_env.py --check` 会核对实际版本是否登记；未登记就用 `unknown_version_policy` 的默认值并提示"生成 3 秒草稿打开确认后补表"。`jy_draft.load_env()` 把 `JY_PLACEHOLDER` 也导出，`jy_localize` 不再写死 UUID。

### 新增 `jy_draft.py --validate`：spec 契约校验

```powershell
& $py tools\jy_draft.py qa2\jy-spec-ep02.json --validate
# spec 校验通过：7 条轨 / 99 个片段
```

校验：必填字段、track type 合法、items 非空、duration>0、text 段有 text、非文字段有 path、keyframe prop 合法、`text_effect` 只能用在文字段、`beauty` 是对象。**校验不过直接报错退出，不会写半成品草稿。**

### 草稿可迁移（素材本地化，默认开）

`jy_draft.build()` 在 `save()` 后自动跑 `jy_localize`：素材复制进 `<草稿>/assets/`，路径改 `##_draftpath_placeholder_<UUID>_##/assets/xxx`，`material_save_mode=1`。

- EP02 实测：42 个素材 / 13.26 MB / 外部绝对路径 **0** / `issues=[]`
- 配套修 `jyai/repair.py` 的 `validate()`：加 `resolve_material_path()` 解析占位符，否则必然误报「素材丢失」
- 用剪映 11.6 实测 `AItest_portable`（占位符段 + 绝对路径段并排）：**两段都有画面**

### 人像美化 + 花字（借 capcut-mate 的 metadata）

- `tools/jy_beauty.py` + `pipeline/jy_beauty_catalog.json`：skin 8 / shape 13 / body 12 / makeup 54 / skin_tone 2，滑杆 0–100
- `pipeline/jy_text_effects.json`：1673 条花字（免费 94 条），spec 里写中文名即可
- 机制：滑杆 → `materials.effects` type=figure + `extra_material_refs`，任意滑杆生效必补一条 `makeup-root`

### EP02 元素重排：audit FAIL 4 → 0

- 删 p1 的 cross（元素 25→24）；`label`→`box` 三处（占比 40%→29%）；slides 复用图 `u12b→u8b`
- `box` 重写为深底白字块（原来只画虚线框、不渲文字）
- 每屏锚点按底板人物位置定：`metro` 正中→分两侧、`office` 贴左→元素去右上、`sofa` 占左三分之二→右侧+左下
- 结果：`FAIL 0 · WARN 4`（剩 panel 最短 2.6s / 卡片单镜中位 2.14s / 5 句 <1.5s / 音效 0）

### 字幕去重

`NO_SUB = {hook, copy, section, wrong, list, outro, stat}` 不出字幕 → EP02 21/55 句无字幕，剪映字幕轨 55→34 段。

## 2026-11-25 之前（要点）

- panel 引擎：`film.json` 的 `panels[]` + `Panel.tsx`（7 种元素）+ `DataFilm` 按 panel 渲染，一屏多句、元素累加
- 剪映链路：`jy_env / jy.cmd / jy_draft / jy_from_film / jy_check / jy_cards` 六个入口，11.6 实测 `issues=[]`
- 三处硬修：只映射 panel 会一半黑场（`jy_cards` 补 30 段）、剪映 y 轴向上为正（`pct_y`）、无定宽文本框（`max_line_width`）
- 声音：按章合成 + 轻削静音 + whisper 词级对齐（525/525 字符），`atempo` 是"怪声"根因（改原生 `speech_rate`）
- 素材库真相：1316 帧抽 997 卡通帧，跨集近重复 **0 对** → 他的"库"是角色 + 提示词模板，每集现做 20–40 张
