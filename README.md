<div align="center">

<img src="./assets/hero_banner.jpg" alt="Paper-Ear Hero Banner" width="100%" />

# 🎧 Paper-Ear

### 把枯燥的 PDF 论文变成「可搜索证据网页」，也能开一场图文并茂的男女双人组会
**Turn Academic PDFs into Offline Interactive Evidence Readers or Group-Meeting MP4 Videos**

[![Agent Skill](https://img.shields.io/badge/Agent_Skill-paper--ear-FF3B30?style=for-the-badge&logo=sparkles&logoColor=white)](#2-方式一作为-agent-skill-交互式调用推荐)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](#1-环境准备-prerequisites)
[![Offline Web](https://img.shields.io/badge/Web-Offline_Evidence_Reader-137F97?style=for-the-badge&logo=html5&logoColor=white)](#-交互式网页速读-interactive-web-reader)
[![FFmpeg](https://img.shields.io/badge/FFmpeg-1080p_H.264-007808?style=for-the-badge&logo=ffmpeg&logoColor=white)](#4-命令行视频模式)
[![Edge-TTS](https://img.shields.io/badge/Audio-Neural_Male_%26_Female_TTS-0284C7?style=for-the-badge)](#男女双人语音声线配置-voice-configuration)
[![License: MIT](https://img.shields.io/badge/License-MIT-F59E0B?style=for-the-badge)](https://opensource.org/licenses/MIT)

[**⚡ 网页速读模式**](#-交互式网页速读-interactive-web-reader) •
[**🎬 视频演示效果**](#-效果演示与示例视频-live-demo--video-showcase) •
[**🖥️ 画面五大模块拆解**](#️-视频画面五大核心区域拆解-frame-anatomy) •
[**🔄 多轮交互式定制流程**](#-多轮交互式工作流全解-interactive-workflow) •
[**🚀 快速安装与使用**](#-快速安装与使用指南-quick-start) •
[**📐 剧本 JSON 规范**](#-对话与红框配置规范-script-json-schema)

</div>

## 🌟 为什么需要 Paper-Ear？ (Why Paper-Ear?)

读顶会论文（NeurIPS / CVPR / ACL / ICML）时，直接看满篇公式容易犯困，而普通的「AI 文本总结」又脱离了论文原图、原表和具体公式位置。**Paper-Ear** 提供两种消费方式：想快读就打开交互式证据网页，想听懂就生成沉浸式双人组会视频。

| 对比维度 | 传统自己啃 PDF | 普通 AI 文本摘要 | 🎧 **Paper-Ear Skill** |
| :--- | :--- | :--- | :--- |
| **定制化程度** | 从头读到尾，抓不住重点 | 千篇一律的模板式总结 | **多轮交互定制**：先选创新点、专业名词解析深度、目标章节再生成 |
| **讲解形式** | 枯燥默读 | 静态文字或单人机械朗读 | **网页三档阅读深度**，或女声主讲 + 男声追问的双人组会视频 |
| **视觉定位** | 自己在字里行间找图找公式 | 脱离原文排版，图表丢失 | 网页保留**全部原像素图/表/公式裁图与原页定位**；视频讲到哪、红框跟到哪 |
| **语言与专业度** | 纯英文阅读门槛高 | 术语翻译生硬 | **中英双语同步字幕** + 右侧实时切换**专业名词与创新点解析卡片** |
| **最终交付物** | 无 | 零散聊天记录 | 可离线打开的静态网页/ZIP，或单个 1080p `.mp4` 高清视频 |

## ⚡ 交互式网页速读 (Interactive Web Reader)

不爱看视频时，Paper-Ear 会把论文整理成一个**完全离线、可搜索、可追溯**的静态网页。正文摘要保持为可检索文本，论文中的图、表和陈列公式则直接从 PDF 原始页面裁切；点击任一视觉证据即可在“高清裁图”和“PDF 原页定位”之间切换。

<div align="center">
  <img src="./assets/web_reader_preview.png" alt="Paper-Ear interactive evidence reader preview" width="96%" />
  <p><i>▲ 网页速读预览：左侧证据导航 + 30 秒 / 3 分钟 / 深读三档 + 原始图表公式定位</i></p>
</div>

| 功能 | 网页中的实际行为 |
| :--- | :--- |
| **三档阅读深度** | 30 秒先抓结论，3 分钟看论证链，深读模式展开逐段梳理与术语表 |
| **证据账本** | 将论文证据、作者主张、讲解推断、批判性分析分色展示，并标注证据强度与 PDF 页码 |
| **完整视觉清单** | 逐页人工复核所有编号图、表、陈列公式；每一项必须纳入网页或写明排除理由 |
| **原图双视图** | 一键切换高清裁图与带红框的 PDF 原页，避免 AI 重画导致坐标、数值或图例失真 |
| **快速定位** | 页面内搜索、图/表/公式筛选、证据收藏、章节滚动定位和阅读进度条 |
| **离线与隐私** | 无远程脚本、无分析追踪、无自动 API 请求；用户论文默认只在本地运行目录处理 |

仓库已内置可直接打开的虚构示例：[`examples/web-reader-demo/index.html`](./examples/web-reader-demo/index.html)。它与视频示例使用同一篇双页样例论文，不包含任何用户提供的测试 PDF。

## 🎬 效果演示与示例视频 (Live Demo & Video Showcase)

下方展示了使用 **Paper-Ear** 对示例论文《*Sparse-Ear: Dynamic Token Routing for Efficient Long-Context Multimodal Reasoning*》自动生成的 **1080p 组会汇报视频**动态预览（完整 MP4 视频文件已内置于仓库 [`examples/paper_ear_demo.mp4`](./examples/paper_ear_demo.mp4)）：

<div align="center">
  <img src="./assets/demo_preview.gif" alt="Paper-Ear 5-Turn Demo Preview GIF" width="96%" />
  <p><i>▲ 动态预览：红框随男女对话自动在 Abstract、核心创新点、公式 (1)-(2)、Figure 1 架构图与 Table 1 实验表之间精准跳转</i></p>
</div>

### 🎞️ 示例视频分镜脚本一览 (`examples/paper_ear_demo.mp4`)

| 轮次 (Turn) | 讲者角色 | 所在页码与红框锁定区域 (`red_box`) | 对话核心内容与右侧知识卡片同步展示 |
| :---: | :--- | :--- | :--- |
| **Turn 1** | **● 主讲人 Lin (女声)** | `Page 1` • **Abstract 摘要全段**<br>`[0.09, 0.165, 0.91, 0.325]` | 指出传统 Transformer 在 128K 长文本下的 $O(N^2)$ 计算复杂度与 KV 显存瓶颈，引出动态稀疏路由动机 |
| **Turn 2** | **◆ 师兄 Alex (男声)** | `Page 1` • **Section 1 三大核心创新点**<br>`[0.08, 0.34, 0.92, 0.58]` | 针对专业名词 **Soft-Gumbel Capacity Gate** 发问：它与传统 Hard Top-K 硬截断门控有何本质区别？ |
| **Turn 3** | **● 主讲人 Lin (女声)** | `Page 1` • **Eq. (1) & Eq. (2) 核心公式**<br>`[0.09, 0.68, 0.91, 0.81]` | 结合红框放大的公式 (1)-(2) 解答温度系数 $\tau$ 连续松弛机制，说明如何保证端到端可微训练 |
| **Turn 4** | **● 主讲人 Lin (女声)** | `Page 2` • **Figure 1 双分支模型架构图**<br>`[0.08, 0.068, 0.92, 0.41]` | 框选整幅架构图并在右侧高清放大，拆解上方 Heavy Attention 分支（25% 锚点）与下方 Light Pooling 分支 |
| **Turn 5** | **◆ 师兄 Alex (男声)** | `Page 2` • **Table 1 消融与加速对比表**<br>`[0.08, 0.49, 0.92, 0.77]` | 点评实验表格高亮行：显存直降 **58%**、推理提速 **3.4x**，且 LongBench 准确率反超基线 **+2.1%** |

## 🖥️ 视频画面五大核心区域拆解 (Frame Anatomy)

每一帧 1920×1080 画面均经过专为学术阅读设计的分栏布局排版，确保「听得懂逻辑、看得清公式、记得住术语」：

<div align="center">
  <img src="./assets/frame_anatomy.png" alt="Paper-Ear Frame Anatomy" width="96%" />
</div>

- **① 动态红框追踪 + 四角瞄准框 (Dynamic Red-Box Focus)**：基于 `pdfplumber` 词元级坐标提取与视觉边界框匹配，当前讲到哪一段、哪条公式或哪张图，红框就自动锁定哪里，并将背景其余区域柔和压暗以突出视觉焦点。
- **② 男女双人组会角色与声波状态栏 (Speaker HUD & Live Waveform)**：顶部实时高亮当前发言人（女声主讲人蓝色声波 / 男声提问师兄橙色声波），营造真实的实验室一问一答互动感。
- **③ 红框区域高清同步放大视图 (Highlighted Region Zoom)**：自动从高分辨率 PDF 渲染图中裁切当前红框区域并在右侧等比放大，解决原论文双栏排版字号过小、看清全页就看不清公式脚标的痛点。
- **④ 核心创新点与专业名词深度解析卡片 (Terminology & Key Notes Card)**：随对话轮次实时切换当前段落的术语中英释义、数学符号物理意义与核心结论提炼。
- **⑤ 中英双语同步字幕 + 章节进度条 (Bilingual Subtitles & Progress Bar)**：底部醒目展示上中下英双语字幕，配合最下方的红线章节进度条，随时掌握组会推进节奏。

## 🔄 多轮交互式工作流全解 (Interactive Workflow)

**Paper-Ear** 拒绝“丢进 PDF 直接盲目生成”。它通过结构化的**多轮交互（Multi-Turn Interaction）**，先与你对齐解读方向，再合成最终视频：

<div align="center">
  <img src="./assets/workflow_diagram.png" alt="Paper-Ear Multi-Turn Workflow" width="96%" />
</div>

### 💬 真实交互过程示例 (Interactive Session Walkthrough)

```text
👤 用户：
[上传论文 Sparse_Ear_NeurIPS2026.pdf] 用 paper-ear 帮我解读这篇论文。

🤖 Paper-Ear (第 1 轮交互 —— 解析论文并弹出定制菜单)：
我已经解析完这篇论文（共 2 页，包含 3 个核心章节、2 组核心公式、1 幅双分支架构图 Figure 1 和 1 张对比表 Table 1）。
在生成组会视频前，请先确认你的定制偏好：
1. 【选择创新点】：本文检测到 3 个核心创新点：
   - (A) Differentiable Sparse Routing (DSR 动态可微稀疏路由)
   - (B) Soft-Gumbel Capacity Gate (软 Gumbel 容量门控)
   - (C) Cross-Scale KV Compression (跨尺度 KV 显存压缩)
   你想重点剖析哪几个？
2. 【解析专业名词】：检测到术语 `KV-Cache`、`Soft-Gumbel Relaxation`、`Top-K Pruning`、`State-Space Pooling`，需要采用「跨领域通俗拆解模式」还是「熟手深度机制模式」？
3. 【解读哪部分内容】：需要按「全篇标准组会流程 (Abstract → Method → Fig.1 → Table 1)」解读，还是只聚焦特定章节？

👤 用户：
创新点重点讲 A 和 B；专业名词用跨领域通俗模式把 Soft-Gumbel 和 Hard Top-K 的区别讲透；内容覆盖全篇重点图表。

🤖 Paper-Ear (第 2 轮交互 —— 确认男女对话剧本与红框坐标映射)：
收到！我为你拟定了共 5 轮的「女声主讲人 Lin + 男声师兄 Alex」组会问答大纲及每轮对应的 PDF 红框位置：
- Turn 1 [Page 1 红框框选 Abstract]：女声介绍长文本 O(N²) 痛点与整体思路
- Turn 2 [Page 1 红框框选 Section 1 创新点列表]：男声追问专业名词 Soft-Gumbel 与 Hard Top-K 的本质区别
- Turn 3 [Page 1 红框框选 Eq.(1)-(2)]：女声结合公式拆解温度系数 tau 如何避免梯度截断
- Turn 4 [Page 2 红框框选 Figure 1 架构图]：女声配合右侧放大图讲解 Heavy/Light 双分支分流过程
- Turn 5 [Page 2 红框框选 Table 1 实验表]：男声总结 58% 显存节省与 3.4x 推理加速结果
确认无误的话我立即为你渲染输出 1080p MP4 视频！

👤 用户：
确认，直接生成 MP4！

🤖 Paper-Ear (第 3 步 —— 渲染直出 1080p MP4 视频)：
🎬 已为你生成并输出组会精读视频：`paper_ear_demo.mp4`
```

## 🚀 快速安装与使用指南 (Quick Start)

### 1. 环境准备 (Prerequisites)

网页模式只要求 `poppler`（提供 `pdftoppm` 页面渲染工具）；视频模式还需要 `ffmpeg` / `ffprobe`。然后安装 Python 依赖：

```bash
# Ubuntu / Debian 系统依赖
sudo apt-get update && sudo apt-get install -y ffmpeg poppler-utils fonts-noto-cjk

# macOS (Homebrew) 系统依赖
brew install ffmpeg poppler

# 克隆本仓库并安装 Python 依赖
git clone https://github.com/siyunhao2025-beep/paper-ear.git
cd paper-ear
pip install -r requirements.txt
```

### 2. 方式一：作为 Agent Skill 交互式调用（推荐）

将本仓库目录导入支持 `SKILL.md` 的 AI Agent 环境（或直接在对话中启用 `paper-ear` Skill），上传任意 PDF 论文并发送触发指令：

- `用 paper-ear 帮我生成这篇论文的组会讲解视频`
- `paper-ear 解读这篇 PDF，重点讲第 3 节的方法架构图和公式`
- `用 paper-ear 把这篇论文做成可快速浏览的离线网页，保留全部图表公式`
- `我只有 3 分钟，生成一个能搜索、能回到原页的论文阅读器`

### 3. 命令行：网页模式

网页模式不需要 FFmpeg 或 TTS。下面用仓库内的虚构双页论文走完「解析 → 视觉清单 → 证据校验 → 网页生成 → 离线验收」：

```bash
# Step 1: 提取完整文本、坐标并渲染每一页
python3 scripts/inspect_paper.py \
  --pdf examples/sample_paper.pdf \
  --out /tmp/paper-ear-web/paper_structure.json \
  --render-dir /tmp/paper-ear-web/pages \
  --dpi 180

# Step 2: 生成图、表、公式候选清单；仍须逐页人工复核
python3 scripts/build_visual_inventory.py \
  --structure /tmp/paper-ear-web/paper_structure.json \
  --out /tmp/paper-ear-web/visual_inventory.json

# Step 3: 严格校验证据锚点、声明类型、裁图坐标和完整性计数
python3 scripts/validate_web_brief.py \
  --pdf examples/sample_paper.pdf \
  --brief examples/sample_web_brief.json \
  --strict \
  --json-out /tmp/paper-ear-web/web_brief_qa.json

# Step 4: 生成无远程依赖的静态网页，并把示例 PDF 复制到本地离线包
python3 scripts/render_paper_web.py \
  --pdf examples/sample_paper.pdf \
  --brief examples/sample_web_brief.json \
  --output-dir /tmp/paper-ear-web/site \
  --pages-dir /tmp/paper-ear-web/pages \
  --copy-pdf \
  --report-json /tmp/paper-ear-web/web_render_report.json

# Step 5: 检查页面控件、全部裁图/原页定位、离线资源和视觉清单
python3 scripts/verify_web_reader.py \
  --site /tmp/paper-ear-web/site \
  --strict \
  --json-out /tmp/paper-ear-web/web_qa.json
```

完整字段说明见 [`references/web-brief-schema.md`](./references/web-brief-schema.md)，发布前人工检查见 [`references/web-quality-checklist.md`](./references/web-quality-checklist.md)。`--copy-pdf` 只把论文复制到本地交付目录，不代表允许把用户论文提交到仓库或上传。

### 4. 命令行：视频模式

你也可以直接在本地终端执行完整的「预检 → 解析 → 剧本校验 → 快速预览 → 正式渲染 → 成片验收」流程。所有中间文件统一放在一个运行目录中，失败后可以从对应阶段继续：

```bash
# Step 1: 检查 PDF、Python 依赖与 ffmpeg / ffprobe / pdftoppm
python3 scripts/validate_dialogue.py \
  --pdf examples/sample_paper.pdf

# Step 2: 解析 PDF 页面结构、段落/图表归一化坐标，并导出页面预览图
python3 scripts/inspect_paper.py \
  --pdf examples/sample_paper.pdf \
  --out /tmp/paper-ear-run/paper_structure.json \
  --render-dir /tmp/paper-ear-run/pages \
  --dpi 150

# Step 3: 严格校验页码、红框、证据锚点、声明类型和字幕长度
python3 scripts/validate_dialogue.py \
  --pdf examples/sample_paper.pdf \
  --script examples/sample_dialogue.json \
  --strict \
  --json-out /tmp/paper-ear-run/script_qa.json

# Step 4: 先低成本渲染四轮“主张→质疑→回答→让步”微场景
python3 scripts/render_paper_video.py \
  --pdf examples/sample_paper.pdf \
  --script examples/sample_dialogue.json \
  --output /tmp/paper-ear-run/preview.mp4 \
  --dpi 110 \
  --max-turns 4 \
  --report-json /tmp/paper-ear-run/preview_render_report.json

# Step 5: 正式渲染；--require-tts 会阻止无声节拍被误当成可交付旁白
python3 scripts/render_paper_video.py \
  --pdf examples/sample_paper.pdf \
  --script examples/sample_dialogue.json \
  --output /tmp/paper-ear-run/final.mp4 \
  --dpi 180 \
  --fps 12 \
  --require-tts \
  --report-json /tmp/paper-ear-run/render_report.json

# Step 6: 验证 1080p 分辨率、音视频流、时长与 A/V 漂移
python3 scripts/verify_video.py \
  --video /tmp/paper-ear-run/final.mp4 \
  --json-out /tmp/paper-ear-run/video_qa.json
```

## 🎙️ 男女双人语音声线配置 (Voice Configuration)

Paper-Ear 现在支持两条真实语音链路：`edge-tts` 适合无需密钥的快速神经语音，`azure-speech` 适合需要逐回合情绪、说话风格、停顿、重音和强度控制的正式成片。网络或凭据不可用时，脚本只会生成用于视觉计时的 `offline-cadence`；它**不是可听懂的旁白**。正式成片请始终启用 `--require-tts`，以阻止静默降级。

默认“严谨组会 + 轻答辩感”选角：

| 角色定位 | 默认声线 | 风格轨迹 | 备选声线 |
| :--- | :--- | :--- | :--- |
| **女声主讲人 (Presenter)** | `zh-CN-XiaoxiaoNeural` | `chat → serious → excited → calm` | `zh-CN-XiaoyiNeural` |
| **男声质疑者 (Discussant)** | `zh-CN-YunjianNeural` | `narration-relaxed → serious → documentary-narration` | `zh-CN-YunxiNeural` / `zh-CN-YunyangNeural` |

Azure 凭据只从环境变量读取，不写入 JSON、日志或仓库：

```powershell
$env:AZURE_SPEECH_KEY = "<your key>"
$env:AZURE_SPEECH_REGION = "<your region>"
```

先生成不联网的 SSML 审核稿，再合成两条选角试听：

```bash
python scripts/render_voice_auditions.py \
  --config examples/sample_voice_casting.json \
  --output-dir /tmp/paper-ear-audition \
  --dry-run

# 配好凭据后移除 --dry-run
python scripts/render_voice_auditions.py \
  --config examples/sample_voice_casting.json \
  --output-dir /tmp/paper-ear-audition
```

在线语音接口只接收最终旁白文本与 SSML 控制；PDF、全文、页面图、图表和本地路径均不会发送。完整选角、隐私边界、试听门槛与互动改写提示词见 [`references/voice-casting-and-dialogue.md`](./references/voice-casting-and-dialogue.md)。

## 📐 对话与红框配置规范 (Script JSON Schema)

`render_paper_video.py` 接收的 `dialogue_script.json` 结构清晰直观，支持**显式归一化坐标 `red_box`** 与**关键词自动坐标匹配 `search_text`** 双重定位：

```json
{
  "title": "Sparse-Ear: Dynamic Token Routing for Long-Context Reasoning",
  "male_name": "师兄 Alex (提问/思辨)",
  "female_name": "主讲人 Lin (精读讲解)",
  "voice_backend": "azure-speech",
  "male_voice": "zh-CN-YunjianNeural",
  "female_voice": "zh-CN-XiaoxiaoNeural",
  "turns": [
    {
      "page": 1,
      "section_tag": "Page 1 • Abstract & Motivation",
      "speaker": "female",
      "dialogue_act": "claim",
      "responds_to_turn": 0,
      "emotion": "serious",
      "emotion_intensity": 0.55,
      "delivery": {
        "provider_style": "serious",
        "style_degree": 1.08,
        "rate": "+0%",
        "pitch": "+0Hz",
        "volume": "+0%",
        "pause_before_ms": 100,
        "pause_after_ms": 300,
        "emphasis_terms": ["O(N²)"]
      },
      "question_target": "",
      "interaction_tags": [],
      "zh_text": "大家好！今天组会我们精读这篇 Sparse-Ear 论文。先看红框里的摘要，它主要解决长序列下自注意力 O(N²) 复杂度痛点。",
      "en_text": "Hi everyone! Today we're presenting Sparse-Ear. Looking at the highlighted Abstract, it tackles the O(N^2) complexity bottleneck.",
      "search_text": "Abstract",
      "red_box": [0.09, 0.165, 0.91, 0.325],
      "box_label": "Abstract / 核心痛点与动机",
      "card_title": "核心动机与背景 (Motivation)",
      "notes": [
        "传统 Transformer 在 128K 长文本下显存与计算开销呈二次方暴涨",
        "本文提出动态稀疏路由 (Dynamic Token Routing)，兼顾速度与跨段落推理精度"
      ],
      "claim_type": "author_claim",
      "evidence_anchor": {
        "page": 1,
        "kind": "section",
        "label": "Abstract"
      }
    }
  ]
}
```

每一轮都应使用 `evidence_anchor`（兼容旧字段 `source_anchor`）记录证据所在页及章节/图/表/公式标签，并用 `claim_type` 区分论文证据、作者主张、讲解者推断和批评。启用 `evidence-dialogue-v2` 后，严格校验器还会检查质疑比例、追问、分歧、让步、自我修正、未决问题，以及每个问题是否在一到两轮内得到证据回应。完整字段、几何规则与示例见 [`references/dialogue-schema.md`](./references/dialogue-schema.md)。

## 📂 仓库目录结构 (Repository Layout)

```text
paper-ear/
├── .gitignore                       # 忽略 Python 缓存、虚拟环境与本地运行目录
├── SKILL.md                         # Agent Skill 核心定义与证据约束工作流
├── README.md                        # 项目主页文档（含视觉预览、架构图与使用说明）
├── LICENSE                          # MIT 开源协议
├── requirements.txt                 # Python 依赖包列表
├── push_to_github.sh                # macOS / Linux 一键推送至 GitHub 脚本
├── push_to_github.bat               # Windows 一键推送至 GitHub 脚本
├── agents/
│   └── openai.yaml                  # Skill 展示名称、简介与默认提示词
├── assets/
│   ├── hero_banner.jpg              # 项目顶部视觉横幅海报
│   ├── demo_preview.gif             # 5 轮红框追踪与男女对话动态预览 GIF
│   ├── frame_anatomy.png            # 视频画面五大核心区域拆解标注图
│   ├── workflow_diagram.png         # 多轮交互式工作流与系统架构图
│   ├── web_reader_preview.png       # 交互式证据阅读器桌面预览图
│   └── web-reader/                  # 完全本地的 HTML/CSS/JS 阅读器模板
├── references/
│   ├── dialogue-schema.md           # 带证据锚点与声明类型的完整剧本规范
│   ├── voice-casting-and-dialogue.md # 声线选角、Azure 隐私边界、试听与互动提示词
│   ├── quality-checklist.md         # 内容、视觉、音频与媒体发布检查表
│   ├── web-brief-schema.md          # 网页证据地图、视觉清单与声明类型规范
│   ├── web-quality-checklist.md     # 网页内容、交互、移动端与离线验收清单
│   └── web-design-provenance.md     # 高星项目调研来源与设计取舍
├── scripts/
│   ├── inspect_paper.py             # PDF 页面尺寸、文本块/图表归一化坐标提取工具
│   ├── build_visual_inventory.py    # 图/表/公式候选盘点（输出必须逐页复核）
│   ├── validate_web_brief.py        # 网页证据、页码、裁图与完整性严格校验器
│   ├── render_paper_web.py          # 离线交互式网页与原页定位图生成器
│   ├── verify_web_reader.py         # 本地资源、图片、DOM 与清单一致性验收工具
│   ├── validate_dialogue.py          # 环境、PDF、剧本与证据字段严格校验器
│   ├── render_voice_auditions.py     # 不读取 PDF 的文本级声线试听与 SSML 预审
│   ├── render_paper_video.py         # 1080p MP4 合成引擎（红框 + 双语字幕 + TTS）
│   └── verify_video.py               # 分辨率、音视频流、时长与同步验收工具
└── examples/
    ├── sample_paper.pdf             # 示例双页学术论文 PDF（含公式、架构图与消融实验表）
    ├── sample_dialogue.json         # 示例 5 轮男女组会对话与红框坐标配置
    ├── sample_voice_casting.json    # Azure 默认选角、情绪映射与试听台词
    ├── sample_web_brief.json        # 示例网页证据地图与完整视觉清单
    ├── web-reader-demo/             # 可直接打开的离线网页成品
    └── paper_ear_demo.mp4           # 实际渲染生成的 1080p 组会讲解示例视频
```

## 🔎 同类项目调研与设计取舍 (Prior Art & Design Decisions)

网页能力上线前，我们检索了 GitHub 中科学阅读、PDF 结构化、证据问答和长文组织相关项目。以下星标数是 **2026-10-14 的仓库级快照**；大型 Skill 仓库中的单个 Skill 并不等于拥有同样的星标数。

| 项目 | 星标快照 | Paper-Ear 吸收的机制 |
| :--- | ---: | :--- |
| [microsoft/markitdown](https://github.com/microsoft/markitdown) | 190,097 | 广格式转 Markdown 的插件化思路；因版面/视觉保真不足，没有作为图表裁切主链路 |
| [bytedance/deer-flow](https://github.com/bytedance/deer-flow) | 83,836 | 深读全章节、逐条抽取主张与证据、方法/优缺点/局限/追问分层 |
| [opendatalab/MinerU](https://github.com/opendatalab/MinerU) | 81,696 | 稳定页块定位、图片回取和解析层级；作为困难 PDF 的可选增强解析器 |
| [docling-project/docling](https://github.com/docling-project/docling) | 68,841 | 阅读顺序、表格结构、公式和本地执行；作为可选增强解析器 |
| [K-Dense-AI/scientific-agent-skills](https://github.com/K-Dense-AI/scientific-agent-skills) | 48,774 | 主题化综合、证据边界和避免机械逐段复述 |
| [datalab-to/marker](https://github.com/datalab-to/marker) | 40,431 | 图片、结构化表格、LaTeX 公式和 JSON 输出；作为可选增强解析器 |
| [stanford-oval/storm](https://github.com/stanford-oval/storm) | 31,627 | 层级论证结构、多视角问题和降低长文认知负担 |
| [Future-House/paper-qa](https://github.com/Future-House/paper-qa) | 9,364 | 带页码/来源的主张、元数据感知检索和上下文摘要 |

调研结论并不是“再塞七个重依赖”。高星生态主要分成科学 Skill 集合、PDF 布局解析器、引用型研究系统三类，真正高星的单篇论文阅读 Skill 很少。因此本仓库吸收机制但保持默认链路轻量：`pdfplumber + Pillow + Poppler` 即可生成网页；MinerU、Docling、Marker 只在复杂论文需要时选用。

这些项目提供的是设计启发；本仓库没有复制其实现代码。完整来源和取舍见 [`references/web-design-provenance.md`](./references/web-design-provenance.md)。Paper-Ear 保留自己的核心组合：**可搜索证据梳理 + 原像素图表公式 + PDF 原页定位 + 声明类型与证据强度 + 双人组会视频**。

## 📄 开源协议 (License)

本项目基于仓库内的 [MIT License](./LICENSE) 开源，欢迎提交 Issue 与 Pull Request 共同扩展更多组会汇报模板！
