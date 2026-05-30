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
    pyqtSignal,
    pyqtSlot,
    QPointF,
    QPoint,
    QPropertyAnimation,
    QEasingCurve,
)
from PyQt6.QtGui import QColor, QPainter, QMouseEvent, QBrush, QIcon, QPixmap, QPixmapCache, QAction
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QLineEdit,
    QComboBox,
    QCheckBox,
    QSystemTrayIcon,
    QMenu,
    QDialog,
    QFormLayout,
    QTimeEdit,
    QDateEdit,
    QTextEdit,
    QSpinBox,
)

from voicecalendar.config import WindowConfig
from voicecalendar.core.theme import ThemeManager, ThemeMode
from voicecalendar.core.resources import ResourceLoader
from voicecalendar.ui.titlebar import TitleBar
from voicecalendar.ui.components.toast import ToastManager, ToastType
from voicecalendar.ui.widgets.waveform import WaveformWidget, StatusIndicator
from voicecalendar.ui.widgets.skeleton import CircularProgress
from voicecalendar.models.event import CalendarEvent
from voicecalendar.services.pipeline import VoiceCalendarPipeline, MockPipeline
from voicecalendar.services.audio_capture import AudioCapture
from voicecalendar.services.errors import get_user_message
from voicecalendar.services.calendar_backend import CalendarBackend
from voicecalendar.core import settings as settings_module

win_cfg = WindowConfig()


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
    """日程事件卡片 — 左侧颜色指示条 + 时间 + 标题 + 操作按钮。"""

    # 信号：编辑 / 删除
    edit_clicked: pyqtSignal = pyqtSignal(object)
    delete_clicked: pyqtSignal = pyqtSignal(object)

    EVENT_COLORS = [
        "#6B8AFF", "#3DDC84", "#FFB340",
        "#FF6B6B", "#7DD3FC", "#BB86FC",
    ]

    def __init__(self, event: CalendarEvent, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._event = event
        self.setFixedHeight(60)
        self.setMinimumHeight(60)
        self.setObjectName("EventCard")
        self.setStyleSheet(
            "QFrame#EventCard {"
            "    background-color: #23272F;"
            "    border: 1px solid #2D323C;"
            "    border-radius: 12px;"
            "}"
            "QFrame#EventCard:hover {"
            "    border-color: #4B5360;"
            "    background-color: #2A2F38;"
            "}"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 12, 16, 12)
        layout.setSpacing(14)

        # ── 颜色指示条 ──
        color = self.EVENT_COLORS[hash(event.title) % len(self.EVENT_COLORS)]
        indicator = QFrame()
        indicator.setFixedSize(3, 36)
        indicator.setStyleSheet(f"QFrame {{ background-color: {color}; border-radius: 2px; }}")
        layout.addWidget(indicator)

        # ── 时间区域 ──
        time_column = QVBoxLayout()
        time_column.setSpacing(2)

        time_label = QLabel(event.start_time.strftime("%H:%M"))
        time_label.setStyleSheet(f"color: {color}; font-size: 13px; font-weight: 700;")
        time_column.addWidget(time_label)

        if event.end_time:
            duration = (
                (event.start_date.toordinal() + event.start_time.hour * 24 + event.start_time.minute)
                - (event.end_date.toordinal() + event.end_time.hour * 24 + event.end_time.minute)
            )
            mins = abs(duration) * 60 if event.end_date == event.start_date else 60
            duration_label = QLabel(f"{mins}min")
            duration_label.setStyleSheet("color: #6B7280; font-size: 10px;")
            time_column.addWidget(duration_label)
        else:
            time_column.addStretch()

        time_column.addStretch()
        layout.addLayout(time_column, 0)

        # ── 分割线 ──
        divider = QFrame()
        divider.setFixedSize(1, 36)
        divider.setStyleSheet("background-color: #2D323C;")
        layout.addWidget(divider)

        # ── 标题 + 日期 ──
        title_container = QWidget()
        title_column = QVBoxLayout(title_container)
        title_column.setContentsMargins(0, 0, 0, 0)
        title_column.setSpacing(4)
        title_column.addStretch()

        title_label = QLabel(event.title)
        title_label.setStyleSheet("color: #E8EAED; font-size: 14px; font-weight: 500;")
        title_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        title_column.addWidget(title_label)

        # 日期徽章
        date_badge = QLabel(event.start_date.strftime("%m/%d"))
        date_badge.setStyleSheet(
            "color: #6B7280; font-size: 10px; font-weight: 600;"
            "background-color: rgba(128,128,128,0.1); padding: 2px 6px; border-radius: 4px;"
        )
        date_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_column.addWidget(date_badge)
        title_column.addStretch()

        layout.addWidget(title_container, 1)

        # ── 操作按钮组（编辑 + 删除）──
        btn_container = QWidget()
        btn_container.setFixedWidth(80)
        btn_layout = QHBoxLayout(btn_container)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(4)

        btn_style_on = (
            "QPushButton#CardBtn {"
            "    background-color: #6B8AFF;"
            "    border: none; border-radius: 4px;"
            "    color: #FFFFFF; font-size: 12px; padding: 4px 8px;"
            "}"
            "QPushButton#CardBtn:hover {"
            "    background-color: #8DA4FF;"
            "}"
            "QPushButton#CardBtn:pressed {"
            "    background-color: #4A6CF7;"
            "}"
        )
        btn_style_red = (
            "QPushButton#CardBtn {"
            "    background-color: #FF6B6B;"
            "    border: none; border-radius: 4px;"
            "    color: #FFFFFF; font-size: 12px; padding: 4px 8px;"
            "}"
            "QPushButton#CardBtn:hover {"
            "    background-color: #FF8A8A;"
            "}"
            "QPushButton#CardBtn:pressed {"
            "    background-color: #E04545;"
            "}"
        )

        # 初始隐藏按钮
        hover_style = """
            QFrame#EventCard:hover QPushButton#CardBtn {
                visibility: visible;
            }
        """

        btn_edit = QPushButton("编辑")
        btn_edit.setObjectName("CardBtn")
        btn_edit.setStyleSheet(btn_style_on)
        btn_edit.clicked.connect(lambda: self.edit_clicked.emit(self._event))
        btn_layout.addWidget(btn_edit)

        btn_delete = QPushButton("删除")
        btn_delete.setObjectName("CardBtn")
        btn_delete.setStyleSheet(btn_style_red)
        btn_delete.clicked.connect(lambda: self.delete_clicked.emit(self._event))
        btn_layout.addWidget(btn_delete)

        layout.addWidget(btn_container)


class EventEditDialog(QDialog):
    """编辑日程事件对话框。"""

    def __init__(self, event: CalendarEvent, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._event = event
        self.setWindowTitle("编辑日程")
        self.setMinimumWidth(400)
        # 深色背景
        self.setStyleSheet(
            "QDialog { background-color: #1E222A; }"
            "QLabel { color: #E8EAED; font-size: 13px; }"
            "QLineEdit, QComboBox, QSpinBox, QDateEdit, QTimeEdit, QTextEdit {"
            "    background-color: #2D323C; border: 1px solid #363C47;"
            "    border-radius: 6px; color: #E8EAED; padding: 6px 10px;"
            "    font-size: 13px;"
            "}"
            "QLineEdit:focus, QComboBox:focus, QSpinBox:focus,"
            "QDateEdit:focus, QTimeEdit:focus, QTextEdit:focus {"
            "    border-color: #6B8AFF;"
            "}"
            "QTextEdit { min-height: 60px; }"
            "QSpinBox::up-button, QTimeEdit::up-button, QDateEdit::up-button {"
            "    background-color: #363C47; border: none;"
            "}"
            "QSpinBox::down-button, QTimeEdit::down-button, QDateEdit::down-button {"
            "    background-color: #2D323C; border: none;"
            "}"
            "QComboBox::drop-down { border: none; }"
            "QComboBox QAbstractItemView {"
            "    background-color: #2D323C; color: #E8EAED;"
            "    selection-background-color: #6B8AFF;"
            "    border: 1px solid #363C47;"
            "}"
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # 表单
        form = QFormLayout()
        form.setSpacing(12)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        # 标题
        self._title_input = QLineEdit(event.title)
        self._title_input.setStyleSheet(
            "QLineEdit { background-color: #2D323C; border: 1px solid #363C47;"
            "border-radius: 6px; color: #E8EAED; padding: 6px 10px; font-size: 14px; font-weight: 600; }"
            "QLineEdit:focus { border-color: #6B8AFF; }"
        )
        form.addRow("标题:", self._title_input)

        # 开始日期
        self._start_date = QDateEdit()
        self._start_date.setCalendarPopup(True)
        self._start_date.setDisplayFormat("yyyy-MM-dd")
        self._start_date.setDate(event.start_date)
        form.addRow("开始日期:", self._start_date)

        # 开始时间
        self._start_time = QTimeEdit()
        self._start_time.setDisplayFormat("HH:mm")
        self._start_time.setTime(event.start_time)
        form.addRow("开始时间:", self._start_time)

        # 结束日期
        self._end_date = QDateEdit()
        self._end_date.setCalendarPopup(True)
        self._end_date.setDisplayFormat("yyyy-MM-dd")
        self._end_date.setDate(event.end_date or event.start_date)
        form.addRow("结束日期:", self._end_date)

        # 结束时间
        self._end_time = QTimeEdit()
        self._end_time.setDisplayFormat("HH:mm")
        default_end = event.end_time or event.start_time
        self._end_time.setTime(default_end)
        form.addRow("结束时间:", self._end_time)

        # 地点
        self._location_input = QLineEdit(event.location)
        self._location_input.setPlaceholderText("可选")
        form.addRow("地点:", self._location_input)

        # 描述
        self._desc_input = QTextEdit(event.description)
        self._desc_input.setMaximumHeight(80)
        self._desc_input.setPlaceholderText("可选")
        form.addRow("描述:", self._desc_input)

        # 提醒
        self._reminder_spin = QSpinBox()
        self._reminder_spin.setRange(0, 1440)
        self._reminder_spin.setValue(event.reminder_minutes)
        self._reminder_spin.setSuffix(" 分钟前")
        form.addRow("提醒:", self._reminder_spin)

        layout.addLayout(form)

        # 按钮行
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.setFixedWidth(80)
        cancel_btn.setStyleSheet(
            "QPushButton { background-color: #2D323C; border: 1px solid #363C47;"
            "border-radius: 6px; color: #E8EAED; padding: 8px 16px; font-size: 13px; }"
            "QPushButton:hover { background-color: #363C47; }"
        )
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton("保存")
        save_btn.setFixedWidth(80)
        save_btn.setStyleSheet(
            "QPushButton { background-color: #6B8AFF; border: none;"
            "border-radius: 6px; color: #FFFFFF; padding: 8px 16px;"
            "font-size: 13px; font-weight: 600; }"
            "QPushButton:hover { background-color: #8DA4FF; }"
            "QPushButton:pressed { background-color: #4A6CF7; }"
        )
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)

        layout.addLayout(btn_row)

    def _save(self) -> None:
        """保存修改后的数据回 self._event。"""
        title = self._title_input.text().strip()
        if not title:
            title = self._event.title  # 空则保留原值

        self._event.title = title
        self._event.start_date = self._start_date.date().toPyDate()
        self._event.start_time = self._start_time.time().toPyTime()
        self._event.end_date = self._end_date.date().toPyDate()
        self._event.end_time = self._end_time.time().toPyTime()
        self._event.location = self._location_input.text().strip()
        self._event.description = self._desc_input.toPlainText().strip()
        self._event.reminder_minutes = self._reminder_spin.value()

        self.accept()


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
    """中央内容容器 — 左侧导航 + 右侧多页面切换。

    页面索引:
        0 = 📅 日程 (SchedulePage)
        1 = 🎙 语音 (VoicePage)
        2 = 📊 统计 (StatsPage)
        3 = ⚙ 设置 (SettingsPage)
    """

    # 页面索引常量
    PAGE_SCHEDULE = 0
    PAGE_VOICE = 1
    PAGE_STATS = 2
    PAGE_SETTINGS = 3

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ContentArea")

        # 初始化服务 — 从设置加载配置，有 API Key 则用真实服务，否则降级 Mock
        self._events: list[CalendarEvent] = []
        self._audio_capture: AudioCapture | None = None
        self._recording_active: bool = False  # 跟踪真实录音是否启动
        self._worker: Optional[WorkerThread] = None  # 后台工作线程（持有引用防 GC）
        self._calendar = CalendarBackend()
        self._init_pipeline()

        # 水平布局：左侧边栏 + 右侧 QStackedWidget
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── 左侧边栏 ──
        sidebar = self._create_sidebar()
        main_layout.addWidget(sidebar)

        # ── 右侧页面堆叠 ──
        self._stack = QStackedWidget()
        self._stack.setStyleSheet("QStackedWidget { background: transparent; }")

        self._schedule_page = self._create_schedule_page()
        self._voice_page = self._create_voice_page()
        self._stats_page = self._create_stats_page()
        self._settings_page = self._create_settings_page()

        self._stack.addWidget(self._schedule_page)
        self._stack.addWidget(self._voice_page)
        self._stack.addWidget(self._stats_page)
        self._stack.addWidget(self._settings_page)

        # 默认显示日程页
        self._stack.setCurrentIndex(self.PAGE_SCHEDULE)

        main_layout.addWidget(self._stack, 1)

        # 连接音频 RMS 到波形可视化（在页面创建后）
        self._setup_rms_callback()

        # 加载示例事件
        self._load_sample_events()

    def _init_pipeline(self) -> None:
        """初始化处理流水线 — 有 API Key 用真实服务，否则 Mock 降级。"""
        asr_cfg = settings_module.get_asr_config()
        nlu_cfg = settings_module.get_nlu_config()

        api_key = asr_cfg.get("api_key", "") or nlu_cfg.get("api_key", "")
        base_url = asr_cfg.get("base_url", "") or nlu_cfg.get("base_url", "")

        if api_key:
            self._pipeline = VoiceCalendarPipeline(
                api_key=api_key,
                base_url=base_url or "https://api.openai.com/v1",
                whisper_model=asr_cfg.get("model", "whisper-1"),
                llm_model=nlu_cfg.get("model", "gpt-4o"),
            )
            self._audio_capture = AudioCapture()
        else:
            self._pipeline = MockPipeline()
            self._audio_capture = None
            import logging
            logging.getLogger("voicecalendar").info(
                "API Key 未配置，使用 Mock 模式。请在设置页面配置 ASR/LLM API Key"
            )

    def _setup_rms_callback(self) -> None:
        """连接音频 RMS 数据到波形可视化（在波形创建后调用）。"""
        if self._audio_capture is not None and hasattr(self, "_waveform"):
            self._audio_capture.set_rms_callback(self._on_audio_rms)

    def _on_audio_rms(self, rms: float) -> None:
        """音频 RMS 数据回调 — 更新波形可视化。"""
        if hasattr(self, "_waveform"):
            self._waveform.set_rms_level(min(rms / 32768.0, 1.0))

    def reload_pipeline(self) -> None:
        """重新加载流水线（设置变更后调用）。"""
        self._init_pipeline()
        self._setup_rms_callback()
        # 更新状态指示灯
        asr_cfg = settings_module.get_asr_config()
        has_key = bool(asr_cfg.get("api_key", ""))
        if has_key:
            self._status_dot.setStyleSheet("color: #3DDC84; font-size: 8px;")
            self._status_dot.setToolTip("服务已连接")
        else:
            self._status_dot.setStyleSheet("color: #FFB340; font-size: 8px;")
            self._status_dot.setToolTip("Mock 模式 — 请在设置中配置 API Key")

    # ── 导航切换 ──

    def switch_page(self, index: int) -> None:
        """切换到指定页面。"""
        self._stack.setCurrentIndex(index)
        for i, btn in enumerate(self._nav_buttons):
            btn.setChecked(i == index)

    # ── 侧边栏 ──

    def _create_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(72)
        sidebar.setStyleSheet(
            "QFrame#Sidebar {"
            "    background-color: #1E222A;"
            "    border: none;"
            "    border-right: 1px solid #2D323C;"
            "}"
        )

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Logo
        logo_container = QFrame()
        logo_container.setFixedHeight(64)
        logo_layout = QVBoxLayout(logo_container)
        logo_layout.setContentsMargins(0, 12, 0, 0)
        logo_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        logo = QLabel("🎙")
        logo.setStyleSheet("font-size: 24px;")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_layout.addWidget(logo)
        layout.addWidget(logo_container)

        # 导航按钮
        nav_container = QFrame()
        nav_layout = QVBoxLayout(nav_container)
        nav_layout.setContentsMargins(8, 12, 8, 12)
        nav_layout.setSpacing(4)

        nav_items = [
            ("📅", "日程", self.PAGE_SCHEDULE),
            ("🎙", "语音", self.PAGE_VOICE),
            ("📊", "统计", self.PAGE_STATS),
            ("⚙", "设置", self.PAGE_SETTINGS),
        ]

        self._nav_buttons: list[QPushButton] = []
        for icon, label, page_idx in nav_items:
            btn = QPushButton(icon)
            btn.setFixedHeight(48)
            btn.setCheckable(True)
            btn.setObjectName("NavButton")
            btn.setToolTip(label)
            btn.setStyleSheet(
                "QPushButton#NavButton {"
                "    background-color: transparent;"
                "    border: none;"
                "    border-radius: 10px;"
                "    font-size: 20px;"
                "    padding: 0;"
                "}"
                "QPushButton#NavButton:hover {"
                "    background-color: rgba(255, 255, 255, 0.06);"
                "}"
                "QPushButton#NavButton:checked {"
                "    background-color: rgba(107, 138, 255, 0.15);"
                "}"
            )
            btn.clicked.connect(lambda checked, idx=page_idx: self.switch_page(idx))
            nav_layout.addWidget(btn)
            self._nav_buttons.append(btn)

        self._nav_buttons[0].setChecked(True)
        layout.addWidget(nav_container)
        layout.addStretch()

        # 底部状态指示灯
        version_container = QFrame()
        version_layout = QVBoxLayout(version_container)
        version_layout.setContentsMargins(0, 8, 0, 12)
        version_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._status_dot = QLabel("●")
        # 根据配置状态设置颜色：绿色 = API 已配置，黄色 = Mock 模式
        asr_cfg = settings_module.get_asr_config()
        has_api_key = bool(asr_cfg.get("api_key", ""))
        if has_api_key:
            self._status_dot.setStyleSheet("color: #3DDC84; font-size: 8px;")
            self._status_dot.setToolTip("服务已连接")
        else:
            self._status_dot.setStyleSheet("color: #FFB340; font-size: 8px;")
            self._status_dot.setToolTip("Mock 模式 — 请在设置中配置 API Key")
        self._status_dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_layout.addWidget(self._status_dot)
        layout.addWidget(version_container)

        return sidebar

    # ═══════════════════════════════════════════
    # 页面 0: 日程列表
    # ═══════════════════════════════════════════

    def _create_schedule_page(self) -> QFrame:
        page = QFrame()
        page.setStyleSheet("QFrame { background: transparent; }")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        # 标题
        header = QHBoxLayout()
        title = QLabel("今日日程")
        title.setStyleSheet("color: #E8EAED; font-size: 18px; font-weight: 700;")
        header.addWidget(title)
        today_str = date.today().strftime("%Y/%m/%d")
        today_label = QLabel(today_str)
        today_label.setStyleSheet("color: #6B8AFF; font-size: 13px; font-weight: 600; margin-left: 8px;")
        header.addWidget(today_label)
        header.addStretch()
        layout.addLayout(header)

        # 分隔线
        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet("background-color: #2D323C;")
        layout.addWidget(divider)

        # 事件列表
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self._event_container = QFrame()
        self._event_container.setStyleSheet("background: transparent;")
        self._event_layout = QVBoxLayout(self._event_container)
        self._event_layout.setContentsMargins(0, 0, 0, 0)
        self._event_layout.setSpacing(8)
        self._event_layout.addStretch()
        scroll.setWidget(self._event_container)
        layout.addWidget(scroll, 1)

        # 空状态
        self._empty_label = QLabel("暂无日程，切换到「语音」页面添加")
        self._empty_label.setStyleSheet("color: #6B7280; font-size: 14px;")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._event_layout.insertWidget(0, self._empty_label)

        return page

    # ═══════════════════════════════════════════
    # 页面 1: 语音交互
    # ═══════════════════════════════════════════

    def _create_voice_page(self) -> QFrame:
        page = QFrame()
        page.setStyleSheet("QFrame { background: transparent; }")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(20)

       # 配置状态提示
        asr_cfg = settings_module.get_asr_config()
        has_api_key = bool(asr_cfg.get("api_key", ""))

        if has_api_key:
            hint = QLabel("点击麦克风按钮开始语音输入")
            hint.setStyleSheet("color: #3DDC84; font-size: 13px;")
        else:
            hint = QLabel("⚠️ Mock 模式 — 点击「设置」⚙ 配置 API Key 启用真实语音识别")
            hint.setStyleSheet("color: #FFB340; font-size: 12px;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

        # 语音卡片
        voice_card = QFrame()
        voice_card.setObjectName("VoiceSection")
        voice_card.setStyleSheet(
            "QFrame#VoiceSection {"
            "    background-color: #1E222A;"
            "    border-radius: 16px;"
            "    border: 1px solid #2D323C;"
            "}"
        )
        voice_layout = QVBoxLayout(voice_card)
        voice_layout.setContentsMargins(24, 20, 24, 20)
        voice_layout.setSpacing(16)

        # 状态指示器
        h_layout = QHBoxLayout()
        h_layout.addStretch()
        self._status_indicator = StatusIndicator()
        h_layout.addWidget(self._status_indicator)
        h_layout.addStretch()
        voice_layout.addLayout(h_layout)

        # 波形
        wf_container = QFrame()
        wf_container.setFixedHeight(140)
        wf_container.setStyleSheet("background: transparent;")
        wf_layout = QVBoxLayout(wf_container)
        wf_layout.setContentsMargins(0, 0, 0, 0)
        self._waveform = WaveformWidget()
        self._waveform.setObjectName("WaveformWidget")
        wf_layout.addWidget(self._waveform)
        voice_layout.addWidget(wf_container, 1)
        voice_layout.addStretch()
        layout.addWidget(voice_card, 1)

        # 识别结果
        self._result_label = QLabel("")
        self._result_label.setObjectName("ResultLabel")
        self._result_label.setStyleSheet(
            "QLabel#ResultLabel {"
            "    color: #9AA0A8; font-size: 13px; padding: 0;"
            "    background-color: transparent;"
            "}"
        )
        self._result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._result_label.setWordWrap(True)
        layout.addWidget(self._result_label, 0)

        # 录音按钮
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._record_btn = RecordButton()
        self._record_btn.recording_started.connect(self._on_recording_started)
        self._record_btn.recording_stopped.connect(self._on_recording_stopped)
        btn_row.addWidget(self._record_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        return page

    # ═══════════════════════════════════════════
    # 页面 2: 统计
    # ═══════════════════════════════════════════

    def _create_stats_page(self) -> QFrame:
        page = QFrame()
        page.setStyleSheet("QFrame { background: transparent; }")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(20)

        title = QLabel("使用统计")
        title.setStyleSheet("color: #E8EAED; font-size: 18px; font-weight: 700;")
        layout.addWidget(title)

        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet("background-color: #2D323C;")
        layout.addWidget(divider)

        # 统计卡片
        stats_data = [
            ("📅", "今日日程", "3", "个事件"),
            ("📆", "本周日程", "12", "个事件"),
            ("🎤", "语音识别", "0", "次"),
            ("✅", "识别成功率", "100", "%"),
        ]

        for icon, label, value, unit in stats_data:
            card = self._create_stat_card(icon, label, value, unit)
            layout.addWidget(card)

        layout.addStretch()
        return page

    @staticmethod
    def _create_stat_card(icon: str, label: str, value: str, unit: str) -> QFrame:
        card = QFrame()
        card.setFixedHeight(64)
        card.setStyleSheet(
            "QFrame {"
            "    background-color: #23272F;"
            "    border: 1px solid #2D323C;"
            "    border-radius: 12px;"
            "}"
        )
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(20, 0, 20, 0)
        card_layout.setSpacing(16)

        # 图标
        icon_label = QLabel(icon)
        icon_label.setStyleSheet("font-size: 24px;")
        card_layout.addWidget(icon_label)

        # 信息
        info_layout = QVBoxLayout()
        info_layout.addStretch()
        val_layout = QHBoxLayout()
        val_layout.setSpacing(4)
        val = QLabel(value)
        val.setStyleSheet("color: #E8EAED; font-size: 18px; font-weight: 700;")
        unit_l = QLabel(unit)
        unit_l.setStyleSheet("color: #6B7280; font-size: 12px;")
        val_layout.addWidget(val)
        val_layout.addWidget(unit_l)
        val_layout.addStretch()
        info_layout.addLayout(val_layout)

        desc = QLabel(label)
        desc.setStyleSheet("color: #9AA0A8; font-size: 12px;")
        info_layout.addWidget(desc)
        info_layout.addStretch()
        card_layout.addLayout(info_layout, 1)

        card_layout.addStretch()
        return card

    # ═══════════════════════════════════════════
    # 页面 3: 设置
    # ═══════════════════════════════════════════

    def _create_settings_page(self) -> QFrame:
        page = QFrame()
        page.setStyleSheet("QFrame { background: transparent; }")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(20)

        title = QLabel("设置")
        title.setStyleSheet("color: #E8EAED; font-size: 18px; font-weight: 700;")
        layout.addWidget(title)

        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet("background-color: #2D323C;")
        layout.addWidget(divider)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        settings_container = QFrame()
        settings_container.setStyleSheet("background: transparent;")
        settings_layout = QVBoxLayout(settings_container)
        settings_layout.setContentsMargins(0, 0, 0, 0)
        settings_layout.setSpacing(20)

        # 加载当前配置
        asr_cfg = settings_module.get_asr_config()
        nlu_cfg = settings_module.get_nlu_config()

        # ── ASR 配置 ──
        asr_section = self._create_api_section(
            "🎤 语音识别 (ASR)",
            asr_cfg,
        )
        settings_layout.addWidget(asr_section)

        # ── LLM 配置 ──
        nlu_section = self._create_api_section(
            "🧠 意图解析 (LLM)",
            nlu_cfg,
        )
        settings_layout.addWidget(nlu_section)

        # ── 界面配置 ──
        ui_section = self._create_ui_section()
        settings_layout.addWidget(ui_section)

        # ── 保存按钮 ──
        save_btn = QPushButton("保存设置")
        save_btn.setFixedHeight(42)
        save_btn.setStyleSheet(
            "QPushButton {"
            "    background-color: #6B8AFF;"
            "    border: none;"
            "    border-radius: 8px;"
            "    color: #FFFFFF;"
            "    font-size: 14px;"
            "    font-weight: 600;"
            "}"
            "QPushButton:hover {"
            "    background-color: #8DA4FF;"
            "}"
            "QPushButton:pressed {"
            "    background-color: #4A6CF7;"
            "}"
        )
        save_btn.clicked.connect(self._save_settings)
        settings_layout.addWidget(save_btn)

        # 状态提示
        self._settings_status = QLabel("")
        self._settings_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._settings_status.setStyleSheet("color: #6B7280; font-size: 12px;")
        settings_layout.addWidget(self._settings_status)

        settings_layout.addStretch()
        scroll.setWidget(settings_container)
        layout.addWidget(scroll, 1)

        return page

    def _create_api_section(
        self,
        title: str,
        config: dict[str, str],
    ) -> QFrame:
        """创建 API 配置卡片。"""
        card = QFrame()
        card.setStyleSheet(
            "QFrame {"
            "    background-color: #23272F;"
            "    border: 1px solid #2D323C;"
            "    border-radius: 12px;"
            "}"
        )
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 16, 20, 16)
        card_layout.setSpacing(12)

        sec_title = QLabel(title)
        sec_title.setStyleSheet("color: #E8EAED; font-size: 14px; font-weight: 600;")
        card_layout.addWidget(sec_title)

        # API Key
        key_row = QHBoxLayout()
        key_row.setSpacing(12)
        key_label = QLabel("API Key")
        key_label.setStyleSheet("color: #9AA0A8; font-size: 13px; min-width: 70px;")
        key_row.addWidget(key_label)

        key_input = QLineEdit()
        key_input.setObjectName(f"{title}_api_key")
        key_input.setText(config.get("api_key", ""))
        key_input.setPlaceholderText("sk-xxx (留空则读取环境变量 OPENAI_API_KEY)")
        key_input.setEchoMode(QLineEdit.EchoMode.Password)
        key_input.setStyleSheet(self._input_style())
        key_row.addWidget(key_input, 1)
        card_layout.addLayout(key_row)

        # Base URL
        url_row = QHBoxLayout()
        url_row.setSpacing(12)
        url_label = QLabel("Base URL")
        url_label.setStyleSheet("color: #9AA0A8; font-size: 13px; min-width: 70px;")
        url_row.addWidget(url_label)

        url_input = QLineEdit()
        url_input.setObjectName(f"{title}_base_url")
        url_input.setText(config.get("base_url", ""))
        url_input.setPlaceholderText("https://api.openai.com/v1")
        url_input.setStyleSheet(self._input_style())
        url_row.addWidget(url_input, 1)
        card_layout.addLayout(url_row)

        # 模型
        model_row = QHBoxLayout()
        model_row.setSpacing(12)
        model_label = QLabel("模型")
        model_label.setStyleSheet("color: #9AA0A8; font-size: 13px; min-width: 70px;")
        model_row.addWidget(model_label)

        model_combo = QComboBox()
        model_combo.setObjectName(f"{title}_model")
        if "ASR" in title:
            # 根据配置中的 Base URL 判断模型列表
            url = config.get("base_url", "").lower()
            if "dashscope" in url:
                models = [
                    "qwen3-asr-flash",
                    "whisper-1",
                    "whisper-large",
                ]
            else:
                models = [
                    "whisper-1",
                    "whisper-large",
                    "whisper-medium",
                ]
        else:
            url = config.get("base_url", "").lower()
            if "dashscope" in url:
                models = [
                    "qwen-turbo",
                    "gpt-4o",
                    "gpt-4o-mini",
                    "qwen3.6-flash"
                ]
            else:
                models = [
                    "gpt-4o",
                    "gpt-4o-mini",
                    "gpt-4",
                    "gpt-3.5-turbo",
                ]
        for m in models:
            model_combo.addItem(m)
        current = config.get("model", "")
        if current:
            idx = model_combo.findText(current)
            if idx >= 0:
                model_combo.setCurrentIndex(idx)
        model_combo.setStyleSheet(self._combo_style())
        model_row.addWidget(model_combo, 1)
        card_layout.addLayout(model_row)

        # 连接状态指示
        status_row = QHBoxLayout()
        status_row.addStretch()
        status_dot = QLabel("●")
        status_dot.setStyleSheet("color: #FFB340; font-size: 10px;")
        status_row.addWidget(status_dot)
        status_text = QLabel("未验证")
        status_text.setStyleSheet("color: #6B7280; font-size: 11px;")
        status_row.addWidget(status_text)
        card_layout.addLayout(status_row)

        return card

    @staticmethod
    def _input_style() -> str:
        return (
            "QLineEdit {"
            "    background-color: #2D323C;"
            "    border: 1px solid #363C47;"
            "    border-radius: 6px;"
            "    padding: 6px 10px;"
            "    color: #E8EAED;"
            "    font-size: 13px;"
            "}"
            "QLineEdit:focus {"
            "    border-color: #6B8AFF;"
            "}"
        )

    @staticmethod
    def _combo_style() -> str:
        return (
            "QComboBox {"
            "    background-color: #2D323C;"
            "    border: 1px solid #363C47;"
            "    border-radius: 6px;"
            "    padding: 6px 10px;"
            "    color: #E8EAED;"
            "    font-size: 13px;"
            "}"
            "QComboBox:focus {"
            "    border-color: #6B8AFF;"
            "}"
            "QComboBox::drop-down { border: none; }"
            "QComboBox QAbstractItemView {"
            "    background-color: #2D323C;"
            "    color: #E8EAED;"
            "    selection-background-color: #6B8AFF;"
            "    border: 1px solid #363C47;"
            "}"
        )

    def _create_ui_section(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet(
            "QFrame {"
            "    background-color: #23272F;"
            "    border: 1px solid #2D323C;"
            "    border-radius: 12px;"
            "}"
        )
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 16, 20, 16)
        card_layout.setSpacing(12)

        sec_title = QLabel("🎨 界面")
        sec_title.setStyleSheet("color: #E8EAED; font-size: 14px; font-weight: 600;")
        card_layout.addWidget(sec_title)

        theme_row = QHBoxLayout()
        theme_row.setSpacing(12)

        theme_label = QLabel("深色模式")
        theme_label.setStyleSheet("color: #E8EAED; font-size: 13px;")
        theme_row.addWidget(theme_label)
        theme_row.addStretch()

        self._theme_toggle = QCheckBox()
        self._theme_toggle.setChecked(settings_module.get_dark_mode())
        self._theme_toggle.setStyleSheet(
            "QCheckBox::indicator {"
            "    width: 40px; height: 22px;"
            "    border-radius: 11px;"
            "    background-color: #2D323C;"
            "}"
            "QCheckBox::indicator:checked {"
            "    background-color: #6B8AFF;"
            "}"
            "QCheckBox { color: #E8EAED; font-size: 13px; }"
        )
        self._theme_toggle.toggled.connect(self._on_theme_toggled)
        theme_row.addWidget(self._theme_toggle)
        card_layout.addLayout(theme_row)

        return card

    def _save_settings(self) -> None:
        """保存设置到本地文件。"""
        settings_data = settings_module.load_settings()

        # 收集 ASR 配置
        for child in self._settings_page.findChildren(QLineEdit):
            if "ASR" in child.objectName() and "api_key" in child.objectName():
                settings_data["asr"]["api_key"] = child.text()
            elif "ASR" in child.objectName() and "base_url" in child.objectName():
                settings_data["asr"]["base_url"] = child.text()
        for child in self._settings_page.findChildren(QComboBox):
            if "ASR" in child.objectName() and "model" in child.objectName():
                settings_data["asr"]["model"] = child.currentText()

        # 收集 NLU 配置
        for child in self._settings_page.findChildren(QLineEdit):
            if "LLM" in child.objectName() and "api_key" in child.objectName():
                settings_data["nlu"]["api_key"] = child.text()
            elif "LLM" in child.objectName() and "base_url" in child.objectName():
                settings_data["nlu"]["base_url"] = child.text()
        for child in self._settings_page.findChildren(QComboBox):
            if "LLM" in child.objectName() and "model" in child.objectName():
                settings_data["nlu"]["model"] = child.currentText()

        # 界面配置
        settings_data["ui"]["dark_mode"] = self._theme_toggle.isChecked()

        settings_module.save_settings(settings_data)

        # 重新加载流水线（应用新配置）
        self.reload_pipeline()

        # 更新状态指示灯颜色
        asr_cfg = settings_module.get_asr_config()
        has_key = bool(asr_cfg.get("api_key", ""))
        status_dot = self._settings_page.findChild(QLabel, "status_dot")
        if has_key:
            self._settings_status.setText("✅ 设置已保存，服务就绪")
            self._settings_status.setStyleSheet("color: #3DDC84; font-size: 12px;")
            self._toast("设置已保存，语音识别已启用", ToastType.SUCCESS)
        else:
            self._settings_status.setText("✅ 设置已保存（Mock 模式）")
            self._settings_status.setStyleSheet("color: #FFB340; font-size: 12px;")
            self._toast("设置已保存（未配置 API Key，使用 Mock 模式）", ToastType.WARNING)

        # 3 秒后清除提示
        QTimer.singleShot(3000, lambda: self._settings_status.setText(""))

    def _on_theme_toggled(self, checked: bool) -> None:
        """主题切换回调。"""
        main_window = self.window()
        if isinstance(main_window, MainWindow):
            theme_mgr = ThemeManager.instance()
            mode = ThemeMode.DARK if checked else ThemeMode.LIGHT
            theme_mgr.set_mode(mode)

    # ═══════════════════════════════════════════
    # 业务逻辑方法
    # ═══════════════════════════════════════════

    def _create_card(self, event: CalendarEvent) -> EventCard:
        """创建带信号连接的 EventCard。"""
        card = EventCard(event)
        card.edit_clicked.connect(self._on_edit_event)
        card.delete_clicked.connect(self._on_delete_event)
        return card

    def _load_sample_events(self) -> None:
        """加载事件到日程页面 — 优先从 CalendarBackend 读取持久化数据，没有才加载示例。"""
        from datetime import date, time

        # 1. 尝试从 ICS 文件加载已有事件
        saved_events = self._calendar.load_events()

        if saved_events:
            saved_events.sort(key=lambda e: (e.start_date, e.start_time))
            for event in saved_events:
                card = self._create_card(event)
                self._event_layout.insertWidget(0, card)
                self._events.append(event)
        else:
            samples = [
                CalendarEvent(title="团队晨会", start_date=date.today(), start_time=time(9, 0)),
                CalendarEvent(title="产品评审", start_date=date.today(), start_time=time(14, 0)),
                CalendarEvent(title="代码审查", start_date=date.today(), start_time=time(16, 0)),
            ]
            for event in samples:
                card = self._create_card(event)
                self._event_layout.insertWidget(0, card)
                self._events.append(event)
            self._calendar.create_ics_file(samples)

        # 隐藏空状态提示
        if self._empty_label.isVisible():
            self._empty_label.hide()

    def _on_recording_started(self) -> None:
        """录音开始 — 启动音频捕获。"""
        self._status_indicator.set_status("recording")
        self._waveform.set_recording(True)
        self._result_label.setText("")
        self._result_label.setStyleSheet(
            "QLabel#ResultLabel { color: #9AA0A8; font-size: 13px; padding: 0; background-color: transparent; }"
        )

        if self._audio_capture is not None:
            try:
                self._audio_capture.start()
                self._recording_active = True
                self._status_indicator.set_status("recording", "正在录音，再次点击停止...")
            except Exception as e:
                import logging
                logging.getLogger("voicecalendar").error("录音启动失败: %s", e)
                self._status_indicator.set_status("error", f"录音失败: {e}")
                self._toast(f"录音失败: {e}", ToastType.ERROR)
                self._waveform.set_recording(False)
                self._record_btn.set_recording(False)
        else:
            self._recording_active = False
            self._status_indicator.set_status("recording", "Mock 模式 — 正在模拟录音...")

    def _on_recording_stopped(self) -> None:
        """录音停止 — 停止捕获，开始处理流程。"""
        self._waveform.set_recording(False)

        if self._recording_active and self._audio_capture is not None and self._audio_capture.is_recording:
            self._recording_active = False
            self._status_indicator.set_status("processing", "正在识别...")
            try:
                wav_path = self._audio_capture.stop()
                self._result_label.setText("🎤 录音完成，正在识别...")
                self._result_label.setStyleSheet(
                    "QLabel#ResultLabel { color: #FFB340; font-size: 13px; padding: 0; background-color: transparent; }"
                )
                # 后台线程处理（ASR → NLU → 日历）— 持有引用防 GC
                if self._worker and self._worker.isRunning():
                    self._worker.quit()
                    self._worker.wait(500)
                self._worker = WorkerThread(self._process_audio_file, str(wav_path))
                self._worker.started.connect(
                    lambda: self._status_indicator.set_status("processing", "正在识别...")
                )
                self._worker.finished.connect(self._on_pipeline_result)
                self._worker.error.connect(self._on_pipeline_error)
                self._worker.start()
            except Exception as e:
                import logging
                logging.getLogger("voicecalendar").error("录音停止失败: %s", e)
                self._status_indicator.set_status("error", f"录音失败: {e}")
                self._toast(f"录音失败: {e}", ToastType.ERROR)
        else:
            # Mock 模式：模拟延迟后返回预设结果
            self._status_indicator.set_status("processing", "Mock 模式 — 正在模拟识别...")
            self._result_label.setText("🎤 Mock 模式 — 正在模拟识别...")
            self._result_label.setStyleSheet(
                "QLabel#ResultLabel { color: #FFB340; font-size: 13px; padding: 0; background-color: transparent; }"
            )
            QTimer.singleShot(1500, self._process_mock)

    def _process_audio_file(self, wav_path: str):
        """处理录音文件 — ASR → NLU → 日历。"""
        asr_cfg = settings_module.get_asr_config()
        nlu_cfg = settings_module.get_nlu_config()

        asr_base_url = asr_cfg.get("base_url", "").lower()
        asr_model = asr_cfg.get("model", "whisper-1")

        # 1. ASR 识别 — 根据 Base URL 选择 ASR 服务
        if "dashscope" in asr_base_url:
            # DashScope Qwen-ASR（qwen3-asr-flash）
            from voicecalendar.services.asr_dashscope import DashScopeASR
            if not asr_model:
                asr_model = "qwen3-asr-flash"
            asr = DashScopeASR(api_key=asr_cfg.get("api_key", ""), model=asr_model)
            trans_result = asr.transcribe(wav_path)
            if not trans_result.success:
                raise Exception(trans_result.error_message)
            text = trans_result.text.strip()
        else:
            # OpenAI Whisper API
            from voicecalendar.services.asr_service import ASRService
            asr = ASRService(
                api_key=asr_cfg.get("api_key", ""),
                base_url=asr_cfg.get("base_url", ""),
                model=asr_model,
            )
            trans_result = asr.transcribe(wav_path)
            if not trans_result.success:
                raise Exception(trans_result.error_message)
            text = trans_result.text.strip()

        if not text:
            raise Exception("未识别到有效语音内容")

        # 2. NLU 意图解析
        from voicecalendar.services.nlu_parser import NLUParser
        nlu = NLUParser(
            api_key=nlu_cfg.get("api_key", ""),
            base_url=nlu_cfg.get("base_url", ""),
            model=nlu_cfg.get("model", "gpt-4o"),
        )
        intent = nlu.parse(text)

        # 3. 日历操作
        calendar = self._calendar
        if intent.is_add and intent.event:
            calendar_result = calendar.add_event(intent.event)
        elif intent.is_delete:
            calendar_result = calendar.delete_event(intent.delete_keyword or text)

        # 返回结果
        from voicecalendar.services.pipeline import PipelineResult, PipelineStatus
        return PipelineResult(
            success=True,
            status=PipelineStatus.DONE,
            raw_text=text,
            intent=intent,
            event=intent.event,
            calendar_result=calendar_result,
        )

    def _on_pipeline_result(self, result) -> None:
        """流水线处理完成回调。"""
        self._handle_pipeline_result(result)

    def _on_pipeline_error(self, error_msg: str) -> None:
        """流水线处理错误回调。"""
        self._status_indicator.set_status("error")
        error_display = get_user_message(Exception(error_msg)) if error_msg else "处理失败"
        self._result_label.setText(f"❌ {error_display}")
        self._result_label.setStyleSheet(
            "QLabel#ResultLabel { color: #FF6B6B; font-size: 13px; padding: 0; background-color: transparent; }"
        )
        self._toast(error_display, ToastType.ERROR)

    def _process_mock(self) -> None:
        """Mock 模式处理流程。"""
        try:
            result = self._pipeline.process_voice()
        except Exception as e:
            self._status_indicator.set_status("error")
            self._result_label.setText("❌ 处理失败")
            self._result_label.setStyleSheet(
                "QLabel#ResultLabel { color: #FF6B6B; font-size: 13px; padding: 0; background-color: transparent; }"
            )
            self._toast(str(e), ToastType.ERROR)
            return

        self._handle_pipeline_result(result)

    def _handle_pipeline_result(self, result) -> None:
        """统一处理流水线结果。"""
        if result.success and result.intent:
            self._status_indicator.set_status("success")

            if result.intent.is_add and result.intent.event:
                self._result_label.setText(f"✅ {result.raw_text}")
                self._result_label.setStyleSheet(
                    "QLabel#ResultLabel { color: #3DDC84; font-size: 13px; padding: 0; background-color: transparent; }"
                )
                self._add_event(result.intent.event)
                # 持久化到 CalendarBackend（真实模式已在 _process_audio_file 保存，此处做幂等兜底）
                self._persist_event(result.intent.event)
                self._toast("日程已添加 ✓", ToastType.SUCCESS)
                QTimer.singleShot(1500, lambda: self.switch_page(self.PAGE_SCHEDULE))
            elif result.intent.is_query:
                self._result_label.setText(f"🔍 {result.raw_text}")
                self._result_label.setStyleSheet(
                    "QLabel#ResultLabel { color: #7DD3FC; font-size: 13px; padding: 0; background-color: transparent; }"
                )
                self._toast("查询完成", ToastType.INFO)
            elif result.intent.is_delete:
                self._result_label.setText(f"🗑 {result.raw_text}")
                self._result_label.setStyleSheet(
                    "QLabel#ResultLabel { color: #FF6B6B; font-size: 13px; padding: 0; background-color: transparent; }"
                )
                # 删除后从 CalendarBackend 刷新 UI 列表
                self._refresh_event_list()
                self._toast("已删除日程", ToastType.SUCCESS)
            else:
                self._result_label.setText(f"💬 {result.raw_text}")
                self._result_label.setStyleSheet(
                    "QLabel#ResultLabel { color: #9AA0A8; font-size: 13px; padding: 0; background-color: transparent; }"
                )
        else:
            self._status_indicator.set_status("error")
            error_msg = get_user_message(Exception(result.error_message)) if result.error_message else ""
            error_display = error_msg or result.error_message or "识别失败，请重试"
            self._result_label.setText(f"❌ {error_display}")
            self._result_label.setStyleSheet(
                "QLabel#ResultLabel { color: #FF6B6B; font-size: 13px; padding: 0; background-color: transparent; }"
            )
            self._toast(error_display, ToastType.ERROR)

    def _add_event(self, event: CalendarEvent) -> None:
        card = self._create_card(event)
        card.show()
        self._event_layout.insertWidget(0, card)
        self._events.append(event)

        # 隐藏空状态
        self._empty_label.hide()

        # 滑入动画
        QTimer.singleShot(10, lambda: self._animate_card_entry(card))

    def _persist_event(self, event: CalendarEvent) -> None:
        """将事件持久化到 CalendarBackend（如果尚未保存）。"""
        # 检查是否已经在持久化存储中（避免真实模式重复保存）
        saved = self._calendar.load_events()
        already_saved = any(
            e.title == event.title and e.start_date == event.start_date and e.start_time == event.start_time
            for e in saved
        )
        if not already_saved:
            self._calendar.add_event(event)

    def _refresh_event_list(self) -> None:
        """从 CalendarBackend 重新加载事件并刷新 UI 列表。"""
        # 清除现有 EventCard — 遍历 layout 只取 EventCard，跳过 _empty_label 和 stretch
        i = 0
        while i < self._event_layout.count():
            item = self._event_layout.itemAt(i)
            if item and item.widget():
                w = item.widget()
                if isinstance(w, EventCard):
                    # 从 layout 移除并删除卡片
                    self._event_layout.removeItem(item)
                    w.setParent(None)
                    w.deleteLater()
                    continue
            i += 1

        # 重新加载
        self._events.clear()
        events = self._calendar.load_events()
        events.sort(key=lambda e: (e.start_date, e.start_time))

        if events:
            for event in events:
                card = self._create_card(event)
                self._event_layout.insertWidget(0, card)
                self._events.append(event)
            self._empty_label.hide()
        else:
            self._empty_label.show()

    # ── 编辑 / 删除 事件 ──

    def _on_edit_event(self, event: CalendarEvent) -> None:
        """编辑事件回调 — 弹出编辑对话框，保存后更新。"""
        # 记录编辑前的唯一标识（start_date + start_time 不变时用于定位）
        old_id = (event.start_date, event.start_time, event.title)

        dialog = EventEditDialog(event, self.window())
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # 可靠更新：加载所有事件，移除被编辑的那个，加入新事件
            all_events = self._calendar.load_events()
            new_events = [
                e for e in all_events
                if not (
                    e.title == old_id[2]
                    and e.start_date == old_id[0]
                    and e.start_time == old_id[1]
                )
            ]
            new_events.append(event)
            self._calendar.create_ics_file(new_events)
            self._refresh_event_list()
            self._toast("日程已更新 ✓", ToastType.SUCCESS)

    def _on_delete_event(self, event: CalendarEvent) -> None:
        """删除事件回调 — 确认后删除。"""
        from PyQt6.QtWidgets import QMessageBox
        msg = QMessageBox(
            QMessageBox.Icon.Question,
            "确认删除",
            f"确定要删除「{event.title}」吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            self.window(),
        )
        msg.setStyleSheet("""
            QMessageBox {
                background-color: #1E222A;
                color: #E8EAED;
            }
            QMessageBox QLabel {
                color: #E8EAED;
            }
            QMessageBox QPushButton {
                background-color: #2D323C;
                border: 1px solid #363C47;
                border-radius: 6px;
                color: #E8EAED;
                padding: 8px 20px;
                font-size: 13px;
            }
            QMessageBox QPushButton:hover {
                background-color: #363C47;
                border-color: #6B8AFF;
            }
        """)
        reply = msg.exec()
        if reply == QMessageBox.StandardButton.Yes:
            # 精确匹配删除：用 start_date + start_time + title 定位
            all_events = self._calendar.load_events()
            new_events = [
                e for e in all_events
                if not (
                    e.title == event.title
                    and e.start_date == event.start_date
                    and e.start_time == event.start_time
                )
            ]
            self._calendar.create_ics_file(new_events)
            self._refresh_event_list()
            self._toast("已删除日程", ToastType.SUCCESS)

    def _animate_card_entry(self, card: EventCard) -> None:
        target_pos = card.pos()
        start_pos = QPointF(target_pos.x(), target_pos.y() - 40)
        anim = QPropertyAnimation(card, b"pos")
        anim.setDuration(350)
        anim.setEasingCurve(QEasingCurve.Type.OutBack)
        anim.setStartValue(start_pos.toPoint())
        anim.setEndValue(target_pos)
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def _toast(self, message: str, toast_type: ToastType) -> None:
        main_window = self.window()
        if isinstance(main_window, MainWindow):
            main_window.toast(message, toast_type)


class MainWindow(QMainWindow):
    """VoiceCalendar-Pro 主窗口。"""

    theme_toggled: pyqtSignal = pyqtSignal(ThemeMode)

    def __init__(self) -> None:
        super().__init__()
        self._toast_manager: Optional[ToastManager] = None
        self._tray_icon: Optional[QSystemTrayIcon] = None
        self._force_quit: bool = False  # 标记是否强制退出（托盘菜单触发）
        self._setup_window()
        self._setup_ui()
        self._apply_theme()
        self._setup_tray()

    def _setup_window(self) -> None:
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.resize(win_cfg.DEFAULT_WIDTH, win_cfg.DEFAULT_HEIGHT)
        self.setMinimumSize(win_cfg.MIN_WIDTH, win_cfg.MIN_HEIGHT)
        self.setWindowTitle(tr("VoiceCalendar Pro"))

    def _setup_ui(self) -> None:
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
        theme_mgr = ThemeManager.instance()
        loader = ResourceLoader()
        loader.load_base_style()
        loader.load_theme_style("dark" if theme_mgr.is_dark() else "light")
        combined = loader.get_combined_style(theme_mgr.get_color_qss())
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

    # ── 系统托盘 ──

    def _create_tray_icon(self) -> QIcon:
        """用 QPainter 绘制麦克风托盘图标（多尺寸）。"""
        icon = QIcon()
        for size in [16, 22, 32, 48, 64]:
            pm = QPixmap(size, size)
            pm.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pm)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            s = size
            blue = QColor(107, 138, 255)
            white = QColor(255, 255, 255)

            # 麦克风主体 — 圆角矩形
            w = int(s * 0.44)
            h = int(s * 0.50)
            x = (s - w) // 2
            y = int(s * 0.08)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(blue)
            painter.drawRoundedRect(x, y, w, h, w // 2, w // 2)

            # 内部白色区域
            iw = int(w * 0.6)
            ih = int(h * 0.75)
            ix = (s - iw) // 2
            iy = y + int((h - ih) * 0.3)
            painter.setBrush(white)
            painter.drawRoundedRect(ix, iy, iw, ih, iw // 2, iw // 2)

            # 底部圆弧（麦克风支架）
            cx = s // 2
            bottom_y = y + h
            arc_w = int(s * 0.6)
            arc_h = int(s * 0.2)
            arc_x = cx - arc_w // 2

            painter.setBrush(blue)
            # 绘制下半椭圆弧
            painter.drawEllipse(
                cx, bottom_y,
                arc_w, arc_h
            )

            # 底部小竖线
            line_w = int(s * 0.12)
            line_h = int(s * 0.06)
            line_x = cx - line_w // 2
            line_y = s - line_h - int(s * 0.02)
            painter.setBrush(white)
            painter.drawRoundedRect(line_x, line_y, line_w, line_h, 1, 1)

            painter.end()
            icon.addPixmap(pm)

        return icon

    def _setup_tray(self) -> None:
        """创建系统托盘图标和右键菜单。"""
        # 检查系统托盘是否可用
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        icon = self._create_tray_icon()
        self._tray_icon = QSystemTrayIcon(icon, self)
        self._tray_icon.setToolTip("VoiceCalendar Pro")

        # 右键菜单 — 设置深色主题配色，避免白色文字在白色背景上看不见
        tray_menu = QMenu()
        tray_menu.setStyleSheet(
            "QMenu {"
            "    background-color: #2D323C;"
            "    color: #E8EAED;"
            "    border: 1px solid #3D4450;"
            "    border-radius: 4px;"
            "    padding: 4px;"
            "    font-family: 'Microsoft YaHei', 'Segoe UI';"
            "    font-size: 12pt;"
            "}"
            "QMenu::item {"
            "    padding: 6px 24px 6px 16px;"
            "    border-radius: 2px;"
            "}"
            "QMenu::item:selected {"
            "    background-color: #6B8AFF;"
            "    color: #FFFFFF;"
            "}"
            "QMenu::separator {"
            "    background-color: #3D4450;"
            "    height: 1px;"
            "    margin: 4px 8px;"
            "}"
        )

        action_show = QAction("显示窗口", tray_menu)
        action_show.triggered.connect(self._show_from_tray)
        tray_menu.addAction(action_show)

        tray_menu.addSeparator()

        action_quit = QAction("退出", tray_menu)
        action_quit.triggered.connect(self._quit_app)
        tray_menu.addAction(action_quit)

        self._tray_icon.setContextMenu(tray_menu)

        # 左键单击 -> 显示窗口
        self._tray_icon.activated.connect(self._on_tray_activated)

        # 显示托盘图标
        self._tray_icon.show()

    def _show_from_tray(self, _checked: bool = False) -> None:
        """从托盘恢复窗口。"""
        self.show()
        self.raise_()
        self.activateWindow()

    def _quit_app(self, _checked: bool = False) -> None:
        """强制退出应用。"""
        # 隐藏托盘图标，清理资源
        if self._tray_icon is not None:
            self._tray_icon.hide()
        # 直接退出 — QApplication.quit() 在有活跃 singleShot timer 时不生效
        # 用 sys.exit(0) 确保立即终止
        import sys
        sys.exit(0)

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        """托盘图标点击事件 — 单击显示窗口。"""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._show_from_tray()

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

    def paintEvent(self, event) -> None:  # type: ignore[override]
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
        if hasattr(self, "_force_quit") and self._force_quit:
            # 强制退出（托盘菜单触发）
            if self._tray_icon is not None:
                self._tray_icon.hide()
            event.accept()
            super().closeEvent(event)
        else:
            # 默认行为：最小化到托盘（不退出）
            event.ignore()
            self.hide()
            if self._toast_manager is not None:
                self._toast_manager.clear_all()
            if self._tray_icon is not None:
                self._tray_icon.showMessage(
                    "VoiceCalendar Pro",
                    "已最小化到系统托盘，右键托盘图标可退出",
                    QSystemTrayIcon.MessageIcon.Information,
                    2000,
                )


def tr(text: str) -> str:
    return text
