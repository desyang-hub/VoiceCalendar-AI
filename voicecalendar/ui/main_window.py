from __future__ import annotations

"""VoiceCalendar-Pro 主窗口。

集成语音日历所有功能。
"""

import math
from datetime import date
from typing import Optional

from PyQt6.QtCore import (
    Qt,
    QTimer,
    QThread,
    QObject,
    pyqtSignal,
    pyqtSlot,
    QSize,
    QPointF,
)
from PyQt6.QtGui import QColor, QPainter, QFont, QMouseEvent, QPen, QBrush
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QPushButton,
    QScrollArea,
    QSpacerItem,
)

from voicecalendar.config import WindowConfig, AnimationConfig
from voicecalendar.core.theme import ThemeManager, ThemeMode
from voicecalendar.core.resources import ResourceLoader
from voicecalendar.ui.titlebar import TitleBar
from voicecalendar.ui.components.toast import ToastManager, ToastType
from voicecalendar.ui.widgets.waveform import WaveformWidget, StatusIndicator
from voicecalendar.models.event import CalendarEvent, ParseIntent
from voicecalendar.services.pipeline import VoiceCalendarPipeline, MockPipeline, PipelineResult

win_cfg = WindowConfig()
anim_cfg = AnimationConfig()


class RecordButton(QWidget):
    """录音按钮 — 带脉冲动画。"""

    recording_started: pyqtSignal = pyqtSignal()
    recording_stopped: pyqtSignal = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(80, 80)

        self._is_recording: bool = False
        self._pulse_phase: float = 0.0

        self._pulse_timer = QTimer(self)
        self._pulse_timer.setInterval(50)
        self._pulse_timer.timeout.connect(self._on_pulse)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_recording = not self._is_recording
            if self._is_recording:
                self._pulse_timer.start()
                self.recording_started.emit()
            else:
                self._pulse_timer.stop()
                self.recording_stopped.emit()
            self.update()
        super().mousePressEvent(event)

    def _on_pulse(self) -> None:
        self._pulse_phase += 0.15
        self.update()

    def set_recording(self, recording: bool) -> None:
        self._is_recording = recording
        if recording:
            self._pulse_timer.start()
        else:
            self._pulse_timer.stop()
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx, cy = self.width() // 2, self.height() // 2

        if self._is_recording:
            # 录音中 — 红色脉冲
            pulse = math.sin(self._pulse_phase) * 0.3 + 0.7
            radius = 35 + pulse * 8

            # 外圈脉冲
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(255, 59, 48, int(60 * pulse))))
            painter.drawEllipse(QPointF(cx, cy), radius, radius)

            # 内圈
            painter.setBrush(QBrush(QColor(255, 59, 48, 220)))
            painter.drawEllipse(QPointF(cx, cy), 30, 30)

            # 停止图标 (方块)
            painter.setBrush(QBrush(QColor(255, 255, 255, 240)))
            painter.drawRect(cx - 12, cy - 12, 24, 24)
        else:
            # 空闲 — 蓝色
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(74, 108, 247, 220)))
            painter.drawEllipse(QPointF(cx, cy), 32, 32)

            # 麦克风图标 (圆形)
            painter.setBrush(QBrush(QColor(255, 255, 255, 240)))
            painter.drawEllipse(QPointF(cx, cy - 5), 10, 12)
            painter.drawRect(cx - 14, cy - 18, 28, 6)
            painter.drawRect(cx - 6, cy + 10, 12, 6)

        painter.end()


class EventCard(QFrame):
    """日程事件卡片。"""

    def __init__(self, event: CalendarEvent, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._event = event
        self.setFixedSize(400, 70)
        self.setStyleSheet(
            "QFrame {"
            "    background-color: #23272F;"
            "    border: 1px solid #2D323C;"
            "    border-radius: 10px;"
            "}"
            "QFrame:hover {"
            "    border-color: #4B5360;"
            "    background-color: #2D323C;"
            "}"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(12)

        # 时间
        time_label = QLabel(event.start_time.strftime("%H:%M"))
        time_label.setStyleSheet("color: #6B8AFF; font-size: 14px; font-weight: 600;")
        layout.addWidget(time_label)

        # 分割线
        divider = QFrame()
        divider.setFixedWidth(1)
        divider.setStyleSheet("background-color: #2D323C;")
        layout.addWidget(divider)

        # 标题
        title_label = QLabel(event.title)
        title_label.setStyleSheet("color: #E8EAED; font-size: 14px;")
        layout.addWidget(title_label, 1)

        # 日期标签
        date_label = QLabel(event.start_date.strftime("%m/%d"))
        date_label.setStyleSheet("color: #5F6B7A; font-size: 12px;")
        layout.addWidget(date_label)


class WorkerThread(QThread):
    """后台工作线程。"""

    started: pyqtSignal = pyqtSignal()
    finished: pyqtSignal = pyqtSignal(object)
    error: pyqtSignal = pyqtSignal(str)

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self._func = func
        self._args = args
        self._kwargs = kwargs

    def run(self):
        try:
            self.started.emit()
            result = self._func(*self._args, **self._kwargs)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class CentralWidget(QWidget):
    """中央内容容器 — 集成语音日历功能。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ContentArea")

        # 初始化服务
        self._pipeline = MockPipeline()  # 默认使用 Mock
        self._events: list[CalendarEvent] = []

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── 左侧边栏 ──
        sidebar = self._create_sidebar()
        main_layout.addWidget(sidebar, 0)

        # ── 主内容区 ──
        content = self._create_content()
        main_layout.addWidget(content, 1)

    def _create_sidebar(self) -> QFrame:
        """创建左侧边栏。"""
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(240)
        sidebar.setStyleSheet(
            "QFrame#Sidebar {"
            "    background-color: #23272F;"
            "    border-right: 1px solid #2D323C;"
            "}"
        )

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(20, 24, 20, 24)
        layout.setSpacing(12)

        # Logo
        logo = QLabel("\U0001f399️")
        logo.setStyleSheet("font-size: 28px;")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(logo)

        brand = QLabel(tr("VoiceCalendar"))
        brand.setStyleSheet("color: #E8EAED; font-size: 16px; font-weight: 700;")
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(brand)

        # 分割线
        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet("background-color: #2D323C;")
        layout.addWidget(divider)

        layout.addStretch()

        version = QLabel("v0.1.0")
        version.setStyleSheet("color: #5F6B7A; font-size: 11px;")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version)

        return sidebar

    def _create_content(self) -> QFrame:
        """创建主内容区。"""
        content = QFrame()
        content.setObjectName("MainContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(20)

        # ── 状态指示器 ──
        self._status_indicator = StatusIndicator()
        layout.addWidget(self._status_indicator)

        # ── 波形可视化 ──
        self._waveform = WaveformWidget()
        self._waveform.setFixedHeight(120)
        layout.addWidget(self._waveform)

        # ── 录音按钮 ──
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._record_btn = RecordButton()
        self._record_btn.recording_started.connect(self._on_recording_started)
        self._record_btn.recording_stopped.connect(self._on_recording_stopped)
        btn_layout.addWidget(self._record_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # ── 识别结果 ──
        self._result_label = QLabel("")
        self._result_label.setStyleSheet(
            "color: #E8EAED; font-size: 14px; padding: 12px;"
            "background-color: #23272F; border-radius: 8px;"
        )
        self._result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._result_label.setWordWrap(True)
        layout.addWidget(self._result_label)

        # ── 日程列表 ──
        list_header = QLabel(tr("今日日程"))
        list_header.setStyleSheet("color: #E8EAED; font-size: 16px; font-weight: 600;")
        layout.addWidget(list_header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none; background: transparent;")

        self._event_list = QFrame()
        self._event_layout = QVBoxLayout(self._event_list)
        self._event_layout.setSpacing(8)
        self._event_layout.addStretch()

        scroll.setWidget(self._event_list)
        layout.addWidget(scroll, 1)

        # 加载示例事件
        self._load_sample_events()

        return content

    def _load_sample_events(self) -> None:
        """加载示例事件。"""
        from datetime import date, time

        samples = [
            CalendarEvent(title="团队晨会", start_date=date.today(), start_time=time(9, 0)),
            CalendarEvent(title="产品评审", start_date=date.today(), start_time=time(14, 0)),
            CalendarEvent(title="代码审查", start_date=date.today(), start_time=time(16, 0)),
        ]

        for event in samples:
            card = EventCard(event)
            self._event_layout.insertWidget(0, card)
            self._events.append(event)

    def _on_recording_started(self) -> None:
        """录音开始。"""
        self._status_indicator.set_status("recording")
        self._waveform.set_recording(True)
        self._result_label.setText("")

    def _on_recording_stopped(self) -> None:
        """录音停止 — 触发处理流程。"""
        self._status_indicator.set_status("processing")
        self._waveform.set_recording(False)

        # 模拟处理 (实际项目中应在 QThread 中执行)
        QTimer.singleShot(500, self._process_voice)

    def _process_voice(self) -> None:
        """处理语音指令。"""
        result = self._pipeline.process_voice()

        if result.success and result.intent:
            self._status_indicator.set_status("success")
            self._result_label.setText(f"🎯 {result.raw_text}")

            if result.intent.is_add and result.intent.event:
                self._add_event(result.intent.event)
                self._toast("日程已添加 ✓", ToastType.SUCCESS)
            elif result.intent.is_query:
                self._toast("查询完成", ToastType.INFO)
            elif result.intent.is_delete:
                self._toast("已删除日程", ToastType.SUCCESS)
        else:
            self._status_indicator.set_status("error")
            self._toast("识别失败", ToastType.ERROR)

    def _add_event(self, event: CalendarEvent) -> None:
        """添加事件到列表。"""
        card = EventCard(event)
        self._event_layout.insertWidget(0, card)
        self._events.append(event)

    def _toast(self, message: str, toast_type: ToastType) -> None:
        """显示 Toast 通知。"""
        main_window = self.window()
        if isinstance(main_window, MainWindow):
            main_window.toast(message, toast_type)


class MainWindow(QMainWindow):
    """VoiceCalendar-Pro 主窗口。

    窗口特性:
    - 无边框 + 自定义圆角裁剪
    - 全局阴影效果
    - 自定义标题栏
    - 入场/出场动画
    - 主题切换
    """

    # Signal 定义
    theme_toggled: pyqtSignal = pyqtSignal(ThemeMode)

    def __init__(self) -> None:
        super().__init__()
        self._toast_manager: Optional[ToastManager] = None
        self._setup_window()
        self._setup_ui()
        self._apply_theme()

    def _setup_window(self) -> None:
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.resize(win_cfg.DEFAULT_WIDTH, win_cfg.DEFAULT_HEIGHT)
        self.setMinimumSize(win_cfg.MIN_WIDTH, win_cfg.MIN_HEIGHT)

        # 窗口标题
        self.setWindowTitle(tr("VoiceCalendar Pro"))

        # 圆角裁剪
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # 阴影
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(48)
        shadow.setOffset(win_cfg.SHADOW_OFFSET_X, win_cfg.SHADOW_OFFSET_Y)
        shadow.setColor(QColor(0, 0, 0, 60))
        self.setGraphicsEffect(shadow)

    def _setup_ui(self) -> None:
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
        theme_mgr = ThemeManager.instance()
        loader = ResourceLoader()

        loader.load_base_style()
        loader.load_theme_style("dark" if theme_mgr.is_dark() else "light")
        combined = loader.get_combined_style(theme_mgr.get_color_qss())
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

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 圆角路径
        path = QPainterPath()
        path.addRoundedRect(
            0, 0, self.width(), self.height(),
            win_cfg.CORNER_RADIUS, win_cfg.CORNER_RADIUS,
        )

        # 背景色
        theme_mgr = ThemeManager.instance()
        if theme_mgr.is_dark():
            bg_color = QColor(26, 29, 35)
        else:
            bg_color = QColor(255, 255, 255)

        # 裁剪 (使圆角外的区域透明)
        old_clip = painter.clipRegion()
        painter.setClipPath(path)
        painter.fillRect(path.boundingRect(), bg_color)
        painter.setClipRegion(old_clip)

        # 边框
        theme_colors = theme_mgr.colors
        painter.setStrokeStyle(Qt.PenStyle.SolidLine)
        painter.end()

    def changeEvent(self, event) -> None:  # type: ignore[override]
        """处理窗口最大化/还原状态变化。"""
        if event.spontaneous():
            window_state = self.windowState()
            is_max = bool(window_state & Qt.WindowType.WindowMaximized)
            self._titlebar.set_maximized(is_max)
        super().changeEvent(event)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        event.accept()
        super().closeEvent(event)

    def _close_window(self) -> None:
        self.close()


# ── tr() 国际化占位 ──

def tr(text: str) -> str:
    """翻译函数占位，后续接入 Qt 翻译系统。"""
    return text
