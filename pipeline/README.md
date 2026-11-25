# 凯哥式短视频流水线（男生变帅）

> **范围**：这个流水线只服务「男生变帅」口播片。LBR 洗面奶项目已停用——`Root.tsx` 里 `LbrFilm120` / `AiflPromo` 两个 composition 已移除，`src/lbr120/`、`src/aifl/` 旧文件留着但不再注册。目录名 `lbr-promo` 是历史遗留，不影响使用。

从**一句文稿**到**一条成片**，全部走 `pipeline/`。参数只在 `config.json` 改，脚本不用动。

```
video/
├─ lbr-promo/
│  ├─ pipeline/
│  │   ├─ config.json    ← 唯一真源：所有数字阈值、音色、颜色、字号
│  │   ├─ run.py         ← 跑流程（voice / align / build / render / mix / check / all）
│  │   ├─ check.py       ← 自动质检
│  │   ├─ SPEC.md        ← 规格全文（讲规则，数字指向 config 字段）
│  │   └─ README.md      ← 本文
│  ├─ scripts/
│  │   ├─ script-bs.json   ← 文稿（一句一卡）
│  │   └─ build_film.py      ← 文稿+时间轴 → film.json
│  ├─ src/bs/Cards.tsx       ← 卡型组件（改样式来这里）
│  ├─ src/bs/DataFilm.tsx    ← 渲染入口（读 film.json）
│  ├─ public/audio/          ← 配音 wav
│  └─ out/                   ← 成片
└─ tools/                    ← cosy_chapter.py（配音）、align_v2.py（对齐）
```

## 一条命令

```powershell
cd C:\Users\张宇\OneDrive\Desktop\video
E:\miniconda\envs\JupyterProject\python.exe lbr-promo\pipeline\run.py all voice-bs
```

七个阶段依次跑：配音 → 对齐 → 生成 film.json → 渲染 → 混音 → 质检。

## 分阶段跑（改了什么就跑哪几步）

| 你改了什么 | 跑这些 |
|---|---|
| 只改文案措辞（句数不变） | `voice` → `align` → `build` → `render` → `mix` |
| 只改卡片类型/配色（`script-bs.json` 的 `card`） | `build` → `render` → `mix` |
| 只改 `config.json` 的卡片字号/颜色 | `render` → `mix` |
| 改语速 `voice.rate` | `voice` → `align` → `build` → `render` → `mix` |
| 只改混音响度 | `mix` |
| 只想看数据 | `check` |
| 只想先知道会做多长 | `plan`（不花钱、不配音） |

```powershell
... python lbr-promo\pipeline\run.py build voice-bs
```

> **名字说明**：`ep` 是音频/成片的文件名基名。当前 EP01 沿用历史名 `voice-bs`（`public/audio/voice-bs.wav`、`out/voice-bs-final.mp4`）。新选题建议直接叫 `ep02`、`ep03`。

## 时长：两种模式

`config.json` → `video.duration`

```json
{ "mode": "auto", "target_sec": 100, "tolerance_pct": 8, "auto_bounds": [30, 600] }
```

| mode | 含义 | 质检 |
|---|---|---|
| `auto`（默认） | **稿子写多长就多长**，不设目标 | 只卡 30–600s 合理区间，字数不卡 |
| `target` | 卡死 `target_sec ± tolerance_pct` | 时长是硬指标，字数按目标反推 ±10% |

想做 **90 秒**：改 `mode: "target"`、`target_sec: 90`，然后跑 `plan`：

```
目标 90s（±8% → 83–97s）
  需要字数 ≈ 472    当前 525    差额 +53 字
  两条路：① 改字数到 472  ② 语速 rate 1.18 → 1.38
```

**先 `plan` 再决定删字还是加速**——加语速会牺牲"像人说话"的感觉，优先删字。

## 文稿格式

`lbr-promo/scripts/script-bs.json`：

```json
{
  "title": "变帅5件事",
  "fps": 30,
  "watermark": "",
  "chapters": [
    {
      "label": "序",
      "lines": [
        { "text": "兄弟们，先说句实话。",
          "card": { "type": "copy", "text": "兄弟们，|先说句实话", "size": 104, "dark": true } }
      ]
    }
  ]
}
```

- `text` = 配音念的字（字幕同步显示这个）
- `card` = 这一句画面上放什么（不写就黑屏，必须每句都写）
- `|` = 换行
- `label` = 底部进度条的分段名

### 卡型清单（`card.type`）

| type | 用途 | 主要字段 |
|---|---|---|
| `copy` | 大字一句话（最常用） | text, size, dark |
| `section` | 章节封页（01 / 头发 / HAIR） | no, title, sub |
| `list` | 打勾清单 | title, items[] |
| `no-list` | 打叉清单 | title, items[] |
| `stat` | 大数字（−3 CM / 1 个月） | value, unit, note |
| `image` | 实拍图满屏 | src, caption |
| `quote` | 引用金句 | text, source |
| `chips` | 三标签并排 | items[] |
| `brow` | 眉毛图解 | — |
| `posture` | 体态点位图 | — |
| `color` | 四色卡 | — |
| `cmd` | 命令行/步骤 | text |
| `outro` | 收尾（START TODAY） | text |
| `teacher` | 讲台提问（讲师剪影 + 一句问） | text, sub |
| `board` | 墨绿黑板编号 1 2 3（逐条滑入） | title, items[] |
| `wrong` | 错误示范（红叉） | text, items[] |
| `annotate` | 实拍 + 红点标注 | src, points[{x,y,label}], caption |
| `slides` | 卡通图当幻灯片放（2–4 张/句，硬切 + 微推） | frames[], hold, text, push |
| `hook` | 卡通角色气泡（**已弃用**，与纸白大字卡风格冲突） | bubble |

**每张卡都能单独指定转场**（不写默认 `fade`）：

```json
"card": { "type": "copy", "text": "…", "transition": "cut" }
```

可选值：`cut`（硬切，默认占 85%）/ `fade`（6 帧）/ `slideL` / `slideR`（±70px）/ `zoom`（0.94→1）/ `slam`（1.16→1）。
选哪个、为什么，见 [ANIMATION.md](ANIMATION.md)；动画实现交给 Remotion 组件或 `video-shotcraft` 镜头卡，本文件只列可用卡型。

## 改一个小点，改哪里

**唯一原则：能动 `config.json` 就不动脚本。**

| 想改 | 改哪个字段 |
|---|---|
| 语速快慢 | `voice.rate`（越大越快；1.18 ≈ 5.1 字/秒） |
| 生图用哪家、用哪把 key | `images.provider` / `images.model` / `images.base_url` / `images.api_key_env` |
| 句子之间停多久 | `voice.gap_between_chapters` |
| 句内静音留多少 | `voice.silence_keep`（0.30 已实测最自然） |
| 音色 | `voice.voice`（`longcheng_v2` 最接近凯哥 163Hz） |
| 大字卡字号 | `card.title_size` / `card.copy_size` |
| 强调红 | `card.accent` |
| 纸白底 / 墨绿 / 墨色 | `card.bg` / `card.green` / `card.ink` |
| 每行最多几个字 | `card.line_max_chars` |
| 入场时长 | `card.enter_ms` |
| 入场起始透明度 | `card.opacity_start`（**保持 0.15**，改 0 会闪白） |
| 字幕字号 / 距底 | `video.subtitle.size` / `video.subtitle.bottom_offset` |
| 进度条分段数 / 线宽 | `video.progress.*` |
| 成片时长目标 | `video.duration_sec`（只用于质检判断） |
| 画质 | `video.crf`（19 已是高质量） |
| 响度 | `voice.lufs` / `voice.true_peak` |
| 质检严格程度 | `check.*` / `video.shot_max_sec` / `video.still_max_sec` |

改完 `card.*` 或 `video.*` → 只需 `render` + `mix`。
改完 `voice.*` → 从 `voice` 开始重跑。

## 质检读法

```
✓ 硬指标   FAIL 会让 run.py 停下
· 风格指标  只提示，不阻断
```

当前 EP01 实测（run.py all 全流程产出）：9.1 MB / 103.2s / 525 字 / 5.09 字秒 / −16.11 LUFS / −1.30 dBTP / 0 异常句。
两条风格提示：单镜中位 2.46s（目标 2.5–3.0）、最长单镜 4.76s（目标 ≤4.0）——都在可接受范围，若想收紧，把那句拆成两句。

## 常见故障

| 症状 | 原因 | 处理 |
|---|---|---|
| 渲染报 `Permission denied ... remotion-audio-mixing` | TEMP 指向系统临时目录 | run.py 已自动设为 `lbr-promo\.tmp-remotion`；手工渲染时先 `$env:TEMP` |
| 对齐报网络错误 | HuggingFace 连不上 | run.py 已注入 `HF_ENDPOINT=https://hf-mirror.com` |
| 画面闪白 | 卡片 opacity 从 0 起 | `card.opacity_start` 保持 0.15 |
| 字幕和语音不同步 | 没重新 align | 改文案后必须 `align` 再 `build` |
| 声音"断触" | 逐句拼接 / atempo 加速 | 只按章合成 + 原生 `speech_rate`，不要 atempo |
| 配音报 `MP3_24000HZ` 不存在 | 枚举名错 | 用 `AudioFormat.MP3_24000HZ_MONO_256KBPS` |
| 底部进度条段落名不对 | `label` 写在 chapters 里 | 改 `script-bs.json` 的 `label`，重跑 `build` |

## 换选题怎么做

1. 复制 `scripts/script-bs.json` → `script-ep02.json`，改 `title` 和每句 `text`
2. `config.json` 的 `project.ep` 改成 `ep02`、`project.script` 指向新文件
3. 跑 `run.py all ep02`
4. 看 `check` 报告：字数 / 语速 / 镜长不对就调文案，别调阈值
