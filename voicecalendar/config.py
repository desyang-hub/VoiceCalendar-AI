from __future__ import annotations

"""全局配置：窗口尺寸、颜色变量、动画参数、API 默认值。

所有硬编码的魔法数字都应集中在此模块中维护。
"""

from dataclasses import dataclass
from pathlib import Path

# ─────────────────────────────────────────────
# 路径配置
# ─────────────────────────────────────────────

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
RESOURCES_DIR: Path = Path(__file__).resolve().parent / "resources"
STYLES_DIR: Path = RESOURCES_DIR / "styles"
ICONS_DIR: Path = RESOURCES_DIR / "icons"

# ─────────────────────────────────────────────
# 窗口配置
# ─────────────────────────────────────────────


@dataclass(frozen=True)
class WindowConfig:
    """主窗口尺寸与行为参数。"""

    # 默认尺寸 (推荐比例 16:10，适配主流分辨率)
    DEFAULT_WIDTH: int = 1000
    DEFAULT_HEIGHT: int = 700
    MIN_WIDTH: int = 800
    MIN_HEIGHT: int = 550

    # 圆角半径
    CORNER_RADIUS: int = 16

    # 标题栏高度
    TITLEBAR_HEIGHT: int = 40

    # 窗口阴影偏移
    SHADOW_OFFSET_X: int = 0
    SHADOW_OFFSET_Y: int = 4

    # 窗口动画
    WINDOW_OPEN_DURATION: int = 300  # ms
    WINDOW_CLOSE_DURATION: int = 200  # ms


# ─────────────────────────────────────────────
# 主题颜色 (CSS 变量风格集中管理)
# ─────────────────────────────────────────────


@dataclass(frozen=True)
class LightThemeColors:
    """浅色主题配色方案。"""

    # 背景层级
    BG_PRIMARY: str = "#FFFFFF"
    BG_SECONDARY: str = "#F7F8FA"
    BG_TERTIARY: str = "#EEF0F4"
    BG_HOVER: str = "#E8EAEE"

    # 文字
    TEXT_PRIMARY: str = "#1A1D23"
    TEXT_SECONDARY: str = "#5F6B7A"
    TEXT_TERTIARY: str = "#8B95A2"
    TEXT_INVERSE: str = "#FFFFFF"

    # 强调色
    ACCENT_PRIMARY: str = "#4A6CF7"
    ACCENT_SECONDARY: str = "#6B8AFF"
    ACCENT_HOVER: str = "#3B5DE7"

    # 功能色
    SUCCESS: str = "#34C759"
    WARNING: str = "#FF9500"
    ERROR: str = "#FF3B30"
    INFO: str = "#5AC8FA"

    # 分割线
    BORDER_LIGHT: str = "#E5E7EB"
    BORDER_MEDIUM: str = "#D1D5DB"

    # 阴影
    SHADOW_COLOR: str = "rgba(0, 0, 0, 0.12)"

    # 标题栏
    TITLEBAR_BG: str = "#F7F8FA"
    TITLEBAR_BORDER: str = "#EEF0F4"

    # 录音按钮
    RECORD_IDLE: str = "#4A6CF7"
    RECORD_ACTIVE: str = "#FF3B30"
    RECORD_PULSE: str = "rgba(255, 59, 48, 0.3)"


@dataclass(frozen=True)
class DarkThemeColors:
    """深色主题配色方案。"""

    # 背景层级
    BG_PRIMARY: str = "#1A1D23"
    BG_SECONDARY: str = "#23272F"
    BG_TERTIARY: str = "#2D323C"
    BG_HOVER: str = "#363C47"

    # 文字
    TEXT_PRIMARY: str = "#E8EAED"
    TEXT_SECONDARY: str = "#9AA0A8"
    TEXT_TERTIARY: str = "#6B7280"
    TEXT_INVERSE: str = "#FFFFFF"

    # 强调色
    ACCENT_PRIMARY: str = "#6B8AFF"
    ACCENT_SECONDARY: str = "#8DA4FF"
    ACCENT_HOVER: str = "#4A6CF7"

    # 功能色
    SUCCESS: str = "#3DDC84"
    WARNING: str = "#FFB340"
    ERROR: str = "#FF6B6B"
    INFO: str = "#7DD3FC"

    # 分割线
    BORDER_LIGHT: str = "#363C47"
    BORDER_MEDIUM: str = "#4B5360"

    # 阴影
    SHADOW_COLOR: str = "rgba(0, 0, 0, 0.4)"

    # 标题栏
    TITLEBAR_BG: str = "#23272F"
    TITLEBAR_BORDER: str = "#2D323C"

    # 录音按钮
    RECORD_IDLE: str = "#6B8AFF"
    RECORD_ACTIVE: str = "#FF6B6B"
    RECORD_PULSE: str = "rgba(255, 107, 107, 0.3)"


# ─────────────────────────────────────────────
# 动画配置
# ─────────────────────────────────────────────


@dataclass(frozen=True)
class AnimationConfig:
    """动画时长与缓动曲线参数。"""

    # 时长 (ms)
    FAST: int = 100
    NORMAL: int = 200
    SLOW: int = 300
    VERY_SLOW: int = 500

    # Toast
    TOAST_APPEAR: int = 250
    TOAST_DURATION: int = 3000  # 停留时间
    TOAST_DISAPPEAR: int = 200

    # 按钮
    BUTTON_HOVER: int = 120
    BUTTON_PRESS: int = 60

    # 录音按钮脉冲
    RECORD_PULSE_DURATION: int = 1000


# ─────────────────────────────────────────────
# Toast 配置
# ─────────────────────────────────────────────


@dataclass(frozen=True)
class ToastConfig:
    """Toast 通知样式参数。"""

    MAX_VISIBLE: int = 3  # 同时最多显示的 Toast 数量
    SPACING: int = 12  # Toast 之间的间距
    OFFSET_RIGHT: int = 20  # 距右侧距离
    OFFSET_TOP: int = 60  # 距顶部距离
    WIDTH: int = 300
    HEIGHT: int = 48
    CORNER_RADIUS: int = 10


# ─────────────────────────────────────────────
# API 配置 (通过环境变量覆盖)
# ─────────────────────────────────────────────


@dataclass
class APIConfig:
    """API 服务默认配置。"""

    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    whisper_model: str = "whisper-1"
    llm_model: str = "gpt-4o"
    request_timeout: int = 30  # seconds

    @classmethod
    def from_env(cls) -> APIConfig:
        """从环境变量加载配置。"""
        import os

        return cls(
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            whisper_model=os.getenv("WHISPER_MODEL", "whisper-1"),
            llm_model=os.getenv("LLM_MODEL", "gpt-4o"),
            request_timeout=int(os.getenv("REQUEST_TIMEOUT", "30")),
        )


# ─────────────────────────────────────────────
# 音频配置
# ─────────────────────────────────────────────


@dataclass(frozen=True)
class AudioConfig:
    """音频录制参数。"""

    SAMPLE_RATE: int = 16000  # Whisper 要求
    CHANNELS: int = 1  # 单声道
    SAMPLE_WIDTH: int = 2  # 16-bit
    CHUNK_SIZE: int = 1024


# ─────────────────────────────────────────────
# 便捷访问
# ─────────────────────────────────────────────

window = WindowConfig()
animation = AnimationConfig()
toast = ToastConfig()
audio = AudioConfig()
light_colors = LightThemeColors()
dark_colors = DarkThemeColors()
