# 变更记录

只记**会影响怎么做**的改动（新能力、口径变化、踩坑修正）。参数以 `lbr-promo/pipeline/config.json` 为准。

## 2026-11-25

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
