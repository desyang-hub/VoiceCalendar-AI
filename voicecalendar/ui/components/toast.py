from __future__ import annotations

"""Toast 非模态通知组件。

设计要点:
- 从右上角滑入/滑出，带透明度渐变动画
- 最多同时显示 3 条，自动堆叠
- 支持 success / error / warning / info 四种类型
- 自动消失 (默认 3s)，鼠标悬停暂停计时
"""

from enum import Enum

from PyQt6.QtCore import (
    Qt,
    QPoint,
    QTimer,
    QPropertyAnimation,
    QEasingCurve,
    pyqtSignal,
)
from PyQt6.QtGui import QColor, QPainter, QPainterPath
from PyQt6.QtWidgets import QWidget, QGraphicsDropShadowEffect, QHBoxLayout, QLabel

from voicecalendar.config import ToastConfig, AnimationConfig

toast_cfg = ToastConfig()
anim_cfg = AnimationConfig()


class ToastType(Enum):
    """Toast 类型。"""

    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


# ─────────────────────────────────────────────
# Toast 图标与颜色映射
# ─────────────────────────────────────────────

_TOAST_ICONS: dict[ToastType, str] = {
    ToastType.SUCCESS: "✓",
    ToastType.ERROR: "✕",
    ToastType.WARNING: "⚠",
    ToastType.INFO: "ℹ",
}

_TOAST_COLORS: dict[ToastType, tuple[str, str]] = {
    ToastType.SUCCESS: ("#34C759", "#FFFFFF"),
    ToastType.ERROR: ("#FF3B30", "#FFFFFF"),
    ToastType.WARNING: ("#FF9500", "#FFFFFF"),
    ToastType.INFO: ("#5AC8FA", "#FFFFFF"),
}


class ToastWidget(QWidget):
    """单条 Toast 通知控件。

    Signal:
        dismissed: 动画结束后发出，通知 ToastManager 移除
    """

    dismissed: pyqtSignal = pyqtSignal(object)

    def __init__(
        self,
        message: str,
        toast_type: ToastType,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(toast_cfg.WIDTH, toast_cfg.HEIGHT)

        self._message = message
        self._type = toast_type
        self._auto_timer: QTimer | None = None

        # ── 布局 ──
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 14, 0)
        layout.setSpacing(10)

        # 图标
        self._icon_label = QLabel(_TOAST_ICONS[toast_type])
        self._icon_label.setFixedSize(22, 22)
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_color = _TOAST_COLORS[toast_type][0]
        self._icon_label.setStyleSheet(
            f"background-color: {icon_color};"
            f"color: #FFFFFF;"
            f"border-radius: 11px;"
            f"font-size: 11px;"
            f"font-weight: 700;"
        )
        layout.addWidget(self._icon_label)

        # 消息文本
        self._msg_label = QLabel(message)
        self._msg_label.setStyleSheet(
            "color: #E8EAED; font-size: 13px;"
        )
        self._msg_label.setWordWrap(False)
        layout.addWidget(self._msg_label, 1)

        # ── 阴影 ──
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(16)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 40))
        self.setGraphicsEffect(shadow)

        # ── 自动消失定时器 ──
        self._auto_timer = QTimer(self)
        self._auto_timer.setSingleShot(True)
        self._auto_timer.timeout.connect(self._dismiss)
        self._start_auto_timer()

    def _start_auto_timer(self) -> None:
        if self._auto_timer is not None:
            self._auto_timer.start(anim_cfg.TOAST_DURATION)

    def _pause_auto_timer(self) -> None:
        if self._auto_timer is not None:
            self._auto_timer.stop()

    def enterEvent(self, event) -> None:  # type: ignore[override]
        self._pause_auto_timer()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # type: ignore[override]
        self._start_auto_timer()
        super().leaveEvent(event)

    def _dismiss(self) -> None:
        """执行滑出动画。"""
        self.setEnabled(False)

        animation = QPropertyAnimation(self, b"pos")
        animation.setDuration(anim_cfg.TOAST_DISAPPEAR)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.setStartValue(self.pos())

        end_pos = self.pos() + QPoint(60, 0)
        animation.setEndValue(end_pos)
        animation.finished.connect(self._on_dismissed)
        animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def _on_dismissed(self) -> None:
        self.dismissed.emit(self)
        self.deleteLater()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 圆角背景
        path = QPainterPath()
        path.addRoundedRect(
            0, 0, self.width(), self.height(),
            toast_cfg.CORNER_RADIUS, toast_cfg.CORNER_RADIUS,
        )
        painter.fillPath(path, QColor(45, 50, 60, 230))

        # 左侧颜色指示条
        icon_color = _TOAST_COLORS[self._type][0]
        painter.save()
        clip_path = QPainterPath()
        clip_path.addRoundedRect(
            0, 0, self.width(), self.height(),
            toast_cfg.CORNER_RADIUS, toast_cfg.CORNER_RADIUS,
        )
        painter.setClipPath(clip_path)
        painter.fillRect(0, 6, 4, self.height() - 12, QColor(icon_color))
        painter.restore()

        painter.end()


class ToastManager:
    """Toast 通知管理器。

    职责:
    - 管理 Toast 堆叠布局
    - 控制最大可见数
    - 处理动画入场/出场
    """

    def __init__(self, parent_window: QWidget) -> None:
        self._parent = parent_window
        self._toasts: list[ToastWidget] = []

    def show_toast(self, message: str, toast_type: ToastType = ToastType.INFO) -> None:
        """显示一条 Toast 通知。"""
        # 限制最大数量
        if len(self._toasts) >= toast_cfg.MAX_VISIBLE:
            oldest = self._toasts.pop(0)
            oldest._dismiss()  # noqa: SLF001

        # 计算位置
        y_offset = len(self._toasts) * (toast_cfg.HEIGHT + toast_cfg.SPACING)
        x = self._parent.width() - toast_cfg.WIDTH - toast_cfg.OFFSET_RIGHT
        y = toast_cfg.OFFSET_TOP + y_offset

        toast = ToastWidget(message, toast_type, self._parent)
        toast.move(x, y)

        self._toasts.append(toast)
        toast.dismissed.connect(self._on_dismissed)

        # 入场动画
        toast.show()
        start_pos = toast.pos() + QPoint(60, 0)
        animation = QPropertyAnimation(toast, b"pos")
        animation.setDuration(anim_cfg.TOAST_APPEAR)
        animation.setEasingCurve(QEasingCurve.Type.OutBack)
        animation.setStartValue(start_pos)
        animation.setEndValue(toast.pos())
        animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def _on_dismissed(self, toast: ToastWidget) -> None:
        """Toast 被移除后的回调。"""
        if toast in self._toasts:
            self._toasts.remove(toast)

        # 重新排列剩余 Toast 的位置
        for i, t in enumerate(self._toasts):
            x = self._parent.width() - toast_cfg.WIDTH - toast_cfg.OFFSET_RIGHT
            y = toast_cfg.OFFSET_TOP + i * (toast_cfg.HEIGHT + toast_cfg.SPACING)
            t.move(x, y)

    def clear_all(self) -> None:
        """清除所有 Toast。"""
        for t in self._toasts[:]:
            t._dismiss()  # noqa: SLF001
