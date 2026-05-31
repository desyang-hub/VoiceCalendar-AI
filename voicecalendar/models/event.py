from __future__ import annotations

"""日历事件数据模型。

定义语音识别后解析出的结构化日程数据。
"""

from datetime import date, datetime, time
from enum import Enum

from pydantic import BaseModel, Field


class EventRecurrence(Enum):
    """事件重复类型。"""

    NONE = "none"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


class CalendarEvent(BaseModel):
    """日历事件模型。

    Attributes:
        title: 事件标题
        start_date: 开始日期
        start_time: 开始时间 (默认为当天)
        end_date: 结束日期 (默认同开始日期)
        end_time: 结束时间 (默认开始时间 + 1 小时)
        description: 事件描述
        recurrence: 重复规则
        recurrence_count: 重复次数 (0=无限)
        location: 地点
        reminder_minutes: 提醒时间 (分钟前)
    """

    title: str = Field(..., min_length=1, max_length=200)
    start_date: date
    start_time: time = time(9, 0)
    end_date: date | None = None
    end_time: time | None = None
    description: str = ""
    recurrence: EventRecurrence = EventRecurrence.NONE
    recurrence_count: int = 0
    location: str = ""
    reminder_minutes: int = 15

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "title": "团队周会",
                    "start_date": "2026-06-01",
                    "start_time": "10:00:00",
                    "end_time": "11:00:00",
                    "description": "每周团队同步会议",
                    "recurrence": "weekly",
                    "location": "会议室 A",
                    "reminder_minutes": 15,
                }
            ]
        }
    }

    @property
    def start_datetime(self) -> datetime:
        """完整的开始时间。"""
        return datetime.combine(self.start_date, self.start_time)

    @property
    def end_datetime(self) -> datetime:
        """完整的结束时间。"""
        end = self.end_date or self.start_date
        if self.end_time is None:
            # 默认 1 小时
            from datetime import timedelta

            dt = datetime.combine(end, self.start_time) + timedelta(hours=1)
            return dt
        return datetime.combine(end, self.end_time)

    def __repr__(self) -> str:
        return f"<CalendarEvent {self.title} @ {self.start_datetime}>"


class ParseIntent(BaseModel):
    """语音解析意图结果。

    Attributes:
        action: 操作类型 (add/query/delete/list)
        event: 日程事件 (add/delete 时有值)
        query_date: 查询日期 (query 时使用)
        query_keyword: 查询关键词
        delete_keyword: 删除关键词 (delete 时使用)
        raw_text: 原始语音文本
        confidence: 解析置信度 (0.0-1.0)
    """

    class Action(str, Enum):
        ADD = "add"
        QUERY = "query"
        DELETE = "delete"
        LIST = "list"
        UNKNOWN = "unknown"

    action: ParseIntent.Action = Action.UNKNOWN
    event: CalendarEvent | None = None
    query_date: date | None = None
    query_keyword: str = ""
    delete_keyword: str = ""
    raw_text: str = ""
    confidence: float = 0.0

    @property
    def is_add(self) -> bool:
        return self.action == self.Action.ADD

    @property
    def is_query(self) -> bool:
        return self.action == self.Action.QUERY

    @property
    def is_delete(self) -> bool:
        return self.action == self.Action.DELETE

    @property
    def is_list(self) -> bool:
        return self.action == self.Action.LIST
