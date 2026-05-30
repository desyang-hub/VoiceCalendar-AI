from __future__ import annotations

"""VoiceCalendar-Pro 应用启动入口。

职责:
- 创建 QApplication 实例
- 配置全局 DPI 缩放
- 初始化主题管理器
- 加载并显示主窗口
"""

import logging
import sys
import traceback
from pathlib import Path


def _load_dotenv() -> None:
    """加载 .env 文件到环境变量。"""
    try:
        from dotenv import load_dotenv

        # 尝试从项目根目录加载 .env
        project_root = Path(__file__).resolve().parent.parent
        env_file = project_root / ".env"
        if env_file.exists():
            load_dotenv(env_file)
    except ImportError:
        pass  # python-dotenv 未安装，忽略


def _install_stderr_filter() -> None:
    """安装 Qt 消息处理器，过滤 Windows DWM 无关警告。

    Windows 上绘制带透明度的窗口时 DWM 会输出
    UpdateLayeredWindowIndirect failed 警告，不影响功能。
    使用 Qt 自带的消息处理器拦截，而非 Python stderr 包装器。
    """
    from PyQt6.QtCore import qInstallMessageHandler, QtMsgType

    def _qt_msg_handler(msg_type, context, message):
        """Qt 消息处理器 — 过滤系统级无关警告。"""
        msg = str(message)
        # 过滤 Windows DWM 警告 和 Qt 跨线程 timer 警告
        if "UpdateLayeredWindowIndirect" in msg or "Timers cannot be" in msg:
            return
        # 保留 Qt 警告/错误
        if msg_type in (QtMsgType.QtWarningMsg, QtMsgType.QtCriticalMsg):
            logger.warning("Qt: %s", msg)

    qInstallMessageHandler(_qt_msg_handler)

from PyQt6.QtCore import Qt, QCoreApplication
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication, QMessageBox

from voicecalendar.core.theme import ThemeManager, ThemeMode
from voicecalendar.core.resources import ResourceLoader
from voicecalendar.ui.main_window import MainWindow

# ── 全局日志配置 ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("voicecalendar")


class GlobalExceptionHandler:
    """全局异常处理器 — 防止未捕获异常导致应用崩溃。"""

    def __init__(self) -> None:
        # 安装 Python 级别异常钩子
        sys.excepthook = self._handle_exception

    def _handle_exception(
        self,
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_traceback,
    ) -> None:
        """处理未捕获的 Python 异常。"""
        error_msg = "".join(
            traceback.format_exception(exc_type, exc_value, exc_traceback)
        )
        logger.error("未捕获的异常:\\n%s", error_msg)

        # 在 UI 中显示错误提示（不阻塞）
        try:
            app = QApplication.instance()
            if app is not None:
                QMessageBox.critical(  # type: ignore[attr-defined]
                    None,
                    "VoiceCalendar 错误",
                    f"发生未预期的错误:\\n\\n{exc_value}\\n\\n详细信息已记录到日志。",
                )
        except Exception:
            pass  # 即使在错误处理器中也避免崩溃


def install_exception_handler() -> None:
    """安装全局异常处理器。"""
    GlobalExceptionHandler()


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
    # 加载 .env 文件到环境变量（必须在最前面，其他模块可能读取环境变量）
    _load_dotenv()

    # 安装 Qt 消息过滤器，抑制 Windows DWM 无关警告
    _install_stderr_filter()

    # 安装全局异常处理器
    install_exception_handler()
    logger.info("VoiceCalendar-Pro 启动")

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

    # 创建并显示主窗口
    window = MainWindow()
    window.show()

    # 居中显示
    screen = app.primaryScreen().geometry()
    window_geometry = window.frameGeometry()
    center_point = screen.center()
    window_geometry.moveCenter(center_point)
    window.move(window_geometry.topLeft())

    # 运行事件循环
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
