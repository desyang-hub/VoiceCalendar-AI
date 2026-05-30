"""服务层测试。"""

import tempfile
from datetime import date, time, timedelta
from pathlib import Path

from voicecalendar.models.event import CalendarEvent, ParseIntent
from voicecalendar.services.asr_service import MockASRService, TranscriptionResult
from voicecalendar.services.nlu_parser import NLUParser, MockNLUParser, QuickTimeParser
from voicecalendar.services.calendar_backend import CalendarBackend
from voicecalendar.services.pipeline import VoiceCalendarPipeline, MockPipeline, PipelineResult


# ═════════════════════════════════════════════
# QuickTimeParser 测试
# ═════════════════════════════════════════════


def test_quick_time_today() -> None:
    today = date.today()
    assert QuickTimeParser.parse_relative("今天") == today
    assert QuickTimeParser.parse_relative("今日") == today


def test_quick_time_tomorrow() -> None:
    tomorrow = date.today() + timedelta(days=1)
    assert QuickTimeParser.parse_relative("明天") == tomorrow
    assert QuickTimeParser.parse_relative("明日") == tomorrow


def test_quick_time_day_after() -> None:
    day_after = date.today() + timedelta(days=2)
    assert QuickTimeParser.parse_relative("后天") == day_after


def test_quick_time_relative_days() -> None:
    future = date.today() + timedelta(days=3)
    assert QuickTimeParser.parse_relative("三天后") == future


def test_quick_time_weekday() -> None:
    ref = date.today()
    # 下周一
    monday = QuickTimeParser.parse_relative("下周一", ref)
    assert monday is not None
    assert monday.weekday() == 0  # Monday = 0


def test_quick_time_parse_hour() -> None:
    result = QuickTimeParser.parse_time("下午三点")
    assert result is not None
    assert result == (15, 0)  # 下午三点 = 15:00


def test_quick_time_parse_half() -> None:
    result = QuickTimeParser.parse_time("下午两点半")
    assert result is not None
    assert result[0] == 14
    assert result[1] == 30


def test_quick_time_parse_24h() -> None:
    result = QuickTimeParser.parse_time("14:30")
    assert result is not None
    assert result == (14, 30)


# ═════════════════════════════════════════════
# MockASRService 测试
# ═════════════════════════════════════════════


def test_mock_asr_transcribe() -> None:
    asr = MockASRService()
    result = asr.transcribe("dummy.wav")

    assert result.success
    assert len(result.text) > 0
    assert result.language == "zh"


def test_mock_asr_multiple() -> None:
    """测试连续调用返回不同结果。"""
    asr = MockASRService()
    r1 = asr.transcribe("a.wav")
    r2 = asr.transcribe("b.wav")
    r3 = asr.transcribe("c.wav")

    assert r1.text != r2.text or r2.text != r3.text


# ═════════════════════════════════════════════
# MockNLUParser 测试
# ═════════════════════════════════════════════


def test_mock_nlu_add() -> None:
    parser = MockNLUParser()
    intent = parser.parse("明天下午三点开会")

    assert intent.action == ParseIntent.Action.ADD
    assert intent.event is not None


def test_mock_nlu_query() -> None:
    parser = MockNLUParser()
    # 跳过 add
    parser.parse("dummy")
    intent = parser.parse("今天有什么安排")

    assert intent.action == ParseIntent.Action.QUERY


def test_mock_nlu_delete() -> None:
    parser = MockNLUParser()
    parser.parse("dummy1")
    parser.parse("dummy2")
    intent = parser.parse("取消明天的会议")

    assert intent.action == ParseIntent.Action.DELETE


# ═════════════════════════════════════════════
# CalendarBackend 测试
# ═════════════════════════════════════════════


def test_calendar_create_ics() -> None:
    """测试 ICS 文件生成。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        backend = CalendarBackend(storage_dir=tmpdir)
        events = [
            CalendarEvent(
                title="测试会议",
                start_date=date(2026, 6, 1),
                start_time=time(10, 0),
                end_time=time(11, 0),
                description="测试描述",
            )
        ]

        result = backend.create_ics_file(events)
        assert result.success
        assert result.event_count == 1
        assert result.file_path is not None

        # 验证文件存在
        assert Path(result.file_path).exists()


def test_calendar_add_and_load() -> None:
    """测试添加并加载事件。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        backend = CalendarBackend(storage_dir=tmpdir)
        event = CalendarEvent(
            title="新事件",
            start_date=date.today(),
            start_time=time(15, 0),
        )

        result = backend.add_event(event)
        assert result.success

        loaded = backend.load_events()
        assert len(loaded) >= 1
        assert loaded[0].title == "新事件"


def test_calendar_delete() -> None:
    """测试删除事件。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        backend = CalendarBackend(storage_dir=tmpdir)

        # 添加事件
        backend.add_event(CalendarEvent(
            title="待删除会议",
            start_date=date.today(),
        ))
        backend.add_event(CalendarEvent(
            title="保留会议",
            start_date=date.today(),
        ))

        # 删除
        result = backend.delete_event("待删除")
        assert result.success

        remaining = backend.load_events()
        assert len(remaining) == 1
        assert remaining[0].title == "保留会议"


def test_calendar_query_date() -> None:
    """测试按日期查询。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        backend = CalendarBackend(storage_dir=tmpdir)

        # 添加今天和明天的
        backend.add_event(CalendarEvent(
            title="今天事件",
            start_date=date.today(),
        ))
        backend.add_event(CalendarEvent(
            title="明天事件",
            start_date=date.today() + timedelta(days=1),
        ))

        today_events = backend.query_events(query_date=date.today())
        assert len(today_events) == 1
        assert today_events[0].title == "今天事件"


def test_calendar_list_today() -> None:
    """测试列出今天日程。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        backend = CalendarBackend(storage_dir=tmpdir)
        backend.add_event(CalendarEvent(
            title="今日会议",
            start_date=date.today(),
            start_time=time(9, 0),
        ))

        events = backend.list_today_events()
        assert len(events) == 1
        assert events[0].title == "今日会议"


# ═════════════════════════════════════════════
# MockPipeline 测试
# ═════════════════════════════════════════════


def test_mock_pipeline() -> None:
    """测试模拟流水线。"""
    pipeline = MockPipeline()
    result = pipeline.process_voice("明天下午三点开会")

    assert result.success
    assert len(result.raw_text) > 0
    assert result.intent is not None
    assert result.event is not None


def test_mock_pipeline_with_text() -> None:
    """测试传入文本的模拟流水线。"""
    pipeline = MockPipeline()
    result = pipeline.process_voice(text="下周一上午十点面试")

    assert result.success
    assert result.raw_text == "下周一上午十点面试"


# ═════════════════════════════════════════════
# NLU 快速解析测试
# ═════════════════════════════════════════════


def test_quick_parse_add() -> None:
    """测试快速解析 — 添加意图。"""
    parser = NLUParser()  # 无 API key，降级为快速解析
    assert not parser.is_ready

    intent = parser.parse("明天下午三点开会")
    assert intent.action == ParseIntent.Action.ADD


def test_quick_parse_query() -> None:
    """测试快速解析 — 查询意图。"""
    parser = NLUParser()
    intent = parser.parse("今天有什么安排")

    assert intent.action == ParseIntent.Action.LIST


def test_quick_parse_delete() -> None:
    """测试快速解析 — 删除意图。"""
    parser = NLUParser()
    intent = parser.parse("取消明天的会议")

    assert intent.action == ParseIntent.Action.DELETE
