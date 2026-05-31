# 🎙️ VoiceCalendar-Pro

> 语音驱动的智能日历桌面应用 —— 用自然语言管理你的日程

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![PyQt6](https://img.shields.io/badge/gui-PyQt6-41cd52.svg)](https://www.riverbankcomputing.com/software/pyqt/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## ✨ 特性

- 🎤 **语音录入** —— 麦克风实时录音 + 音频波形可视化
- 🧠 **AI 理解** —— 基于 LLM 的自然语言意图解析与时间归一化
- 📅 **日历管理** —— 支持 Google Calendar API / ICS 文件导出
- 🎨 **精致 UI** —— 无边框窗口、自定义动画、深色/浅色主题切换
- ⚡ **流畅交互** —— 非阻塞架构、Toast 实时反馈

## 🏗️ 架构

```
┌──────────────────────────────────────────────┐
│                  UI Layer (View)              │
│  ┌──────────┐ ┌──────────┐ ┌──────────────┐  │
│  │ MainWin  │ │Waveform  │ │   Toast      │  │
│  └────┬─────┘ └────┬─────┘ └──────┬───────┘  │
│       │             │              │           │
│  ┌────▼─────────────▼──────────────▼───────┐  │
│  │         ViewModel (Signal/Slot)          │  │
│  └──────────────────┬──────────────────────┘  │
├─────────────────────┼─────────────────────────┤
│                     │                          │
│  ┌──────────────────▼──────────────────────┐  │
│  │              Core Services               │  │
│  │  ┌────────┐ ┌──────┐ ┌──────┐ ┌──────┐ │  │
│  │  │ Audio  │ │ ASR  │ │ NLU  │ │Cal   │ │  │
│  │  └────────┘ └──────┘ └──────┘ └──────┘ │  │
│  └─────────────────────────────────────────┘  │
└──────────────────────────────────────────────┘
```

## 🚀 快速开始

```bash
# 安装依赖
uv sync

# 配置环境变量 (复制 .env.example → .env)
cp .env.example .env

# 启动应用
uv run python app.py
```

## 📁 项目结构

```
VoiceCalendar-Pro/
├── app.py                    # 程序入口
├── pyproject.toml            # 项目配置与依赖
├── voicecalendar/
│   ├── main.py               # 应用启动入口
│   ├── config.py             # 全局配置
│   ├── core/                 # 核心基础设施
│   │   ├── theme.py          # 主题管理系统
│   │   └── resources.py      # 资源加载器
│   ├── ui/                   # UI 层 (View)
│   │   ├── main_window.py    # 主窗口
│   │   ├── titlebar.py       # 自定义标题栏
│   │   ├── components/       # UI 组件
│   │   └── widgets/          # 自定义控件
│   ├── services/             # 业务服务层
│   └── resources/            # 静态资源
│       └── styles/           # QSS 样式表
├── tests/                    # 测试
└── README.md
```

## 🎯 开发计划

| Phase | 内容 | 状态 |
|-------|------|------|
| Phase 0 | 项目初始化与 UI 骨架 | 🚧 进行中 |
| Phase 1 | 核心业务链路 | ⏳ 待开始 |
| Phase 2 | UI 组件与整合 | ⏳ 待开始 |
| Phase 3 | 打磨与交付 | ⏳ 待开始 |

## 🛠️ 技术栈

- **GUI**: PyQt6 + QSS + QPainter
- **ASR**: OpenAI Whisper API
- **LLM**: OpenAI Compatible API
- **日历**: Google Calendar API / ICS
- **构建**: uv + PyInstaller

## 📄 License

MIT License
