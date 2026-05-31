from __future__ import annotations

"""资源加载器：QSS 样式表加载与动态注入。

职责:
- 从 resources/styles/ 目录加载 .qss 文件
- 合并基础样式 + 主题样式 + 动态颜色变量
- 提供 apply_style(widget) 方法一键应用样式
"""

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QApplication

from voicecalendar.config import STYLES_DIR

if TYPE_CHECKING:
    pass


class ResourceLoader:
    """资源加载器 (负责 QSS 样式管理)。"""

    def __init__(self) -> None:
        self._base_qss: str = ""
        self._theme_qss: str = ""
        self._cached_combined: str = ""

    def load_base_style(self) -> None:
        """加载基础样式表 (不随主题变化)。"""
        base_path = STYLES_DIR / "base.qss"
        if base_path.exists():
            self._base_qss = base_path.read_text(encoding="utf-8")
        else:
            self._base_qss = self._default_base_style()

    def load_theme_style(self, theme: str = "dark") -> None:
        """加载指定主题的样式表。

        Args:
            theme: 'light' 或 'dark'
        """
        theme_path = STYLES_DIR / f"{theme}.qss"
        if theme_path.exists():
            self._theme_qss = theme_path.read_text(encoding="utf-8")
        else:
            self._theme_qss = ""

    def get_combined_style(self, dynamic_colors: str = "") -> str:
        """获取合并后的完整样式表。

        Args:
            dynamic_colors: 由 ThemeManager.get_color_qss() 生成的动态颜色块
        """
        combined = f"{self._base_qss}\n\n{self._theme_qss}\n\n{dynamic_colors}"

        if combined != self._cached_combined:
            self._cached_combined = combined
        return self._cached_combined

    def apply_to_app(self, dynamic_colors: str = "") -> None:
        """将合并后的样式表应用到全局 QApplication。"""
        style = self.get_combined_style(dynamic_colors)
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(style)

    @staticmethod
    def _default_base_style() -> str:
        """内建默认基础样式 (当 base.qss 不存在时的兜底)。"""
        return """
/* ═══════════════════════════════════════════
   VoiceCalendar-Pro — 基础样式表
   ═══════════════════════════════════════════ */

/* 全局字体与背景 */
QWidget {
    font-family: "Segoe UI", "Microsoft YaHei UI", "PingFang SC", sans-serif;
    font-size: 14px;
    color: #E8EAED;
    background-color: #1A1D23;
}

/* 消除焦点边框 */
QWidget:focus {
    outline: none;
}

/* 滚动条 — 轨道 */
QScrollBar:vertical {
    border: none;
    background: transparent;
    width: 8px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: rgba(255, 255, 255, 0.15);
    border-radius: 4px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background: rgba(255, 255, 255, 0.25);
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {
    background: none;
    height: 0px;
}

/* 滚动条 — 水平 */
QScrollBar:horizontal {
    border: none;
    background: transparent;
    height: 8px;
    margin: 0px;
}

QScrollBar::handle:horizontal {
    background: rgba(255, 255, 255, 0.15);
    border-radius: 4px;
    min-width: 30px;
}

QScrollBar::handle:horizontal:hover {
    background: rgba(255, 255, 255, 0.25);
}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal,
QScrollBar::sub-page:horizontal {
    background: none;
    width: 0px;
}
"""
