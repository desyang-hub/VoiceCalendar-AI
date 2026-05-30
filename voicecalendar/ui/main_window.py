from __future__ import annotations

"""VoiceCalendar-Pro 主窗口。

Windows 兼容性方案:
- 无边框窗口 (FramelessWindowHint)
- 不使用 WA_TranslucentBackground / setMask / QGraphicsDropShadowEffect
- 圆角通过 setStyleSheet 实现 (border-radius)
- 自定义标题栏 + 拖拽
"""

from PyQt6.QtCore import (
    Qt,
    QPropertyAnimation,
    QEasingCurve,
    pyqtSignal,
)
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
)

from voicecalendar.config import WindowConfig, AnimationConfig
from voicecalendar.core.theme import ThemeManager, ThemeMode
from voicecalendar.core.resources import ResourceLoader
from voicecalendar.ui.titlebar import TitleBar
from voicecalendar.ui.components.toast import ToastManager, ToastType

win_cfg = WindowConfig()
anim_cfg = AnimationConfig()


class CentralWidget(QWidget):
    """中央内容容器。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ContentArea")

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── 左侧边栏 ──
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(240)
        sidebar.setStyleSheet(
            "QFrame#Sidebar {"
            "    background-color: #23272F;"
            "    border-right: 1px solid #2D323C;"
            "}"
        )

        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(20, 24, 20, 24)
        sidebar_layout.setSpacing(12)

        logo_label = QLabel("\U0001f399️")
        logo_label.setStyleSheet("font-size: 28px;")
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sidebar_layout.addWidget(logo_label)

        brand_label = QLabel(tr("VoiceCalendar"))
        brand_label.setStyleSheet(
            "color: #E8EAED; font-size: 16px; font-weight: 700; padding: 4px 0;"
        )
        brand_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sidebar_layout.addWidget(brand_label)

        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet("background-color: #2D323C;")
        sidebar_layout.addWidget(divider)

        sidebar_layout.addStretch()

        version_label = QLabel("v0.1.0")
        version_label.setStyleSheet("color: #5F6B7A; font-size: 11px;")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sidebar_layout.addWidget(version_label)

        main_layout.addWidget(sidebar)

        # ── 主内容区 ──
        content = QFrame()
        content.setObjectName("MainContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(40, 40, 40, 40)
        content_layout.setSpacing(24)

        welcome_frame = QFrame()
        welcome_layout = QVBoxLayout(welcome_frame)
        welcome_layout.setSpacing(12)

        greeting = QLabel(tr("欢迎使用 VoiceCalendar Pro"))
        greeting.setStyleSheet(
            "color: #E8EAED; font-size: 24px; font-weight: 700;"
        )
        welcome_layout.addWidget(greeting, alignment=Qt.AlignmentFlag.AlignLeft)

        subtitle = QLabel(tr("点击麦克风按钮，用语音管理您的日程"))
        subtitle.setStyleSheet("color: #9AA0A8; font-size: 14px;")
        welcome_layout.addWidget(subtitle, alignment=Qt.AlignmentFlag.AlignLeft)

        content_layout.addWidget(welcome_frame)
        content_layout.addStretch()

        hint_frame = QFrame()
        hint_layout = QHBoxLayout(hint_frame)
        hint_layout.setSpacing(16)

        for icon, text in [
            ("\U0001f4c5", tr("添加日程")),
            ("\U0001f50d", tr("查询日程")),
            ("\U0001f5d1️", tr("删除日程")),
        ]:
            hint_item = QFrame()
            hint_item.setStyleSheet(
                "QFrame {"
                "    background-color: #23272F;"
                "    border: 1px solid #2D323C;"
                "    border-radius: 12px;"
                "    padding: 16px;"
                "}"
                "QFrame:hover {"
                "    border-color: #4B5360;"
                "    background-color: #2D323C;"
                "}"
            )
            item_layout = QVBoxLayout(hint_item)
            item_layout.setSpacing(8)

            icon_label = QLabel(icon)
            icon_label.setStyleSheet("font-size: 24px;")
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            item_layout.addWidget(icon_label)

            text_label = QLabel(text)
            text_label.setStyleSheet("color: #9AA0A8; font-size: 12px;")
            text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            item_layout.addWidget(text_label)

            hint_layout.addWidget(hint_item, stretch=1)

        content_layout.addWidget(hint_frame)
        main_layout.addWidget(content, stretch=1)


class MainWindow(QMainWindow):
    """VoiceCalendar-Pro 主窗口。"""

    theme_toggled: pyqtSignal = pyqtSignal(ThemeMode)

    def __init__(self) -> None:
        super().__init__()
        self._toast_manager: ToastManager | None = None
        self._setup_window()
        self._setup_ui()
        self._apply_theme()
        self._setup_animation()

    def _setup_window(self) -> None:
        """配置窗口。"""
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.resize(win_cfg.DEFAULT_WIDTH, win_cfg.DEFAULT_HEIGHT)
        self.setMinimumSize(win_cfg.MIN_WIDTH, win_cfg.MIN_HEIGHT)
        self.setWindowTitle(tr("VoiceCalendar Pro"))

    def _setup_ui(self) -> None:
        """构建 UI。"""
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self._titlebar = TitleBar(self)
        self._titlebar.minimize_clicked.connect(self.showMinimized)
        self._titlebar.maximize_clicked.connect(self._toggle_maximize)
        self._titlebar.close_clicked.connect(self.close)
        main_layout.addWidget(self._titlebar)

        self._content = CentralWidget(self)
        main_layout.addWidget(self._content, 1)

        self._toast_manager = ToastManager(self)

    def _apply_theme(self) -> None:
        """应用主题样式。"""
        theme_mgr = ThemeManager.instance()
        loader = ResourceLoader()
        loader.load_base_style()
        loader.load_theme_style("dark" if theme_mgr.is_dark() else "light")

        dynamic_colors = theme_mgr.get_color_qss()
        combined = loader.get_combined_style(dynamic_colors)
        self.setStyleSheet(combined)

        theme_mgr.theme_changed.connect(self._on_theme_changed)

    def _on_theme_changed(self, mode: ThemeMode) -> None:
        loader = ResourceLoader()
        loader.load_base_style()
        loader.load_theme_style("dark" if mode == ThemeMode.DARK else "light")

        theme_mgr = ThemeManager.instance()
        combined = loader.get_combined_style(theme_mgr.get_color_qss())
        self.setStyleSheet(combined)
        self.theme_toggled.emit(mode)

    def _setup_animation(self) -> None:
        """入场动画（暂时禁用，Windows 兼容性待优化）。"""
        # TODO: 淡入动画在 Windows 上导致窗口不可见，暂时禁用
        pass

    def _toggle_maximize(self) -> None:
        if self.isMaximized():
            self.showNormal()
            self._titlebar.set_maximized(False)
        else:
            self.showMaximized()
            self._titlebar.set_maximized(True)

    def toast(self, message: str, toast_type: ToastType = ToastType.INFO) -> None:
        if self._toast_manager is not None:
            self._toast_manager.show_toast(message, toast_type)

    # ── 重写方法 ──

    def paintEvent(self, event) -> None:  # type: ignore[override]
        """绘制窗口背景。"""
        from PyQt6.QtGui import QPainter

        painter = QPainter(self)
        theme_mgr = ThemeManager.instance()
        bg = QColor(26, 29, 35) if theme_mgr.is_dark() else QColor(255, 255, 255)
        painter.fillRect(self.rect(), bg)
        painter.end()

    def changeEvent(self, event) -> None:  # type: ignore[override]
        if event.spontaneous():
            is_max = bool(self.windowState() & Qt.WindowState.WindowMaximized)
            self._titlebar.set_maximized(is_max)
        super().changeEvent(event)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        event.ignore()
        fade_out = QPropertyAnimation(self, b"windowOpacity")
        fade_out.setDuration(win_cfg.WINDOW_CLOSE_DURATION)
        fade_out.setStartValue(self.windowOpacity())
        fade_out.setEndValue(0.0)
        fade_out.setEasingCurve(QEasingCurve.Type.InCubic)
        fade_out.finished.connect(self._close_window)
        fade_out.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def _close_window(self) -> None:
        self.close()


def tr(text: str) -> str:
    return text
