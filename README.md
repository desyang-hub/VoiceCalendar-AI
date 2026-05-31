# 🎙️ VoiceCalendar-Pro

> 语音驱动的智能日历桌面应用 —— 用自然语言管理你的日程

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)
[![PyQt6](https://img.shields.io/badge/gui-PyQt6%206.8-41cd52.svg)](https://www.riverbankcomputing.com/software/pyqt/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://img.shields.io/badge/tests-58%20passed-brightgreen.svg)](tests/)

一个基于 **PyQt6** 的高品质语音日历桌面应用，通过自然语言交互管理日程。

```
用户："明天下午三点开会"  →  🎤 录音  →  🧠 识别  →  📅 自动创建日程
用户："今天有什么安排"    →  🎤 录音  →  🔍 查询  →  📋 列出今日日程
```

---

## ✨ 核心特性

### 🎤 语音交互
- **实时录音** — 麦克风捕获，WAV 格式输出，支持 16kHz/16-bit 单声道
- **波形可视化** — 自定义 QPainter 绘制实时音频波形，支持柱状频谱/平滑波形两种模式
- **空闲呼吸动画** — 待机状态下微弱的正弦呼吸波，录音时切换为 RMS 驱动

### 🧠 AI 驱动
- **ASR 语音识别** — OpenAI Whisper API，支持中英文混合识别
- **LLM 意图解析** — GPT-4o 理解自然语言指令，输出结构化 JSON
- **快速时间解析** — 离线 Fallback，支持 "明天"、"下周一"、"下午三点半" 等中文时间表达
- **优雅降级** — LLM 不可用时自动切换到快速解析器

### 📅 日历管理
- **日程 CRUD** — 添加、查询、删除日程事件
- **ICS 导出** — 标准 .ics 文件生成，兼容 Google Calendar、Outlook、Apple Calendar
- **日程提醒** — 支持 DISPLAY 类型提醒
- **重复事件** — daily/weekly/monthly/yearly 支持

### 🎨 精致 UI
- **无边框窗口** — 自定义标题栏，支持拖拽、最小化、最大化、关闭
- **深色/浅色主题** — 一键切换，颜色变量集中管理
- **动画系统** — 所有状态切换带过渡动画，Toast 通知滑入滑出
- **侧边栏导航** — 72px 紧凑图标导航，选中态高亮
- **Toast 通知** — 非模态通知，支持 4 种类型（success/error/warning/info）

### 🛡️ 健壮性
- **集中式错误处理** — 8 种错误类型层次结构，用户友好提示
- **自动重试** — 网络错误指数退避重试（最多 3 次）
- **API 限流** — 令牌桶限流器，避免触发服务端限流
- **全局异常捕获** — 未捕获异常不导致崩溃，自动记录日志

---

## 🏗️ 架构设计

### 数据流

```
┌─────────────────────────────────────────────────────────────┐
│                        UI Layer (View)                       │
│                                                              │
│  ┌───────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │MainWindow │  │ Waveform     │  │ ToastManager         │  │
│  │TitleBar   │  │ StatusInd.   │  │ EventCard (动画)     │  │
│  │Sidebar    │  │ RecordButton │  │ SkeletonShimmer      │  │
│  └─────┬─────┘  └──────┬───────┘  └──────────┬───────────┘  │
│        │               │                      │              │
│  ┌─────▼────────────────▼──────────────────────▼──────────┐  │
│  │              Pipeline (ViewModel)                       │  │
│  │         Signal/Slot + QThread 通信                       │  │
│  └──────────────────────┬─────────────────────────────────┘  │
├─────────────────────────┼───────────────────────────────────┤
│                         │                                    │
│  ┌──────────────────────▼─────────────────────────────────┐  │
│  │                   Core Services                         │  │
│  │                                                         │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐ │  │
│  │  │ Audio    │→ │ ASR      │→ │ NLU      │→ │ Cal    │ │  │
│  │  │ Capture  │  │ Whisper  │  │ GPT-4o   │  │ ICS    │ │  │
│  │  └──────────┘  └──────────┘  └──────────┘  └────────┘ │  │
│  │                                                         │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐              │  │
│  │  │ RateLimiter│ │ Retry    │  │ Error    │              │  │
│  │  │ (令牌桶)  │  │ (指数退避)│  │ Handler  │              │  │
│  │  └──────────┘  └──────────┘  └──────────┘              │  │
│  └─────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 设计原则

| 原则 | 实现方式 |
|------|----------|
| **MVC/MVVM** | UI (View) 与 Services (Model) 完全分离，Pipeline 充当 ViewModel |
| **线程安全** | 所有耗时操作在 QThread 中执行，通过 Signal/Slot 与 UI 通信 |
| **类型安全** | 全部 Type Hints，Pydantic 数据模型，Signal 声明参数类型 |
| **可扩展** | QSS 样式独立文件，主题系统支持热切换，插件化服务设计 |

---

## 🚀 快速开始

### 环境要求

- **Python** >= 3.9
- **操作系统**: Windows 10+ / macOS 11+ / Ubuntu 20.04+
- **麦克风**: 用于语音录入（可选，可手动输入文本）

### 安装

```bash
# 1. 克隆项目
git clone https://github.com/yourname/VoiceCalendar-Pro.git
cd VoiceCalendar-Pro

# 2. 安装依赖（使用 uv，推荐）
uv sync

# 或使用 pip
pip install -e .
```

### 配置

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件，填入 API Key：
#   OPENAI_API_KEY=sk-xxx
#   OPENAI_BASE_URL=https://api.openapi.com/v1
#   WHISPER_MODEL=whisper-1
#   LLM_MODEL=gpt-4o
```

### 启动

```bash
# 开发模式
uv run python -m voicecalendar

# 或使用入口命令
uv run voicecalendar
```

### 无 API Key 运行

应用支持 **Mock 模式**运行，无需 API Key，使用模拟数据演示完整流程：

```bash
# 不设置 OPENAI_API_KEY 即可启动 Mock 模式
uv run python -m voicecalendar
```

---

## 📁 项目结构

```
VoiceCalendar-Pro/
├── pyproject.toml              # 项目配置、依赖、构建脚本
├── .env.example                # 环境变量模板
├── .gitignore
├── README.md
│
├── voicecalendar/              # 主应用包
│   ├── __init__.py
│   ├── main.py                 # 应用入口（DPI 配置、主题初始化、异常处理）
│   ├── config.py               # 全局配置（窗口/颜色/动画/音频/API）
│   │
│   ├── core/                   # 核心基础设施
│   │   ├── __init__.py
│   │   ├── theme.py            # 主题管理器（深色/浅色切换 + Signal）
│   │   └── resources.py        # QSS 资源加载器
│   │
│   ├── ui/                     # UI 层 (View)
│   │   ├── __init__.py
│   │   ├── main_window.py      # 主窗口 + 录音按钮 + 事件卡片
│   │   ├── titlebar.py         # 自定义标题栏（拖拽、按钮）
│   │   ├── components/
│   │   │   └── toast.py        # Toast 通知管理器
│   │   └── widgets/
│   │       ├── waveform.py     # 波形可视化 + 状态指示器
│   │       ├── skeleton.py     # 加载骨架屏 + 圆形进度
│   │       └── base_widget.py  # 基础圆角 Widget
│   │
│   ├── services/               # 业务服务层 (Model)
│   │   ├── __init__.py
│   │   ├── pipeline.py         # 处理流水线（串联所有服务）
│   │   ├── audio_capture.py    # 麦克风录音 + WAV 输出
│   │   ├── asr_service.py      # Whisper API 语音识别
│   │   ├── nlu_parser.py       # LLM 意图解析 + 快速时间解析
│   │   ├── calendar_backend.py # ICS 日历后端
│   │   └── errors.py           # 集中式错误处理
│   │
│   ├── models/                 # 数据模型
│   │   ├── __init__.py
│   │   └── event.py            # CalendarEvent + ParseIntent (Pydantic)
│   │
│   └── resources/              # 静态资源
│       └── styles/
│           ├── base.qss        # 基础样式（滚动条、字体）
│           ├── dark.qss        # 深色主题
│           └── light.qss       # 浅色主题
│
└── tests/                      # 测试套件
    ├── test_config.py          # 配置模块测试 (6 tests)
    ├── test_models.py          # 数据模型测试 (6 tests)
    ├── test_services.py        # 服务链路测试 (23 tests)
    └── test_errors.py          # 错误处理测试 (23 tests)
```

---

## 🎨 UI 设计

### 布局结构

```
┌─────────────────────────────────────────────────────┐
│  ☰  VoiceCalendar Pro              ─  □  ✕          │  ← 自定义标题栏
├────┬────────────────────────────────────────────────┤
│    │                                                 │
│ 🎙 │   ┌───────────────────────────────────────┐    │
│ 📅 │   │  ● 正在录音...                         │    │  ← 状态指示器
│ 🎙 │   │                                       │    │
│ ⚙  │   │  ▂▅▆▇  ┃ ┃  ▁  ▂▃▄▅▆▇  (波形)        │    │  ← 波形可视化
│    │   │                                       │    │
│    │   │         ⏺ (录音按钮)                  │    │  ← 录音交互
│    │   └───────────────────────────────────────┘    │
│    │                                                 │
│    │   🔍 今日日程  2025/05/30                       │  ← 日程标题
│    │   ┌───────────────────────────────────────┐    │
│    │   │ ▎ 09:00  │  团队晨会              05/30 │    │  ← 事件卡片
│    │   ├───────────────────────────────────────┤    │
│    │   │ ▎ 14:00  │  产品评审               05/30 │    │
│    │   │                                   (可滚动) │    │
│    │   └───────────────────────────────────────┘    │
│    │                                                 │
└────┴────────────────────────────────────────────────┘
  72px
```

### 主题系统

| 组件 | 深色主题 | 浅色主题 |
|------|---------|---------|
| 背景 | `#1A1D23` | `#FFFFFF` |
| 侧边栏 | `#1E222A` | `#F7F8FA` |
| 卡片 | `#23272F` | `#F7F8FA` |
| 强调色 | `#6B8AFF` | `#4A6CF7` |
| 成功 | `#3DDC84` | `#34C759` |
| 错误 | `#FF6B6B` | `#FF3B30` |

---

## 🧠 Prompt 设计

### 系统提示词

LLM 意图解析使用精心设计的系统提示词，引导模型输出结构化 JSON：

```json
{
    "action": "add|query|delete|list",
    "event": {
        "title": "事件标题",
        "start_date": "YYYY-MM-DD",
        "start_time": "HH:MM",
        "end_time": "HH:MM",
        "recurrence": "none|daily|weekly|monthly"
    },
    "confidence": 0.95
}
```

### 时间归一化

支持以下中文时间表达（无需 LLM，离线解析）：

| 表达 | 解析结果 |
|------|---------|
| "今天" / "今日" | 当天日期 |
| "明天" / "明日" | 明天日期 |
| "后天" | 后天日期 |
| "下周一" ~ "下周日" | 下周对应星期 |
| "本周三" | 本周对应星期 |
| "三天后" / "十天后" | 相对日期 |
| "下午三点" | 15:00 |
| "早上九点半" | 09:30 |
| "14:30" | 14:30 |

---

## 🧪 测试

```bash
# 运行全部测试
PYTHONPATH=. pytest tests/ -v

# 运行特定测试文件
PYTHONPATH=. pytest tests/test_errors.py -v

# 带覆盖率报告
PYTHONPATH=. pytest tests/ --cov=voicecalendar --cov-report=html
```

### 测试覆盖

| 模块 | 测试数 | 覆盖范围 |
|------|--------|---------|
| Config | 6 | 配置数据类默认值验证 |
| Models | 6 | 事件创建、默认结束时间、循环、意图识别 |
| Services | 23 | 时间解析、ASR、NLU、日历 CRUD、Pipeline |
| Errors | 23 | 错误类型、用户提示、重试、限流、HTTP 解析 |
| **总计** | **58** | 全部通过 ✓ |

---

## 🔧 构建与部署

### 构建可执行文件

```bash
# Windows
.\build.ps1

# macOS / Linux
chmod +x build.sh
./build.sh
```

构建产物位于 `dist/` 目录。

### PyInstaller 配置

```python
# pyinstaller.spec
a = Analysis(
    ['voicecalendar/main.py'],
    hiddenimports=[
        'PyQt6',
        'PyQt6.QtWidgets',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
    ],
)
```

---

## 📖 API 参考

### 快速使用 Pipeline

```python
from voicecalendar.services.pipeline import VoiceCalendarPipeline

# 初始化
pipeline = VoiceCalendarPipeline(
    api_key="sk-xxx",
    base_url="https://api.openai.com/v1",
)

# 处理语音指令
result = pipeline.process_voice(text="明天下午三点开会")

if result.success and result.intent.is_add:
    print(f"日程已添加: {result.intent.event.title}")

# 查询今天日程
events = pipeline.list_today()
for event in events:
    print(f"{event.start_time}: {event.title}")
```

### 错误处理

```python
from voicecalendar.services.errors import (
    get_user_message,
    NetworkError,
    ASRError,
)

try:
    result = pipeline.process_voice(text="...")
except (NetworkError, ASRError) as e:
    # 获取用户友好的错误提示
    print(get_user_message(e))  # "网络连接失败，请检查网络后重试"
```

---

## 🎯 开发计划

| Phase | 内容 | 状态 |
|-------|------|------|
| Phase 0 | 项目初始化与 UI 骨架 | ✅ 完成 |
| Phase 1 | 核心业务链路 (Audio/ASR/NLU/Calendar) | ✅ 完成 |
| Phase 2 | UI 组件与整合 | ✅ 完成 |
| Phase 3 | 动画打磨 | ✅ 完成 |
| Phase 3 | 错误处理 | ✅ 完成 |
| Phase 3 | 文档与构建脚本 | ✅ 完成 |

---

## 🛠️ 技术栈

| 类别 | 技术 |
|------|------|
| **GUI 框架** | PyQt6 6.8+ (Qt 6.8+) |
| **样式** | QSS + QPainter 自定义绘制 |
| **语音识别** | OpenAI Whisper API |
| **意图解析** | OpenAI GPT-4o Compatible API |
| **日历** | ics (Python ICS Library) |
| **数据模型** | Pydantic |
| **依赖管理** | uv / pip |
| **测试** | pytest |
| **代码质量** | black, ruff, mypy |
| **打包** | PyInstaller |

---

## 📝 许可

MIT License

---

## 🙏 致谢

- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) — 优秀的 Python GUI 框架
- [OpenAI Whisper](https://openai.com/index/whisper/) — 精准的多语言语音识别
- [ics](https://github.com/coleifer/ics) — Python ICS 日历库
- 七牛云暑期实训营
