<div align="center">

<img src="./assets/hero_banner.jpg" alt="Paper-Ear Hero Banner" width="100%" />

# 🎧 Paper-Ear

### 把枯燥的 PDF 论文变成一场图文并茂的「男女双人组会汇报」MP4 视频
**Turn Academic PDF Papers into Interactive Group-Meeting MP4 Videos with Male-Female Dialogue, Bilingual Subtitles & Dynamic Red-Box Tracking**

[![Agent Skill](https://img.shields.io/badge/Agent_Skill-paper--ear-FF3B30?style=for-the-badge&logo=sparkles&logoColor=white)](#2-方式一作为-agent-skill-交互式调用推荐)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](#1-环境准备-prerequisites)
[![FFmpeg](https://img.shields.io/badge/FFmpeg-1080p_H.264-007808?style=for-the-badge&logo=ffmpeg&logoColor=white)](#3-方式二命令行-cli-独立运行)
[![Edge-TTS](https://img.shields.io/badge/Audio-Neural_Male_%26_Female_TTS-0284C7?style=for-the-badge)](#男女双人语音声线配置-voice-configuration)
[![License: MIT](https://img.shields.io/badge/License-MIT-F59E0B?style=for-the-badge)](https://opensource.org/licenses/MIT)

[**🎬 在线观看演示效果**](#-效果演示与示例视频-live-demo--video-showcase) •
[**🖥️ 画面五大模块拆解**](#️-视频画面五大核心区域拆解-frame-anatomy) •
[**🔄 多轮交互式定制流程**](#-多轮交互式工作流全解-interactive-workflow) •
[**🚀 快速安装与使用**](#-快速安装与使用指南-quick-start) •
[**📐 剧本 JSON 规范**](#-对话与红框配置规范-script-json-schema)

</div>

## 🌟 为什么需要 Paper-Ear？ (Why Paper-Ear?)

读顶会论文（NeurIPS / CVPR / ACL / ICML）时，直接看满篇公式容易犯困，而普通的「AI 文本总结」又脱离了论文原图、原表和具体公式位置。**Paper-Ear** 将单向阅读改造为一场**沉浸式实验室组会**：

| 对比维度 | 传统自己啃 PDF | 普通 AI 文本摘要 | 🎧 **Paper-Ear 组会视频 Skill** |
| :--- | :--- | :--- | :--- |
| **定制化程度** | 从头读到尾，抓不住重点 | 千篇一律的模板式总结 | **多轮交互定制**：先选创新点、专业名词解析深度、目标章节再生成 |
| **讲解形式** | 枯燥默读 | 静态文字或单人机械朗读 | **男女双人组会对话**：女声主讲人步步拆解 + 男声师兄犀利追问思辨 |
| **视觉定位** | 自己在字里行间找图找公式 | 脱离原文排版，图表丢失 | **讲到哪、红框框到哪**：原页面动态红框追踪 + 右侧同步高清放大图 |
| **语言与专业度** | 纯英文阅读门槛高 | 术语翻译生硬 | **中英双语同步字幕** + 右侧实时切换**专业名词与创新点解析卡片** |
| **最终交付物** | 无 | 零散聊天记录 | **直出单个 1080p `.mp4` 高清视频**，随时随地倍速观看或组会分享 |

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

确保系统已安装 `ffmpeg` 与 `poppler`（提供 `pdftoppm` 页面渲染工具），然后安装 Python 依赖：

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

### 3. 方式二：命令行 CLI 独立运行

你也可以直接在本地终端调用 `scripts/` 下的两个核心脚本：

```bash
# Step 1: 解析 PDF 页面结构、段落/图表归一化坐标 [x0, y0, x1, y1]，并导出页面预览图
python3 scripts/inspect_paper.py \
  --pdf examples/sample_paper.pdf \
  --out /tmp/paper_structure.json \
  --render-dir /tmp/paper_pages \
  --dpi 150

# Step 2: 根据对话与红框脚本渲染输出 1080p MP4 视频（可选同时导出 README 动图预览）
python3 scripts/render_paper_video.py \
  --pdf examples/sample_paper.pdf \
  --script examples/sample_dialogue.json \
  --output examples/paper_ear_demo.mp4 \
  --dpi 180 \
  --export-gif assets/demo_preview.gif
```

## 🎙️ 男女双人语音声线配置 (Voice Configuration)

在联网环境下，`scripts/render_paper_video.py` 默认调用微软 `edge-tts` 高自然度神经网络中英双语声线（天然支持中文句子里夹杂英文专业术语）；在无网隔离环境下则自动无缝切换为离线节拍音频合成。你可以在 `dialogue_script.json` 顶层自由替换喜欢的男女声线组合：

| 角色定位 | JSON 字段 | 默认推荐声线 | 备选高表现力声线 | 声音风格特点 |
| :--- | :--- | :--- | :--- | :--- |
| **女声主讲人 (Presenter)** | `"female_voice"` | `zh-CN-XiaoxiaoNeural` | `zh-CN-XiaoyiNeural` / `en-US-JennyNeural` | 清晰自然、学术汇报感强、中英混读流畅 |
| **男声提问者 (Discussant)** | `"male_voice"` | `zh-CN-YunxiNeural` | `zh-CN-YunjianNeural` / `en-US-GuyNeural` | 富有思辨感与追问张力，适合扮演师兄/导师角色 |

## 📐 对话与红框配置规范 (Script JSON Schema)

`render_paper_video.py` 接收的 `dialogue_script.json` 结构清晰直观，支持**显式归一化坐标 `red_box`** 与**关键词自动坐标匹配 `search_text`** 双重定位：

```json
{
  "title": "Sparse-Ear: Dynamic Token Routing for Long-Context Reasoning",
  "male_name": "师兄 Alex (提问/思辨)",
  "female_name": "主讲人 Lin (精读讲解)",
  "male_voice": "zh-CN-YunxiNeural",
  "female_voice": "zh-CN-XiaoxiaoNeural",
  "turns": [
    {
      "page": 1,
      "section_tag": "Page 1 • Abstract & Motivation",
      "speaker": "female",
      "zh_text": "大家好！今天组会我们精读这篇 Sparse-Ear 论文。先看红框里的摘要，它主要解决长序列下自注意力 O(N²) 复杂度痛点。",
      "en_text": "Hi everyone! Today we're presenting Sparse-Ear. Looking at the highlighted Abstract, it tackles the O(N^2) complexity bottleneck.",
      "search_text": "Abstract",
      "red_box": [0.09, 0.165, 0.91, 0.325],
      "box_label": "Abstract / 核心痛点与动机",
      "card_title": "核心动机与背景 (Motivation)",
      "notes": [
        "传统 Transformer 在 128K 长文本下显存与计算开销呈二次方暴涨",
        "本文提出动态稀疏路由 (Dynamic Token Routing)，兼顾速度与跨段落推理精度"
      ]
    }
  ]
}
```

## 📂 仓库目录结构 (Repository Layout)

```text
paper-ear/
├── SKILL.md                         # Agent Skill 核心定义与多轮交互指令
├── README.md                        # 项目主页文档（含视觉预览、架构图与使用说明）
├── requirements.txt                 # Python 依赖包列表
├── push_to_github.sh                # macOS / Linux 一键推送至 GitHub 脚本
├── push_to_github.bat               # Windows 一键推送至 GitHub 脚本
├── assets/
│   ├── hero_banner.jpg              # 项目顶部视觉横幅海报
│   ├── demo_preview.gif             # 5 轮红框追踪与男女对话动态预览 GIF
│   ├── frame_anatomy.png            # 视频画面五大核心区域拆解标注图
│   └── workflow_diagram.png         # 多轮交互式工作流与系统架构图
├── scripts/
│   ├── inspect_paper.py             # PDF 页面尺寸、文本块/图表归一化坐标提取工具
│   └── render_paper_video.py        # 1080p MP4 视频合成引擎（红框追踪 + 双语字幕 + TTS）
└── examples/
    ├── sample_paper.pdf             # 示例双页学术论文 PDF（含公式、架构图与消融实验表）
    ├── sample_dialogue.json         # 示例 5 轮男女组会对话与红框坐标配置
    └── paper_ear_demo.mp4           # 实际渲染生成的 1080p 组会讲解示例视频
```

## 📄 开源协议 (License)

本项目基于 [MIT License](https://opensource.org/licenses/MIT) 开源，欢迎提交 Issue 与 Pull Request 共同扩展更多组会汇报模板！
