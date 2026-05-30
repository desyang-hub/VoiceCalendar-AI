from __future__ import annotations

"""自定义无边框标题栏。

功能:
- 应用图标 + 标题
- 最小化 / 最大化 / 关闭按钮 (带悬停效果)
- 支持窗口拖拽
- 双击最大化/还原
- 深色/浅色主题适配
"""

from PyQt6.QtCore import QPoint, Qt, QSize, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QFont,
    QIcon,
    QMouseEvent,
    QPainter,
    QPainterPath,
)
from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from voicecalendar.config import WindowConfig

win_cfg = WindowConfig()


class TitleBarButton(QPushButton):
    """标题栏窗口控制按钮。"""

    def __init__(
        self,
        icon_text: str,
        parent: "TitleBar | None" = None,
        button_type: str = "normal",
    ) -> None:
        super().__init__(parent)
        self._button_type = button_type
        self._icon_text = icon_text
        self.setFixedSize(46, win_cfg.TITLEBAR_HEIGHT)
        self.setStyleSheet(
            "QPushButton {"
            "    background-color: transparent;"
            "    border: none;"
            "    color: #9AA0A8;"
            "    font-size: 14px;"
            "}"
            "QPushButton:hover {"
            "    background-color: rgba(255, 255, 255, 0.08);"
            "    color: #E8EAED;"
            "}"
            "QPushButton.close:hover {"
            "    background-color: #E81123;"
            "    color: #FFFFFF;"
            "}"
        )
        if button_type == "close":
            self.setProperty("class", "close")
        self.setText(icon_text)
        self.setFont(QFont("Segoe MDL2 Assets", 10))
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        # 让样式表生效
        super().paintEvent(event)


class TitleBar(QWidget):
    """自定义标题栏组件。

    Signal:
        minimize_clicked: 点击最小化
        maximize_clicked: 点击最大化/还原
        close_clicked: 点击关闭
    """

    minimize_clicked: pyqtSignal = pyqtSignal()
    maximize_clicked: pyqtSignal = pyqtSignal()
    close_clicked: pyqtSignal = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(win_cfg.TITLEBAR_HEIGHT)
        self.setObjectName("TitleBar")

        self._is_maximized: bool = False
        self._drag_position: "QPoint | None" = None
        self._drag_threshold: int = 4  # 像素阈值，防止误触发

        # ── 布局 ──
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 0, 0)
        layout.setSpacing(8)

        # 应用图标 (使用文字占位)
        self._icon_label = QLabel("🎙️")
        self._icon_label.setFixedSize(20, 20)
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_label.setStyleSheet("font-size: 16px;")
        layout.addWidget(self._icon_label)

        # 窗口标题
        self._title_label = QLabel(tr("VoiceCalendar Pro"))
        self._title_label.setObjectName("title-label")
        self._title_label.setStyleSheet(
            "QLabel {"
            "    color: #E8EAED;"
            "    font-size: 13px;"
            "    font-weight: 600;"
            "}"
        )
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self._title_label, 1)

        # 窗口控制按钮
        self._btn_minimize = TitleBarButton("—", self, "minimize")  # type: ignore[arg-type]
        self._btn_minimize.clicked.connect(self.minimize_clicked.emit)
        layout.addWidget(self._btn_minimize)

        self._btn_maximize = TitleBarButton("◻", self, "maximize")  # type: ignore[arg-type]
        self._btn_maximize.clicked.connect(self.maximize_clicked.emit)
        layout.addWidget(self._btn_maximize)

        self._btn_close = TitleBarButton("✕", self, "close")  # type: ignore[arg-type]
        self._btn_close.clicked.connect(self.close_clicked.emit)
        layout.addWidget(self._btn_close)

        # 样式
        self.setStyleSheet(
            "QWidget#TitleBar {"
            "    background-color: #23272F;"
            "    border-bottom: 1px solid #2D323C;"
            "}"
        )

    def set_title(self, title: str) -> None:
        """设置窗口标题。"""
        self._title_label.setText(title)

    def set_maximized(self, maximized: bool) -> None:
        """更新最大化状态显示。"""
        self._is_maximized = maximized
        if maximized:
            self._btn_maximize.setText("❐")
        else:
            self._btn_maximize.setText("◻")

    # ── 鼠标事件 (拖拽 + 双击) ──

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_position = event.globalPosition().toPoint()  # type: ignore[attr-defined]
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if (
            self._drag_position is not None
            and event.buttons() == Qt.MouseButton.LeftButton
        ):
            parent = self.parent()
            if parent is not None and parent.windowFlags() & Qt.WindowType.FramelessWindowHint:
                delta = event.globalPosition().toPoint() - self._drag_position  # type: ignore[attr-defined]
                # 超过阈值才移动，防止抖动
                if delta.manhattanLength() > self._drag_threshold:
                    parent.move(parent.pos() + delta)
                    self._drag_position = event.globalPosition().toPoint()  # type: ignore[attr-defined]

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        self._drag_position = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self.maximize_clicked.emit()
        super().mouseDoubleClickEvent(event)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(35, 39, 47))
        painter.end()


# ── tr() 国际化占位 ──

def tr(text: str) -> str:
    """翻译函数占位，后续接入 Qt 翻译系统。"""
    return text
