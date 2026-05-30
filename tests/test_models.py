"""数据模型测试。"""

from datetime import date, time
from voicecalendar.models.event import CalendarEvent, ParseIntent, EventRecurrence


def test_calendar_event_basic() -> None:
    """测试基础事件创建。"""
    event = CalendarEvent(
        title="团队周会",
        start_date=date(2026, 6, 1),
        start_time=time(10, 0),
        end_time=time(11, 0),
    )

    assert event.title == "团队周会"
    assert event.start_date == date(2026, 6, 1)
    assert event.start_time == time(10, 0)
    assert event.end_datetime.hour == 11


def test_calendar_event_default_end_time() -> None:
    """测试默认结束时间 (+1 小时)。"""
    event = CalendarEvent(
        title="会议",
        start_date=date(2026, 6, 1),
        start_time=time(14, 0),
    )

    assert event.end_datetime.hour == 15


def test_calendar_event_recurrence() -> None:
    """测试重复事件。"""
    event = CalendarEvent(
        title="每日晨会",
        start_date=date(2026, 6, 1),
        start_time=time(9, 0),
        recurrence=EventRecurrence.DAILY,
        recurrence_count=5,
    )

    assert event.recurrence == EventRecurrence.DAILY
    assert event.recurrence_count == 5


def test_parse_intent_add() -> None:
    """测试添加意图。"""
    intent = ParseIntent(
        action=ParseIntent.Action.ADD,
        event=CalendarEvent(title="会议", start_date=date.today()),
        raw_text="明天开会",
        confidence=0.9,
    )

    assert intent.is_add
    assert not intent.is_query
    assert not intent.is_delete


def test_parse_intent_query() -> None:
    """测试查询意图。"""
    intent = ParseIntent(
        action=ParseIntent.Action.QUERY,
        query_date=date.today(),
        raw_text="今天有什么安排",
        confidence=0.85,
    )

    assert intent.is_query
    assert not intent.is_add


def test_parse_intent_delete() -> None:
    """测试删除意图。"""
    intent = ParseIntent(
        action=ParseIntent.Action.DELETE,
        delete_keyword="会议",
        raw_text="取消明天的会议",
    )

    assert intent.is_delete
    assert intent.delete_keyword == "会议"
