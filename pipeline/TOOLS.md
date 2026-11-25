# 工具索引

> 对标 capcut-mate-skill 的 `references/tools-index.md`：**一个表查"我该调哪个工具"**，不要再翻 685 行的 SKILL。
> 所有命令都先设 `$py = "E:\miniconda\envs\JupyterProject\python.exe"`。

## 0 我在做什么 → 用哪个

| 我想… | 调这个 | 输出 |
|---|---|---|
| 从零出一条片 | `lbr-promo\pipeline\run.py all <name>` | `out/<name>-final.mp4` |
| 只估算时长/字数，不花钱 | `lbr-promo\pipeline\run.py plan <name> [script]` | 秒数 + 字数 + rate 建议 |
| 检查排布（元素/单镜/素材复用） | `lbr-promo\pipeline\audit.py` | FAIL / WARN 列表，FAIL 拦渲染 |
| 检查成片（时长/响度/静止/字速） | `lbr-promo\pipeline\check.py <name> [mp4]` | 11 项体检 |
| 把 film.json 变成剪映工程 | `tools\jy_from_film.py` | spec json → `jy_draft.py` |
| 直接写剪映工程（手工 spec） | `tools\jy_draft.py spec.json` | 加密登记好的草稿 |
| 回读草稿看落了什么 | `tools\jy_check.py <草稿目录>` | 轨/关键帧/黑场/素材本地化 |
| 草稿换机器不丢素材 | `jy_draft.py` 自动跑（`localize:false` 可关） | `<草稿>/assets/` + 占位符路径 |
| 加人像美颜 | spec 顶层 `beauty` | `materials.effects` type=figure |
| 加花字 | item 里 `text_effect: "白字红边立体字"` | 文字段 effect |
| 换设备/升级剪映 | `tools\jy_env.py --write-env` | `tools\jy.env` + 版本能力表核对 |
| 抓关键帧拼对比图 | `qa2\sheet_*.py` 自己写，参考 `sheet_e5.py` | contact sheet |
| 抽卡片静帧（垫满非 panel 段） | `tools\jy_cards.py --render` | `public/cards/l*.png` |
| 生图 | `tools\img.py "<prompt>" out.jpg --seed N` | 图 |
| 配音 | `tools\cosy_chapter.py`（`run.py voice` 已封装） | `public/audio/<name>.wav` |

## 1 工具逐个说明

### `lbr-promo\pipeline\run.py` — 主流水线

```powershell
& $py lbr-promo\pipeline\run.py plan   ep02 scripts\script-ep02.json
& $py lbr-promo\pipeline\run.py all    ep02 scripts\script-ep02.json
& $py lbr-promo\pipeline\run.py render ep02        # 单阶段：plan/voice/align/build/render/mix/check
```

- 子命令：`plan / voice / align / build / render / mix / check / all`
- 第 3 参数是脚本路径，**不给就用 `config.project.script`**（会拿错稿子）
- 渲染前自动设 `TEMP/TMP` 到 `lbr-promo\.tmp-remotion`（不设会报音频混音权限错误）
- 产物：`out/<name>-raw.mp4` → `out/<name>-final.mp4`（loudnorm −16 LUFS）

### `lbr-promo\pipeline\audit.py` — 排布体检（不渲染）

```powershell
& $py lbr-promo\pipeline\audit.py            # 读 config.project.script 生成的 film.json
& $py lbr-promo\pipeline\audit.py --json
```

10 项判据（阈值在文件顶部常量）：元素跨区 / label 占比 / panel 单镜 / 卡片单镜中位 / 短镜数 / y 越界 / 素材复用 / 字幕覆盖 / 音效 / emoji 占比。
**有 FAIL 不许渲染。**

### `lbr-promo\pipeline\check.py` — 成片体检

```powershell
& $py lbr-promo\pipeline\check.py ep02
& $py lbr-promo\pipeline\check.py ep02 "lbr-promo\out\ep02-final.mp4"
```

11 项：文件/时长/字数/句数/字秒/单镜中位/最长单镜/语速异常/最长静止/静止占比/响度。
**响度只对 `-final.mp4` 有意义**，raw 显示 −23 是跑错文件（没混音）。

### `tools\jy_from_film.py` — film.json → 剪映 spec

```powershell
& $py tools\jy_from_film.py --name "EP02_剪映工程" --spec-out qa2\jy-spec-ep02.json
& $py tools\jy_from_film.py --dry-run          # 只打印不落盘
```

分轨规则：底板→视频轨（scale 1→1.035 两关键帧）；元素→文字轨**按 panel 内序号分轨**（`元素1/2/3`，因为剪映同轨不能重叠）；卡片→`卡片` 视频轨（30 段，scale 1→1.02）；字幕→`字幕` 轨（`sub:false` 的句跳过）；配音→音频轨（fade 0.15/0.3）。
末了 `_fill_across()` 把视频层间隙补满 → 黑场 0。

### `tools\jy_draft.py` — spec → 剪映草稿

```powershell
& $py tools\jy_draft.py qa2\jy-spec-ep02.json
& $py tools\jy_draft.py --list-enums text_intro      # 查可用动画/转场/滤镜名
```

顺序固定：建轨 → 逐段 `add_segment`（**装饰必须在此之前**）→ `script.save()` → 素材本地化 → 美颜 → `finalize()`（加密 + 登记首页）。
spec 字段见 `pipeline/SPEC.md`。

### `tools\jy_check.py` — 回读校验

```powershell
& $py tools\jy_check.py "E:\剪映5.9版本免激活(1)\草稿\JianyingPro Drafts\EP02_剪映工程"
```

输出：版本/画布/时长、逐轨逐段（关键帧/引用数）、**画面覆盖（黑场）**、素材统计、**素材本地化**。

### `tools\jy_env.py` — 环境探测（换设备第一步）

```powershell
& $py tools\jy_env.py --check        # 核对：版本 / 草稿根 / skill 路径 / pyJianYingDraft
& $py tools\jy_env.py --write-env    # 写 tools\jy.env
```

现在还会打印**版本能力表**核对结果（`pipeline/jy_versions.json`）：该版本登记过没有、`new_version` 取多少、已验证哪些能力。

### `tools\jy_localize.py` — 素材本地化

被 `jy_draft.build()` 自动调用。单独用：`& $py tools\jy_localize.py <草稿目录>`。
做四件事：复制素材进 `assets/`、路径改 `##_draftpath_placeholder_<UUID>_##/assets/xxx`、`material_save_mode=1`、同步 `draft_meta_info.json` 的 `file_Path`。

### `tools\jy_beauty.py` — 人像美化

```powershell
& $py tools\jy_beauty.py --list
& $py tools\jy_beauty.py <草稿目录> --skin smooth=40,even=30 --shape slim=25 --tint 暖白:60:20
```

滑杆写 0 = 不写素材（等价剪映里关闭）；任意滑杆生效会自动补 `makeup-root`。

### `tools\jy_cards.py` — 卡片静帧

```powershell
& $py tools\jy_cards.py --render     # 渲 DataFilmNoSub → 按非 panel 句中点抽帧
& $py tools\jy_cards.py --list
```

不跑这个，剪映工程里非 panel 的 30 句全是黑场（EP02 实测 66s/117s）。

## 2 不要做的事（负面清单）

> capcut-mate-skill 明确列出"不要主动调用的接口"，我们也该有。以下每条都踩过。

| 别做 | 为什么 |
|---|---|
| 改完 `config.json` 就直接 `run.py all` | 先 `plan` 估时长，字数和目标差太多就是白配音（一次 3 分钟 + API） |
| 用 `run.py build xx` 漏第 3 参数 | 会用 `config.project.script`（38 句那版），生成错的 film.json |
| 对 `-raw.mp4` 跑 `check.py` 看响度 | raw 没混音，永远 −23 左右，会误判"太轻" |
| 把"静止占比高"当 bug 压 | 凯哥原片 0–30s 有连续 5 秒完全静止，全段 43%；静止是风格 |
| 手工改 `film.json` | 它是 build 产物，下次 `build_film.py` 就覆盖；改 `script-*.json` |
| 手工改加密后的 `draft_content.json` | 密文；改 spec 重新生成，或用 `jyai patch` |
| 在同一轨道放重叠片段 | 剪映 `SegmentOverlap` 直接失败；元素要"停留到屏尾"必须分轨 |
| 装饰写在 `add_segment()` 之后 | 素材不登记，只留悬空 ref，finalize 一剥动画全没 |
| 给 `tim()` 传小数秒 | 单位是微秒，`0.35` → 0；用 `us(秒)` 或 `"0.35s"` |
| 只映射 panel 就交付剪映工程 | panel 只覆盖 44%，其余全黑；必须跑 `jy_cards.py` |
| 用 emoji 当图标交付 | 剪映渲成系统彩色表情，跨设备不一致；长期要换 PNG |
| 想靠换更强语言模型解决"图不够戏" | 卡通只有单场景单姿势，是生图通道的上限，不是文案问题 |
| 在 TUN 模式下发誓 `NO_PROXY` 能救 | TUN 是网络层劫持，进程级环境变量无效；只能靠 Clash 规则分流 |
