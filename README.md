# 男生变帅 · 口播短视频流水线

一套可复现的「**文稿 → 配音 → 逐句卡点 → 渲染 → 质检**」流水线，用来生产 90–120 秒的横屏知识口播片（1280×720，底部分段进度条，逐句字幕）。

对标抖音「凯哥恋爱说」的形态，但**方法论、参数、素材规格全部显式化**，不靠手感。

---

## 30 秒上手

```bash
# 1 体检（缺什么会直接告诉你装什么）
python pipeline/preflight.py

# 2 缺依赖就一键装
python pipeline/preflight.py --install

# 3 跑一条
python pipeline/run.py all ep02 scripts/script-ep02.json
```

产物在 `remotion/out/ep02-final.mp4`。

> 换自己的片子：复制 `scripts/script-ep02.json` 改文案与卡片，改 `pipeline/config.example.json` 里的参数，重跑。

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
  config.example.json   所有可调参数（复制成 config.local.json 再改）
  run.py                一条命令跑完：voice → align → build → render → mix → check
  check.py              11 项自动质检
  preflight.py          依赖自检 / 自动安装
  README.md             怎么用、改哪个字段
  SPEC.md               内容 / 文稿 / 动画 / 素材 / 流程的完整规格
  ANIMATION.md          动画与转场的"看起来该是什么样"
  CARTOON.md            卡通素材的数量、节拍与衔接六法
scripts/
  script-*.json         逐句文稿 + 每句的画面卡
  build_film.py         文稿 + 时间轴 → film.json
tools/
  cosy_chapter.py       按章合成配音（cosyvoice-v2）
  align_v2.py           whisper 词级对齐 → timeline.json
  img.py                文生图（多 provider，支持 --seed 锁角色）
  shot_stats.py         测镜头密度 / 静止占比
remotion/
  src/bs/Cards.tsx      19 种卡片组件
  src/bs/DataFilm.tsx   渲染入口（读 film.json，逐句一镜）
  src/Root.tsx          composition 注册
```

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
