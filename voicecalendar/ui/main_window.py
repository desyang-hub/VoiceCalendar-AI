from __future__ import annotations

"""VoiceCalendar-Pro 主窗口。

设计要点:
- 无边框窗口 (FramelessWindowHint)
- 自定义圆角 + 阴影 (QPainter 绘制，不依赖 QGraphicsDropShadowEffect)
- 自定义标题栏 (拖拽、最小化、最大化、关闭)
- 主内容区域布局: 左侧边栏 + 中央内容区
- 入场动画 (淡入)
- 主题切换支持
"""

from PyQt6.QtCore import (
    Qt,
    QPropertyAnimation,
    QEasingCurve,
    QPointF,
    QRectF,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QColor,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)
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
    """中央内容容器 — 承载主布局。"""

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

        # Logo / 品牌名
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

        # 分割线
        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet("background-color: #2D323C;")
        sidebar_layout.addWidget(divider)

        sidebar_layout.addStretch()

        # 底部版本信息
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

        # 欢迎区
        welcome_frame = QFrame()
        welcome_layout = QVBoxLayout(welcome_frame)
        welcome_layout.setSpacing(12)

        greeting = QLabel(tr("欢迎使用 VoiceCalendar Pro"))
        greeting.setStyleSheet(
            "color: #E8EAED; font-size: 24px; font-weight: 700;"
        )
        welcome_layout.addWidget(greeting, alignment=Qt.AlignmentFlag.AlignLeft)

        subtitle = QLabel(tr("点击麦克风按钮，用语音管理您的日程"))
        subtitle.setStyleSheet(
            "color: #9AA0A8; font-size: 14px;"
        )
        welcome_layout.addWidget(subtitle, alignment=Qt.AlignmentFlag.AlignLeft)

        content_layout.addWidget(welcome_frame)
        content_layout.addStretch()

        # 底部提示卡片
        hint_frame = QFrame()
        hint_layout = QHBoxLayout(hint_frame)
        hint_layout.setSpacing(16)

        hints = [
            ("\U0001f4c5", tr("添加日程")),
            ("\U0001f50d", tr("查询日程")),
            ("\U0001f5d1️", tr("删除日程")),
        ]
        for icon, text in hints:
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
    """VoiceCalendar-Pro 主窗口。

    窗口特性:
    - 无边框 + 自定义圆角裁剪
    - QPainter 绘制阴影 (不依赖 QGraphicsDropShadowEffect)
    - 自定义标题栏
    - 入场/出场动画
    - 主题切换
    """

    theme_toggled: pyqtSignal = pyqtSignal(ThemeMode)

    # 阴影参数
    SHADOW_BLUR = 20
    SHADOW_OFFSET_X = 0
    SHADOW_OFFSET_Y = 8

    def __init__(self) -> None:
        super().__init__()
        self._toast_manager: ToastManager | None = None
        self._setup_window()
        self._setup_ui()
        self._setup_animation()
        self._apply_theme()

    # ──────────────────────────────────────────
    # 窗口初始化
    # ──────────────────────────────────────────

    def _setup_window(self) -> None:
        """配置窗口标志、尺寸、透明背景。

        注意: 不再使用 QGraphicsDropShadowEffect，
        阴影在 paintEvent 中用 QPainter 绘制。
        """
        # 无边框 + 透明背景
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # 窗口尺寸
        self.resize(win_cfg.DEFAULT_WIDTH, win_cfg.DEFAULT_HEIGHT)
        self.setMinimumSize(win_cfg.MIN_WIDTH, win_cfg.MIN_HEIGHT)

        # 窗口标题
        self.setWindowTitle(tr("VoiceCalendar Pro"))

    def _setup_ui(self) -> None:
        """构建窗口内部布局。"""
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── 标题栏 ──
        self._titlebar = TitleBar(self)
        self._titlebar.minimize_clicked.connect(self.showMinimized)
        self._titlebar.maximize_clicked.connect(self._toggle_maximize)
        self._titlebar.close_clicked.connect(self.close)
        main_layout.addWidget(self._titlebar)

        # ── 内容区 ──
        self._content = CentralWidget(self)
        main_layout.addWidget(self._content, 1)

        # ── Toast 管理器 ──
        self._toast_manager = ToastManager(self)

    def _apply_theme(self) -> None:
        """加载并应用主题样式。"""
        theme_mgr = ThemeManager.instance()
        loader = ResourceLoader()

        loader.load_base_style()
        loader.load_theme_style("dark" if theme_mgr.is_dark() else "light")

        dynamic_colors = theme_mgr.get_color_qss()
        combined = loader.get_combined_style(dynamic_colors)
        self.setStyleSheet(combined)

        theme_mgr.theme_changed.connect(self._on_theme_changed)

    def _on_theme_changed(self, mode: ThemeMode) -> None:
        """主题切换回调。"""
        loader = ResourceLoader()
        loader.load_base_style()
        loader.load_theme_style("dark" if mode == ThemeMode.DARK else "light")

        theme_mgr = ThemeManager.instance()
        dynamic_colors = theme_mgr.get_color_qss()
        combined = loader.get_combined_style(dynamic_colors)
        self.setStyleSheet(combined)

        self.theme_toggled.emit(mode)

    # ──────────────────────────────────────────
    # 动画
    # ──────────────────────────────────────────

    def _setup_animation(self) -> None:
        """窗口入场动画 (淡入)。"""
        self.setWindowOpacity(0.0)

        fade_in = QPropertyAnimation(self, b"windowOpacity")
        fade_in.setDuration(anim_cfg.SLOW)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)
        fade_in.setEasingCurve(QEasingCurve.Type.OutCubic)
        fade_in.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    # ──────────────────────────────────────────
    # 窗口控制
    # ──────────────────────────────────────────

    def _toggle_maximize(self) -> None:
        """切换最大化/还原。"""
        if self.isMaximized():
            self.showNormal()
            self._titlebar.set_maximized(False)
        else:
            self.showMaximized()
            self._titlebar.set_maximized(True)

    # ──────────────────────────────────────────
    # Toast 便捷方法
    # ──────────────────────────────────────────

    def toast(self, message: str, toast_type: ToastType = ToastType.INFO) -> None:
        """显示一条 Toast 通知。"""
        if self._toast_manager is not None:
            self._toast_manager.show_toast(message, toast_type)

    # ──────────────────────────────────────────
    # 重写方法
    # ──────────────────────────────────────────

    def paintEvent(self, event) -> None:  # type: ignore[override]
        """自定义绘制：圆角背景 + 阴影 (QPainter 实现)。

        不使用 QGraphicsDropShadowEffect，避免 Windows
        UpdateLayeredWindowIndirect 兼容性问题。
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        radius = win_cfg.CORNER_RADIUS
        w, h = self.width(), self.height()

        # ── 阴影层 (多层渐变模拟真实阴影) ──
        self._draw_shadow(painter, w, h, radius)

        # ── 主体背景 ──
        theme_mgr = ThemeManager.instance()
        if theme_mgr.is_dark():
            bg_color = QColor(26, 29, 35)
        else:
            bg_color = QColor(255, 255, 255)

        bg_path = QPainterPath()
        bg_path.addRoundedRect(
            0, 0, w, h, radius, radius,
        )
        painter.fillPath(bg_path, bg_color)

        # ── 细微边框 ──
        border_color = QColor(60, 65, 75, 120) if theme_mgr.is_dark() else QColor(200, 200, 200, 80)
        painter.setPen(QPen(border_color, 1))
        painter.drawPath(bg_path)

        painter.end()

    def _draw_shadow(self, painter: QPainter, w: int, h: int, radius: int) -> None:
        """用多层渐变绘制圆角阴影。"""
        blur = self.SHADOW_BLUR
        ox = self.SHADOW_OFFSET_X
        oy = self.SHADOW_OFFSET_Y

        # 阴影偏移区域
        sx = -blur + ox
        sy = -blur + oy
        sw = w + 2 * blur
        sh = h + 2 * blur

        # 多层阴影叠加
        for i in range(3):
            alpha = 20 - i * 5
            expand = blur * (i + 1) * 0.3

            shadow_path = QPainterPath()
            shadow_path.addRoundedRect(
                sx - expand, sy - expand,
                sw + expand * 2, sh + expand * 2,
                radius + expand * 0.5, radius + expand * 0.5,
            )

            gradient = QLinearGradient(
                sx - expand, sy - expand,
                sx - expand, sy + sh + expand
            )
            shadow_c = QColor(0, 0, 0, alpha)
            gradient.setColorAt(0.0, shadow_c)
            gradient.setColorAt(1.0, QColor(0, 0, 0, alpha // 2))
            painter.fillPath(shadow_path, gradient)

    def changeEvent(self, event) -> None:  # type: ignore[override]
        """处理窗口最大化/还原状态变化。"""
        if event.spontaneous():
            window_state = self.windowState()
            is_max = bool(window_state & Qt.WindowState.WindowMaximized)
            self._titlebar.set_maximized(is_max)
        super().changeEvent(event)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        """窗口关闭动画。"""
        event.ignore()
        fade_out = QPropertyAnimation(self, b"windowOpacity")
        fade_out.setDuration(anim_cfg.WINDOW_CLOSE_DURATION)
        fade_out.setStartValue(self.windowOpacity())
        fade_out.setEndValue(0.0)
        fade_out.setEasingCurve(QEasingCurve.Type.InCubic)
        fade_out.finished.connect(self._close_window)
        fade_out.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def _close_window(self) -> None:
        self.close()


# ── tr() 国际化占位 ──

def tr(text: str) -> str:
    """翻译函数占位，后续接入 Qt 翻译系统。"""
    return text
