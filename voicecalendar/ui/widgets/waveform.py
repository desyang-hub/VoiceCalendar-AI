from __future__ import annotations

"""实时音频波形可视化 Widget。

支持柱状频谱 / 平滑波形两种显示模式。
空闲状态下有微弱的呼吸动画，录音时响应 RMS 数据。
"""

import math
from typing import Optional

from PyQt6.QtCore import (
    Qt,
    QTimer,
    QPropertyAnimation,
    QEasingCurve,
    QRectF,
    QPointF,
    pyqtSignal,
)
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QFontMetrics
from PyQt6.QtWidgets import QWidget

from voicecalendar.config import AnimationConfig

anim_cfg = AnimationConfig()


class WaveformWidget(QWidget):
    """音频波形可视化控件。

    Signal:
        recording_toggled: 录音状态切换信号
    """

    recording_toggled: pyqtSignal = pyqtSignal(bool)

    # 显示模式
    BARS = 1
    WAVE = 2

    def __init__(self, parent: QWidget | None = None, mode: int = 1) -> None:
        super().__init__(parent)
        self._mode = mode
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)

        # 波形数据
        self._bars: list[float] = [0.0] * 64
        self._wave_points: list[float] = [0.0] * 128

       # 状态
        self._is_recording: bool = False
        self._rms_level: float = 0.0
        self._pulse_value: float = 0.0
        self._idle_phase: float = 0.0  # 空闲呼吸相位

        # 动画定时器
        self._update_timer = QTimer(self)
        self._update_timer.setInterval(50)  # 20fps
        self._update_timer.timeout.connect(self._update_animation)
        self._update_timer.start()

        # 脉冲动画
        self._pulse_timer = QTimer(self)
        self._pulse_timer.setInterval(100)
        self._pulse_timer.timeout.connect(self._on_pulse_tick)

    def set_mode(self, mode: int) -> None:
        """切换显示模式。"""
        self._mode = mode
        self.update()

    def set_rms_level(self, rms: float) -> None:
        """设置当前 RMS 音量水平 (0.0 - 1.0)。"""
        self._rms_level = max(0.0, min(1.0, rms))
        self._update_bars_from_rms()

    def set_recording(self, recording: bool) -> None:
        """设置录音状态。"""
        self._is_recording = recording
        self.recording_toggled.emit(recording)

        if recording:
            self._pulse_timer.start()
            # 激活波形数据
            self._activate_bars()
        else:
            self._pulse_timer.stop()
            # 缓慢衰减
            self._decay_bars()

    def _update_bars_from_rms(self) -> None:
        """根据 RMS 值更新柱状数据。"""
        for i in range(len(self._bars)):
            target = self._rms_level * (0.5 + 0.5 * math.sin(i * 0.3))
            self._bars[i] += (target - self._bars[i]) * 0.3

    def _activate_bars(self) -> None:
        """激活波形数据 (模拟动态效果)。"""
        for i in range(len(self._bars)):
            self._bars[i] = 0.3 + 0.4 * math.sin(i * 0.5 + self._rms_level * 10)

    def _decay_bars(self) -> None:
        """衰减波形数据。"""
        for i in range(len(self._bars)):
            self._bars[i] *= 0.9

    def _on_pulse_tick(self) -> None:
        """脉冲动画计时器。"""
        self._pulse_value = (self._pulse_value + 0.1) % (2 * math.pi)
        self.update()

    def _update_animation(self) -> None:
        """更新动画帧 — 空闲时驱动呼吸，录音时驱动波形。"""
        # 空闲呼吸相位
        if not self._is_recording:
            self._idle_phase += 0.08
        if self._is_recording:
            # 更新波形数据
            for i in range(len(self._bars)):
                noise = (math.sin(i * 0.7 + self._rms_level * 20) + 1) * 0.25
                target = self._rms_level * noise
                self._bars[i] += (target - self._bars[i]) * 0.5

            # 更新波形点
            for i in range(len(self._wave_points)):
                self._wave_points[i] = math.sin(i * 0.2 + self._rms_level * 30) * self._rms_level * 0.4

        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        """绘制波形。"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()

        if self._mode == self.BARS:
            self._draw_bars(painter, w, h)
        else:
            self._draw_wave(painter, w, h)

        # 录音脉冲指示
        if self._is_recording:
            self._draw_recording_indicator(painter, w, h)

        painter.end()

    def _draw_bars(self, painter: QPainter, w: int, h: int) -> None:
        """绘制柱状频谱。

        空闲状态下显示微弱的呼吸动画（中心线附近轻微波动）。
        录音状态下响应 RMS 数据驱动。
        """
        num_bars = len(self._bars)
        bar_width = max(2, (w - 20) / num_bars - 2)
        start_x = 10

        for i, level in enumerate(self._bars):
            x = start_x + i * (bar_width + 2)

            if not self._is_recording and level < 0.01:
                # 空闲呼吸 — 中心线附近微弱波动
                breathe = math.sin(i * 0.4 + self._idle_phase) * 0.15 + 0.5
                bar_height = max(3, h * breathe * 0.06)
                y = (h - bar_height) / 2
                alpha = int(60 + math.sin(i * 0.3 + self._idle_phase) * 20)
                color = QColor(107, 138, 255, alpha)
            else:
                bar_height = max(4, h * level * 0.8)
                y = (h - bar_height) / 2
                # 颜色渐变 (从蓝到红)
                hue = int(240 - level * 240)  # 蓝色(240) -> 红色(0)
                color = QColor.fromHsl(hue, 200, 60)

            painter.setBrush(QBrush(color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(x, y, bar_width, bar_height, bar_width / 2, bar_width / 2)

    def _draw_wave(self, painter: QPainter, w: int, h: int) -> None:
        """绘制平滑波形。

        空闲状态下显示微弱正弦呼吸波，录音状态下响应数据驱动。
        """
        points = self._wave_points
        if not points:
            return

        step = w / (len(points) - 1)
        max_height = h * 0.8

        # 波形颜色
        wave_color = QColor(107, 138, 255, 200)
        if not self._is_recording:
            wave_color = QColor(107, 138, 255, 50)

        painter.setPen(QPen(wave_color, 2, Qt.PenStyle.SolidLine))
        painter.setBrush(Qt.BrushStyle.NoBrush)

        # 绘制波形
        path = QPainterPath()
        path.moveTo(0, h / 2)

        for i, point in enumerate(points):
            x = i * step
            if not self._is_recording:
                # 空闲呼吸波 — 微弱正弦
                idle_wave = math.sin(i * 0.15 + self._idle_phase) * 0.02
                y = h / 2 + idle_wave * max_height
            else:
                y = h / 2 + point * max_height
            path.lineTo(x, y)

        painter.drawPath(path)

        # 中心线
        line_color = QColor(107, 138, 255, 40) if self._is_recording else QColor(107, 138, 255, 20)
        painter.setPen(QPen(line_color, 1, Qt.PenStyle.SolidLine))
        painter.drawLine(0, h // 2, w, h // 2)

    def _draw_recording_indicator(self, painter: QPainter, w: int, h: int) -> None:
        """绘制录音状态指示器。"""
        pulse = math.sin(self._pulse_value) * 0.5 + 0.5  # 0-1
        indicator_size = 12 + pulse * 4
        x = w - 30
        y = h // 2

        # 外圈
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(255, 59, 48, int(100 + pulse * 100))))
        painter.drawEllipse(QPointF(x, y), indicator_size, indicator_size)

        # 内圈
        painter.setBrush(QBrush(QColor(255, 59, 48, 200)))
        painter.drawEllipse(QPointF(x, y), indicator_size * 0.5, indicator_size * 0.5)

        # "REC" 文字
        painter.setPen(QColor(255, 59, 48, int(180 + pulse * 75)))
        font = QFont("Segoe UI", 10, QFont.Weight.Bold)
        painter.setFont(font)
        painter.setPen(QColor(255, 59, 48, int(200 + pulse * 55)))
        painter.drawText(10, h - 8, "REC")


class StatusIndicator(QWidget):
    """录音状态指示器 — 带光晕效果和脉冲动画。

    状态流转: idle → recording → processing → success/error
    """

    # 状态颜色映射
    _STATUS_COLORS = {
        "idle": QColor(154, 160, 168, 180),
        "recording": QColor(255, 59, 48, 240),
        "processing": QColor(255, 179, 64, 220),
        "success": QColor(61, 220, 132, 220),
        "error": QColor(255, 107, 107, 220),
    }

    _STATUS_TEXTS = {
        "idle": "点击麦克风开始录音",
        "recording": "正在录音...",
        "processing": "正在识别...",
        "success": "识别完成",
        "error": "识别失败",
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(36)

        self._status: str = "idle"
        self._status_text: str = "点击麦克风开始录音"
        self._pulse_phase: float = 0.0

        self._pulse_timer = QTimer(self)
        self._pulse_timer.setInterval(50)
        self._pulse_timer.timeout.connect(self._on_pulse)

    def set_status(self, status: str, text: str = "") -> None:
        """设置状态。"""
        self._status = status
        self._status_text = text or self._STATUS_TEXTS.get(status, "未知状态")

        if status == "recording":
            self._pulse_timer.start()
        else:
            self._pulse_timer.stop()

        self.update()

    def _on_pulse(self) -> None:
        self._pulse_phase += 0.12
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        center_y = h // 2
        dot_x = 12

        base_color = self._STATUS_COLORS.get(self._status, self._STATUS_COLORS["idle"])

        # 脉冲效果
        pulse = 1.0
        if self._status == "recording":
            pulse = math.sin(self._pulse_phase) * 0.3 + 0.7

        # ── 外圈光晕 ──
        glow_color = QColor(base_color.red(), base_color.green(),
                           base_color.blue(), int(40 * pulse))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(glow_color))
        painter.drawEllipse(dot_x - 2, center_y - 9, 20, 20)

        # ── 状态指示灯 ──
        dot_color = QColor(base_color.red(), base_color.green(),
                          base_color.blue(), int(base_color.alpha() * pulse))
        painter.setBrush(QBrush(dot_color))
        painter.drawEllipse(dot_x - 5, center_y - 5, 10, 10)

        # ── 状态文字 ──
        text_color = QColor(base_color.red(), base_color.green(),
                           base_color.blue(), 200)
        painter.setPen(text_color)
        font = QFont("Segoe UI", 12)
        painter.setFont(font)
        painter.drawText(30, center_y + 4, self._status_text)

        painter.end()
