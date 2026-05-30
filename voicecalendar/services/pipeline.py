from __future__ import annotations

"""语音日历处理流水线 (Pipeline)。

串联 Audio → ASR → NLU → Calendar 四个服务。
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from voicecalendar.models.event import CalendarEvent, ParseIntent
from voicecalendar.services.audio_capture import AudioCapture
from voicecalendar.services.asr_service import ASRService, TranscriptionResult
from voicecalendar.services.nlu_parser import NLUParser
from voicecalendar.services.calendar_backend import CalendarBackend, CalendarOperationResult


class PipelineStatus(Enum):
    """流水线状态。"""

    IDLE = "idle"
    RECORDING = "recording"
    TRANSCRIBING = "transcribing"
    PARSING = "parsing"
    SAVING = "saving"
    DONE = "done"
    ERROR = "error"


@dataclass
class PipelineResult:
    """流水线处理结果。"""

    success: bool
    status: PipelineStatus = PipelineStatus.DONE
    raw_text: str = ""
    intent: Optional[ParseIntent] = None
    event: Optional[CalendarEvent] = None
    calendar_result: Optional[CalendarOperationResult] = None
    audio_path: Optional[str] = None
    error_message: str = ""


class VoiceCalendarPipeline:
    """语音日历处理流水线。

    串联四个服务：
    1. AudioCapture — 录音
    2. ASRService — 语音转文字
    3. NLUParser — 意图解析
    4. CalendarBackend — 日历写入

    Args:
        api_key: OpenAI API 密钥
        base_url: API 基础 URL
        whisper_model: Whisper 模型
        llm_model: LLM 模型
        storage_dir: 日历存储目录
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        whisper_model: str = "whisper-1",
        llm_model: str = "gpt-4o",
        storage_dir: Optional[str] = None,
    ) -> None:
        # 初始化各服务
        self.audio = AudioCapture()
        self.asr = ASRService(api_key, base_url, whisper_model)
        self.nlu = NLUParser(api_key, base_url, llm_model)
        self.calendar = CalendarBackend(storage_dir)

        self._status = PipelineStatus.IDLE

    @property
    def status(self) -> PipelineStatus:
        return self._status

    @property
    def is_ready(self) -> bool:
        """服务是否就绪。"""
        return self.asr.is_ready and self.nlu.is_ready

    # ── 完整流程 ──

    def process_voice(self, text: str = "", use_recording: bool = False) -> PipelineResult:
        """处理语音指令 (完整流程)。

        Args:
            text: 文本输入 (非空则跳过录音)
            use_recording: True=先录音再识别

        Returns:
            PipelineResult
        """
        self._status = PipelineStatus.IDLE

        # 1. 录音 (可选)
        audio_path: Optional[Path] = None
        if use_recording:
            try:
                self._status = PipelineStatus.RECORDING
                self.audio.start()
                # 等待外部调用 stop_recording()
                # 此处不阻塞
                return PipelineResult(
                    success=False,
                    status=PipelineStatus.RECORDING,
                    error_message="等待录音结束",
                )
            except Exception as e:
                return PipelineResult(
                    success=False,
                    status=PipelineStatus.ERROR,
                    error_message=f"录音失败: {e}",
                )

        # 1.5 如果有录音，获取 WAV 路径
        if self.audio.output_path is not None:
            audio_path = self.audio.output_path

        # 2. 语音识别
        self._status = PipelineStatus.TRANSCRIBING
        if not text and audio_path:
            result = self.asr.transcribe(audio_path)
            if not result.success:
                return PipelineResult(
                    success=False,
                    status=PipelineStatus.ERROR,
                    error_message=result.error_message,
                )
            text = result.text

        if not text.strip():
            return PipelineResult(
                success=False,
                status=PipelineStatus.ERROR,
                error_message="未识别到有效文本",
            )

        # 3. 意图解析
        self._status = PipelineStatus.PARSING
        intent = self.nlu.parse(text)

        if intent.action == ParseIntent.Action.UNKNOWN:
            return PipelineResult(
                success=False,
                status=PipelineStatus.DONE,
                raw_text=text,
                intent=intent,
                error_message="无法识别意图",
            )

        # 4. 日历操作
        self._status = PipelineStatus.SAVING
        calendar_result: Optional[CalendarOperationResult] = None

        if intent.is_add and intent.event:
            calendar_result = self.calendar.add_event(intent.event)
        elif intent.is_delete:
            calendar_result = self.calendar.delete_event(intent.delete_keyword or text)

        # 5. 完成
        self._status = PipelineStatus.DONE

        return PipelineResult(
            success=True,
            status=PipelineStatus.DONE,
            raw_text=text,
            intent=intent,
            event=intent.event,
            calendar_result=calendar_result,
            audio_path=str(audio_path) if audio_path else None,
        )

    # ── 单独操作 ──

    def start_recording(self) -> None:
        """开始录音。"""
        self._status = PipelineStatus.RECORDING
        self.audio.start()

    def stop_recording(self) -> Path:
        """停止录音。"""
        return self.audio.stop()

    def query_schedule(self, text: str) -> list[CalendarEvent]:
        """查询日程。

        Args:
            text: 查询文本 ("今天有什么安排")

        Returns:
            匹配的事件列表
        """
        intent = self.nlu.parse(text)

        if intent.is_query or intent.is_list:
            return self.calendar.query_events(
                query_date=intent.query_date,
                keyword=intent.query_keyword,
            )

        return self.calendar.load_events()

    def list_today(self) -> list[CalendarEvent]:
        """列出今天日程。"""
        return self.calendar.list_today_events()

    def list_week(self) -> list[CalendarEvent]:
        """列出本周日程。"""
        return self.calendar.list_week_events()

    def save_ics(self, output_path: Optional[str] = None) -> CalendarOperationResult:
        """保存当前所有事件为 ICS 文件。"""
        events = self.calendar.load_events()
        return self.calendar.create_ics_file(events, output_path)


class MockPipeline:
    """模拟流水线 (用于测试，无需 API)。"""

    def __init__(self) -> None:
        from voicecalendar.services.asr_service import MockASRService
        from voicecalendar.services.nlu_parser import MockNLUParser

        self.asr = MockASRService()
        self.nlu = MockNLUParser()
        self.calendar = CalendarBackend()

    def process_voice(self, text: str = "") -> PipelineResult:
        """模拟处理流程。"""
        from datetime import date, time

        # 模拟识别结果
        if not text:
            text = "明天下午三点开会"

        # 模拟解析结果
        intent = ParseIntent(
            action=ParseIntent.Action.ADD,
            event=CalendarEvent(
                title="团队会议",
                start_date=date.today(),
                start_time=time(15, 0),
            ),
            raw_text=text,
            confidence=0.95,
        )

        return PipelineResult(
            success=True,
            raw_text=text,
            intent=intent,
            event=intent.event,
        )
