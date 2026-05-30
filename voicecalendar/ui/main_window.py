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
    QPointF,
    QPoint,
    QPropertyAnimation,
    QEasingCurve,
)
from PyQt6.QtGui import QColor, QPainter, QMouseEvent, QBrush
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
)

from voicecalendar.config import WindowConfig
from voicecalendar.core.theme import ThemeManager, ThemeMode
from voicecalendar.core.resources import ResourceLoader
from voicecalendar.ui.titlebar import TitleBar
from voicecalendar.ui.components.toast import ToastManager, ToastType
from voicecalendar.ui.widgets.waveform import WaveformWidget, StatusIndicator
from voicecalendar.ui.widgets.skeleton import CircularProgress
from voicecalendar.models.event import CalendarEvent
from voicecalendar.services.pipeline import MockPipeline
from voicecalendar.services.errors import get_user_message

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
    """日程事件卡片 — 左侧颜色指示条 + 时间 + 标题 + 日期标签。"""

    # 事件类型配色
    EVENT_COLORS = [
        "#6B8AFF",  # 蓝
        "#3DDC84",  # 绿
        "#FFB340",  # 橙
        "#FF6B6B",  # 红
        "#7DD3FC",  # 青
        "#BB86FC",  # 紫
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

        # 颜色指示条（左侧 3px 圆角条）
        color = self.EVENT_COLORS[hash(event.title) % len(self.EVENT_COLORS)]
        indicator = QFrame()
        indicator.setFixedSize(3, 36)
        indicator.setStyleSheet(
            f"QFrame {{ background-color: {color}; border-radius: 2px; }}"
        )
        layout.addWidget(indicator)

        # 时间区域
        time_column = QVBoxLayout()
        time_column.setSpacing(2)

        time_label = QLabel(event.start_time.strftime("%H:%M"))
        time_label.setStyleSheet(f"color: {color}; font-size: 13px; font-weight: 700;")
        time_column.addWidget(time_label)

        # 如果有结束时间，显示持续时间
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

        # 分割线
        divider = QFrame()
        divider.setFixedSize(1, 36)
        divider.setStyleSheet("background-color: #2D323C;")
        layout.addWidget(divider)

        # 标题区域（可伸缩容器）
        title_container = QWidget()
        title_column = QVBoxLayout(title_container)
        title_column.setContentsMargins(0, 0, 0, 0)
        title_column.setSpacing(4)
        title_column.addStretch()

        title_label = QLabel(event.title)
        title_label.setStyleSheet("color: #E8EAED; font-size: 14px; font-weight: 500;")
        title_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        title_column.addWidget(title_label)
        title_column.addStretch()

        layout.addWidget(title_container, 1)

        # 日期标签徽章
        date_badge = QLabel(event.start_date.strftime("%m/%d"))
        date_badge.setStyleSheet(
            "color: #6B7280;"
            "font-size: 11px;"
            "font-weight: 600;"
            "background-color: rgba(128, 128, 128, 0.1);"
            "padding: 4px 8px;"
            "border-radius: 6px;"
        )
        date_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(date_badge)


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

        # 初始化服务
        self._pipeline = MockPipeline()
        self._events: list[CalendarEvent] = []

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

        # 加载示例事件
        self._load_sample_events()

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
        version_dot = QLabel("●")
        version_dot.setStyleSheet("color: #3DDC84; font-size: 8px;")
        version_dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_layout.addWidget(version_dot)
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

        # 提示
        hint = QLabel("点击麦克风按钮开始语音输入")
        hint.setStyleSheet("color: #6B7280; font-size: 13px;")
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

        # ── ASR 配置 ──
        asr_section = self._create_settings_section(
            "🎤 语音识别 (ASR)",
            [
                ("API Key", "OPENAI_API_KEY", "sk-xxx"),
                ("Base URL", "OPENAI_BASE_URL", "https://api.openai.com/v1"),
                ("模型", None, "whisper-1", True),
            ],
        )
        settings_layout.addWidget(asr_section)

        # ── LLM 配置 ──
        llm_section = self._create_settings_section(
            "🧠 意图解析 (LLM)",
            [
                ("API Key", None, "sk-xxx"),
                ("Base URL", None, "https://api.openai.com/v1"),
                ("模型", None, "gpt-4o", True),
            ],
        )
        settings_layout.addWidget(llm_section)

        # ── 主题配置 ──
        theme_section = self._create_settings_section(
            "🎨 界面",
            [],
        )
        # 主题切换按钮
        theme_row = QHBoxLayout()
        theme_row.setSpacing(12)

        theme_label = QLabel("深色模式")
        theme_label.setStyleSheet("color: #E8EAED; font-size: 13px;")
        theme_row.addWidget(theme_label)
        theme_row.addStretch()

        self._theme_toggle = QCheckBox()
        self._theme_toggle.setChecked(True)
        self._theme_toggle.setStyleSheet(
            "QCheckBox::indicator {"
            "    width: 40px; height: 22px;"
            "    border-radius: 11px;"
            "    background-color: #2D323C;"
            "}"
            "QCheckBox::indicator:checked {"
            "    background-color: #6B8AFF;"
            "}"
            "QCheckBox {"
            "    color: #E8EAED;"
            "    font-size: 13px;"
            "}"
        )
        self._theme_toggle.toggled.connect(self._on_theme_toggled)
        theme_row.addWidget(self._theme_toggle)
        theme_section.layout().addLayout(theme_row)

        settings_layout.addWidget(theme_section)
        settings_layout.addStretch()

        scroll.setWidget(settings_container)
        layout.addWidget(scroll, 1)

        return page

    def _create_settings_section(
        self,
        title: str,
        fields: list,
    ) -> QFrame:
        """创建设置卡片。

        fields: list of (label_text, env_var_name, placeholder, is_combo)
        """
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

        # 标题
        sec_title = QLabel(title)
        sec_title.setStyleSheet("color: #E8EAED; font-size: 14px; font-weight: 600;")
        card_layout.addWidget(sec_title)

        for field_data in fields:
            is_combo = len(field_data) == 4 and field_data[3]
            if is_combo:
                label_text, _, placeholder, _ = field_data
                combo_values = placeholder.split(",")
            else:
                label_text, _, placeholder = field_data
                combo_values = None

            row = QHBoxLayout()
            row.setSpacing(12)

            lbl = QLabel(label_text)
            lbl.setStyleSheet("color: #9AA0A8; font-size: 13px; min-width: 70px;")
            row.addWidget(lbl)

            if combo_values:
                combo = QComboBox()
                for v in combo_values:
                    combo.addItem(v.strip())
                combo.setCurrentText(placeholder.strip())
                combo.setStyleSheet(
                    "QComboBox {"
                    "    background-color: #2D323C;"
                    "    border: 1px solid #363C47;"
                    "    border-radius: 6px;"
                    "    padding: 6px 10px;"
                    "    color: #E8EAED;"
                    "    font-size: 13px;"
                    "}"
                    "QComboBox::drop-down {"
                    "    border: none;"
                    "}"
                    "QComboBox QAbstractItemView {"
                    "    background-color: #2D323C;"
                    "    color: #E8EAED;"
                    "    selection-background-color: #6B8AFF;"
                    "}"
                )
                row.addWidget(combo, 1)
            else:
                line = QLineEdit()
                line.setPlaceholderText(placeholder)
                line.setStyleSheet(
                    "QLineEdit {"
                    "    background-color: #2D323C;"
                    "    border: 1px solid #363C47;"
                    "    border-radius: 6px;"
                    "    padding: 6px 10px;"
                    "    color: #E8EAED;"
                    "    font-size: 13px;"
                    "}"
                )
                row.addWidget(line, 1)

            card_layout.addLayout(row)

        return card

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

    def _load_sample_events(self) -> None:
        """加载示例事件到日程页面。"""
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

        # 隐藏空状态提示
        if self._empty_label.isVisible():
            self._empty_label.hide()

    def _on_recording_started(self) -> None:
        self._status_indicator.set_status("recording")
        self._waveform.set_recording(True)
        self._result_label.setText("")
        self._result_label.setStyleSheet(
            "QLabel#ResultLabel { color: #9AA0A8; font-size: 13px; padding: 0; background-color: transparent; }"
        )

    def _on_recording_stopped(self) -> None:
        self._status_indicator.set_status("processing")
        self._waveform.set_recording(False)
        self._result_label.setText("⏳ 正在识别语音...")
        self._result_label.setStyleSheet(
            "QLabel#ResultLabel { color: #FFB340; font-size: 13px; padding: 0; background-color: transparent; }"
        )
        QTimer.singleShot(1200, self._process_voice)

    def _process_voice(self) -> None:
        try:
            result = self._pipeline.process_voice()
        except Exception as e:
            self._status_indicator.set_status("error")
            self._result_label.setText("❌ 处理失败，请稍后重试")
            self._result_label.setStyleSheet(
                "QLabel#ResultLabel { color: #FF6B6B; font-size: 13px; padding: 0; background-color: transparent; }"
            )
            self._toast(get_user_message(e) or "处理失败", ToastType.ERROR)
            return

        if result.success and result.intent:
            self._status_indicator.set_status("success")
            if result.intent.is_add and result.intent.event:
                self._result_label.setText(f"✅ {result.raw_text}")
                self._result_label.setStyleSheet(
                    "QLabel#ResultLabel { color: #3DDC84; font-size: 13px; padding: 0; background-color: transparent; }"
                )
                self._add_event(result.intent.event)
                self._toast("日程已添加 ✓", ToastType.SUCCESS)
                # 自动跳回日程页面
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
                self._toast("已删除日程", ToastType.SUCCESS)
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
        card = EventCard(event)
        card.show()
        self._event_layout.insertWidget(0, card)
        self._events.append(event)

        # 隐藏空状态
        self._empty_label.hide()

        # 滑入动画
        QTimer.singleShot(10, lambda: self._animate_card_entry(card))

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
        self._setup_window()
        self._setup_ui()
        self._apply_theme()

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
        event.accept()
        super().closeEvent(event)


def tr(text: str) -> str:
    return text
