"""主题管理系统：深色/浅色主题切换与 QSS 变量注入。

设计理念：
- 所有颜色变量集中定义在 config.py 中
- 本模块负责将 config 中的颜色映射为 QSS 中的自定义属性
- 支持运行时动态切换，通过 Signal 通知 UI 层更新
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, pyqtSignal

from voicecalendar.config import DarkThemeColors, LightThemeColors, dark_colors, light_colors

if TYPE_CHECKING:
    pass


class ThemeMode(Enum):
    """主题模式枚举。"""

    LIGHT = "light"
    DARK = "dark"


class ThemeManager(QObject):
    """全局主题管理器 (单例模式)。

    Signal:
        theme_changed: 主题切换时发出，携带新的 ThemeMode
    """

    theme_changed: pyqtSignal = pyqtSignal(ThemeMode)

    _instance: ThemeManager | None = None

    def __init__(self, parent: object | None = None) -> None:
        super().__init__(parent)
        self._current_mode: ThemeMode = ThemeMode.DARK
        self._colors: LightThemeColors | DarkThemeColors = dark_colors

    @classmethod
    def instance(cls) -> ThemeManager:
        """获取单例实例。"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def current_mode(self) -> ThemeMode:
        return self._current_mode

    @property
    def colors(self) -> LightThemeColors | DarkThemeColors:
        return self._colors

    def set_mode(self, mode: ThemeMode) -> None:
        """切换主题模式。"""
        if mode == self._current_mode:
            return

        self._current_mode = mode
        self._colors = dark_colors if mode == ThemeMode.DARK else light_colors
        self.theme_changed.emit(mode)

    def toggle(self) -> None:
        """在深色/浅色之间切换。"""
        new_mode = ThemeMode.LIGHT if self._current_mode == ThemeMode.DARK else ThemeMode.DARK
        self.set_mode(new_mode)

    def is_dark(self) -> bool:
        return self._current_mode == ThemeMode.DARK

    def is_light(self) -> bool:
        return self._current_mode == ThemeMode.LIGHT

    def get_color_qss(self) -> str:
        """将当前主题颜色导出为 QSS 自定义属性块。

        返回形如:
            * {
                qproperty-bgPrimary: "#FFFFFF";
                qproperty-textPrimary: "#1A1D23";
                ...
            }
        """

        def _attr(name: str, value: str) -> str:
            return f"    {name}: {value};"

        lines = [
            "/* ── Dynamic Theme Colors ── */",
            "[ThemeColors] {",
            _attr("bg-primary", self._colors.BG_PRIMARY),
            _attr("bg-secondary", self._colors.BG_SECONDARY),
            _attr("bg-tertiary", self._colors.BG_TERTIARY),
            _attr("bg-hover", self._colors.BG_HOVER),
            _attr("text-primary", self._colors.TEXT_PRIMARY),
            _attr("text-secondary", self._colors.TEXT_SECONDARY),
            _attr("text-tertiary", self._colors.TEXT_TERTIARY),
            _attr("text-inverse", self._colors.TEXT_INVERSE),
            _attr("accent-primary", self._colors.ACCENT_PRIMARY),
            _attr("accent-secondary", self._colors.ACCENT_SECONDARY),
            _attr("accent-hover", self._colors.ACCENT_HOVER),
            _attr("success", self._colors.SUCCESS),
            _attr("warning", self._colors.WARNING),
            _attr("error", self._colors.ERROR),
            _attr("info", self._colors.INFO),
            _attr("border-light", self._colors.BORDER_LIGHT),
            _attr("border-medium", self._colors.BORDER_MEDIUM),
            _attr("shadow-color", self._colors.SHADOW_COLOR),
            _attr("titlebar-bg", self._colors.TITLEBAR_BG),
            _attr("titlebar-border", self._colors.TITLEBAR_BORDER),
            _attr("record-idle", self._colors.RECORD_IDLE),
            _attr("record-active", self._colors.RECORD_ACTIVE),
            _attr("record-pulse", self._colors.RECORD_PULSE),
            "}",
        ]
        return "\n".join(lines)
