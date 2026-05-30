from __future__ import annotations

"""VoiceCalendar-Pro 应用启动入口。

职责:
- 创建 QApplication 实例
- 配置全局 DPI 缩放
- 初始化主题管理器
- 加载并显示主窗口
"""

import sys

from PyQt6.QtCore import Qt, QCoreApplication
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication

from voicecalendar.core.theme import ThemeManager, ThemeMode
from voicecalendar.core.resources import ResourceLoader
from voicecalendar.ui.main_window import MainWindow


def create_app() -> QApplication:
    """创建并配置 QApplication。"""
    # Qt6 高 DPI 缩放策略 — 必须在 QApplication 创建之前调用
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)

    # 全局调色板 (深色)
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(26, 29, 35))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(232, 234, 237))
    palette.setColor(QPalette.ColorRole.Base, QColor(35, 39, 47))
    palette.setColor(QPalette.ColorRole.Text, QColor(232, 234, 237))
    palette.setColor(QPalette.ColorRole.Button, QColor(35, 39, 47))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(232, 234, 237))
    app.setPalette(palette)

    # 应用名称与组织 (用于 Qt 配置存储)
    app.setApplicationName("VoiceCalendar-Pro")
    app.setOrganizationName("VoiceCalendar")
    app.setDesktopFileName("voicecalendar-pro")

    return app


def main() -> None:
    """应用主入口。"""
    # 创建应用
    app = create_app()

    # 初始化主题 (默认深色)
    theme_mgr = ThemeManager.instance()
    theme_mgr.set_mode(ThemeMode.DARK)

    # 加载基础样式
    loader = ResourceLoader()
    loader.load_base_style()
    loader.load_theme_style("dark")

    # 全局应用样式 (主窗口有自己的样式覆盖)
    dynamic_colors = theme_mgr.get_color_qss()
    combined = loader.get_combined_style(dynamic_colors)
    app.setStyleSheet(combined)

    # 创建并居中显示主窗口
    window = MainWindow()

    # 先隐藏再居中，避免闪烁
    window.hide()
    screen = app.primaryScreen().geometry()
    window_geometry = window.frameGeometry()
    center_point = screen.center()
    window_geometry.moveCenter(center_point)
    window.move(window_geometry.topLeft())

    # 显示并激活窗口 (Windows FramelessWindowHint 必须显式激活)
    window.show()
    window.raise_()
    window.activateWindow()

    # 运行事件循环
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
