from __future__ import annotations

"""基础 Widget 类：提供圆角裁剪、阴影、主题响应等通用能力。

所有自定义 Widget 应继承此基类而非直接使用 QWidget。
"""

from abc import abstractmethod

from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QPen, QColor, QBrush
from PyQt6.QtWidgets import QWidget, QGraphicsDropShadowEffect


class RoundedWidget(QWidget):
    """带圆角的 Widget 基类。

    自动处理:
    - 圆角背景绘制
    - 可选边框
    - 可选阴影
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        corner_radius: int = 12,
        border_width: int = 0,
        shadow_enabled: bool = False,
    ) -> None:
        super().__init__(parent)
        self._corner_radius = corner_radius
        self._border_width = border_width

        if shadow_enabled:
            shadow = QGraphicsDropShadowEffect(self)
            shadow.setBlurRadius(16)
            shadow.setOffset(0, 4)
            shadow.setColor(QColor(0, 0, 0, 30))
            self.setGraphicsEffect(shadow)

    def set_corner_radius(self, radius: int) -> None:
        self._corner_radius = radius
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        super().paintEvent(event)
