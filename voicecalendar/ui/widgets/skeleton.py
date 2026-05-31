from __future__ import annotations

"""加载骨架屏组件。

在数据加载期间显示微光闪烁动画，替代空白等待。
"""

import math

from PyQt6.QtCore import QPointF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QWidget


class SkeletonShimmer(QWidget):
    """骨架屏微光闪烁动画。

    用途:
    - 日程加载时的占位卡片
    - 语音处理中的进度提示
    """

    finished: pyqtSignal = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedHeight(56)

        self._phase: float = 0.0

        self._timer = QTimer(self)
        self._timer.setInterval(30)  # ~33fps
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def _tick(self) -> None:
        self._phase += 0.04
        if self._phase > math.pi * 2:
            self._phase -= math.pi * 2
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        radius = 12

        # 圆角背景
        path = QPainterPath()
        path.addRoundedRect(0, 0, w, h, radius, radius)
        painter.fillPath(path, QColor(35, 39, 47, 240))

        # 微光渐变
        shimmer_x = (self._phase / (math.pi * 2)) * (w + 200) - 100

        gradient = QLinearGradient(shimmer_x, 0, shimmer_x + 200, 0)
        gradient.setColorAt(0.0, QColor(35, 39, 47, 240))
        gradient.setColorAt(0.5, QColor(45, 50, 60, 240))
        gradient.setColorAt(1.0, QColor(35, 39, 47, 240))

        painter.fillPath(path, gradient)

        # 模拟内容占位
        # 左侧色条
        painter.fillRect(8, 12, 3, 32, QColor(50, 55, 65, 180))

        # 时间文字占位
        painter.fillRect(20, 14, 40, 10, QColor(50, 55, 65, 180))

        # 分割线占位
        painter.fillRect(72, 12, 1, 32, QColor(50, 55, 65, 120))

        # 标题文字占位（两行宽度不同）
        painter.fillRect(90, 16, min(w * 0.4, 200), 10, QColor(50, 55, 65, 180))
        painter.fillRect(90, 32, min(w * 0.25, 120), 10, QColor(50, 55, 65, 120))

        # 右侧日期徽章占位
        badge_w, badge_h = 36, 20
        painter.setBrush(QColor(50, 55, 65, 180))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(
            w - badge_w - 12, (h - badge_h) // 2,
            badge_w, badge_h, 6, 6,
        )

        painter.end()


class CircularProgress(QWidget):
    """圆形进度指示器 — 用于"正在识别"状态。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(40, 40)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._angle: float = 0.0
        self._color = QColor(107, 138, 255)

        self._timer = QTimer(self)
        self._timer.setInterval(16)  # ~60fps
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def set_color(self, color: QColor) -> None:
        self._color = color
        self.update()

    def _tick(self) -> None:
        self._angle += 0.12
        if self._angle > math.pi * 2:
            self._angle -= math.pi * 2
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx, cy = self.width() // 2, self.height() // 2
        radius = 14
        line_width = 3

        # 背景圆环（淡色）
        painter.setPen(QPen(QColor(self._color.red(), self._color.green(), self._color.blue(), 30),
                           line_width, Qt.PenStyle.SolidLine,
                           Qt.PenCapStyle.RoundCap))
        painter.drawEllipse(QPointF(cx, cy), radius, radius)

        # 旋转弧段
        painter.setPen(QPen(self._color, line_width, Qt.PenStyle.SolidLine,
                           Qt.PenCapStyle.RoundCap))
        painter.drawArc(
            cx - radius - line_width, cy - radius - line_width,
            (radius + line_width) * 2, (radius + line_width) * 2,
            int(self._angle * 180 / math.pi * 16),
            int(5 * 180 / math.pi * 16),
        )

        painter.end()
