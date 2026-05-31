from __future__ import annotations

"""自定义无边框标题栏。

功能:
- 应用图标 + 标题
- 最小化 / 最大化 / 关闭按钮
- 支持窗口拖拽 (通过 QMainWindow 的 windowHandle())
- 双击最大化/还原

事件处理注意事项:
- 按钮区域不触发拖拽
- 拖拽通过 QMouseEvent 在 MainWindow 上执行 move()
"""

from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QMouseEvent, QPainter
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from voicecalendar.config import WindowConfig

win_cfg = WindowConfig()


class TitleBarButton(QPushButton):
    """标题栏窗口控制按钮。"""

    def __init__(
        self,
        icon_text: str,
        parent: TitleBar | None = None,
        button_type: str = "normal",
    ) -> None:
        super().__init__(parent)
        self._button_type = button_type
        self.setFixedSize(46, win_cfg.TITLEBAR_HEIGHT)

        if button_type == "close":
            self.setStyleSheet(
                "QPushButton {"
                "    background-color: transparent; border: none;"
                "    color: #9AA0A8; font-size: 14px;"
                "}"
                "QPushButton:hover {"
                "    background-color: #E81123; color: #FFFFFF;"
                "}"
                "QPushButton:pressed {"
                "    background-color: #C50E1A; color: #FFFFFF;"
                "}"
            )
        else:
            self.setStyleSheet(
                "QPushButton {"
                "    background-color: transparent; border: none;"
                "    color: #9AA0A8; font-size: 14px;"
                "}"
                "QPushButton:hover {"
                "    background-color: rgba(255,255,255,0.08); color: #E8EAED;"
                "}"
                "QPushButton:pressed {"
                "    background-color: rgba(255,255,255,0.04);"
                "}"
            )

        self.setText(icon_text)
        self.setFont(QFont("Segoe MDL2 Assets", 10))
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, event) -> None:  # type: ignore[override]
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
        self._drag_start_pos: QPoint | None = None
        self._drag_threshold: int = 3

        # ── 布局 ──
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 8, 0)
        layout.setSpacing(8)

        # 应用图标
        self._icon_label = QLabel("\U0001f399️")
        self._icon_label.setFixedSize(20, 20)
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_label.setStyleSheet("font-size: 14px;")
        layout.addWidget(self._icon_label)

        # 窗口标题
        self._title_label = QLabel(tr("VoiceCalendar Pro"))
        self._title_label.setObjectName("title-label")
        self._title_label.setStyleSheet(
            "QLabel { color: #E8EAED; font-size: 13px; font-weight: 600; }"
        )
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self._title_label, 1)

        # 窗口控制按钮
        self._btn_minimize = TitleBarButton("―", self, "minimize")
        self._btn_minimize.clicked.connect(self._on_minimize)
        layout.addWidget(self._btn_minimize)

        self._btn_maximize = TitleBarButton("⛶", self, "maximize")
        self._btn_maximize.clicked.connect(self._on_maximize)
        layout.addWidget(self._btn_maximize)

        self._btn_close = TitleBarButton("✕", self, "close")
        self._btn_close.clicked.connect(self._on_close)
        layout.addWidget(self._btn_close)

    def _on_minimize(self) -> None:
        self.minimize_clicked.emit()

    def _on_maximize(self) -> None:
        self.maximize_clicked.emit()

    def _on_close(self) -> None:
        self.close_clicked.emit()

    def set_title(self, title: str) -> None:
        self._title_label.setText(title)

    def set_maximized(self, maximized: bool) -> None:
        self._is_maximized = maximized
        self._btn_maximize.setText("⊞" if maximized else "⛶")

    # ── 鼠标事件 (拖拽) ──

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            # 按钮区域不触发拖拽
            if self._is_button_area(event.pos()):
                return
            self._drag_start_pos = event.globalPosition().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if self._drag_start_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            current_pos = event.globalPosition().toPoint()
            delta = current_pos - self._drag_start_pos

            if delta.manhattanLength() > self._drag_threshold:
                # 拖拽目标: 顶层窗口 (不是 parent widget)
                main_window = self.window()
                if main_window is not None:
                    new_pos = main_window.pos() + delta
                    main_window.move(new_pos)
                self._drag_start_pos = current_pos
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        self._drag_start_pos = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton and not self._is_button_area(event.pos()):
            self.maximize_clicked.emit()
        super().mouseDoubleClickEvent(event)

    def _is_button_area(self, pos: QPoint) -> bool:
        """判断鼠标位置是否在按钮区域内。

        三个按钮各 46px + 间距 8px × 2 = 150px，
        所以标题栏右侧约 150px 是按钮区域。
        """
        return pos.x() >= self.width() - 150

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(35, 39, 47))
        painter.setPen(QColor(45, 50, 60))
        painter.drawLine(0, self.height() - 1, self.width() - 1, self.height() - 1)
        painter.end()


def tr(text: str) -> str:
    return text
