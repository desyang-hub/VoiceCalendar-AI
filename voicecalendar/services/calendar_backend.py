from __future__ import annotations

"""日历后端服务 — ICS 文件生成与管理。

使用 ics 库生成标准 .ics 日历文件，可被系统日历导入。
"""

import os
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import ics  # type: ignore[import-not-found]

from voicecalendar.models.event import CalendarEvent, EventRecurrence

# ICS 重复规则映射
RECURRENCE_MAP = {
    EventRecurrence.NONE: None,
    EventRecurrence.DAILY: {"freq": "DAILY"},
    EventRecurrence.WEEKLY: {"freq": "WEEKLY"},
    EventRecurrence.MONTHLY: {"freq": "MONTHLY"},
    EventRecurrence.YEARLY: {"freq": "YEARLY"},
}


@dataclass
class CalendarOperationResult:
    """日历操作结果。"""

    success: bool
    message: str
    file_path: str | None = None
    event_count: int = 0


class CalendarBackend:
    """日历后端服务。

    功能:
    - 生成标准 ICS 日历文件
    - 管理本地事件存储
    - 查询/删除事件

    Args:
        storage_dir: 事件存储目录 (默认 ~/.voicecalendar/events)
    """

    def __init__(self, storage_dir: str | None = None) -> None:
        self._storage_dir = Path(storage_dir) if storage_dir else Path.home() / ".voicecalendar" / "events"
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._default_ics_path = self._storage_dir / "calendar.ics"

    def create_ics_file(
        self,
        events: list[CalendarEvent],
        output_path: str | Path | None = None,
    ) -> CalendarOperationResult:
        """从事件列表生成 ICS 文件。

        Args:
            events: 日历事件列表
            output_path: 输出文件路径 (默认 ~/.voicecalendar/events/calendar.ics)

        Returns:
            CalendarOperationResult
        """
        if not events:
            return CalendarOperationResult(
                success=False,
                message="事件列表为空",
            )

        path = Path(output_path) if output_path else self._default_ics_path
        path.parent.mkdir(parents=True, exist_ok=True)

        try:
            calendar = ics.Calendar()

            for event in events:
                vevent = self._event_to_vcalendar(event)
                calendar.events.add(vevent)

            with open(path, "w", encoding="utf-8") as f:
                f.write(str(calendar))

            return CalendarOperationResult(
                success=True,
                message=f"已生成 {len(events)} 个事件",
                file_path=str(path),
                event_count=len(events),
            )

        except Exception as e:
            return CalendarOperationResult(
                success=False,
                message=f"生成失败: {e}",
            )

    def add_event(self, event: CalendarEvent) -> CalendarOperationResult:
        """添加单个事件到日历。

        Args:
            event: 要添加的事件

        Returns:
            CalendarOperationResult
        """
        # 读取现有事件
        existing = self.load_events()
        existing.append(event)

        return self.create_ics_file(existing)

    def load_events(self) -> list[CalendarEvent]:
        """从 ICS 文件加载事件。

        Returns:
            事件列表
        """
        if not self._default_ics_path.exists():
            return []

        try:
            with open(self._default_ics_path, encoding="utf-8") as f:
                calendar = ics.Calendar(f.read())

            events = []
            for vevent in calendar.events:
                event = self._vcalendar_to_event(vevent)
                events.append(event)

            return events

        except Exception:
            return []

    def delete_event(self, title_keyword: str) -> CalendarOperationResult:
        """根据标题关键词删除事件。

        Args:
            title_keyword: 搜索关键词 (模糊匹配)

        Returns:
            CalendarOperationResult
        """
        events = self.load_events()
        original_count = len(events)

        # 模糊匹配
        events = [e for e in events if title_keyword.lower() not in e.title.lower()]

        if len(events) == original_count:
            return CalendarOperationResult(
                success=False,
                message=f"未找到包含 '{title_keyword}' 的事件",
            )

        result = self.create_ics_file(events)
        if result.success:
            result.message = f"已删除 {original_count - len(events)} 个事件"

        return result

    def query_events(
        self,
        query_date: date | None = None,
        keyword: str = "",
        days: int = 1,
    ) -> list[CalendarEvent]:
        """查询事件。

        Args:
            query_date: 查询日期
            keyword: 关键词过滤
            days: 查询范围 (天数)

        Returns:
            匹配的事件列表
        """
        events = self.load_events()
        results = []

        for event in events:
            # 日期范围过滤
            if query_date is not None:
                end = query_date + timedelta(days=days - 1)
                if not (query_date <= event.start_date <= end):
                    continue

            # 关键词过滤
            if keyword and keyword.lower() not in event.title.lower():
                continue

            results.append(event)

        return results

    def list_today_events(self) -> list[CalendarEvent]:
        """列出今天的日程。"""
        from datetime import date as _date

        return self.query_events(query_date=_date.today())

    def list_week_events(self) -> list[CalendarEvent]:
        """列出本周的日程。"""
        from datetime import date as _date

        today = _date.today()
        # 本周一
        monday = today - timedelta(days=today.weekday())
        return self.query_events(query_date=monday, days=7)

    def open_in_calendar(self, ics_path: str | None = None) -> None:
        """用系统默认日历应用打开 ICS 文件。

        Args:
            ics_path: ICS 文件路径
        """
        path = ics_path or str(self._default_ics_path)

        if os.name == "nt":
            # Windows
            os.startfile(path)  # type: ignore[attr-defined]
        elif os.name == "darwin":
            # macOS
            os.system(f"open '{path}'")
        else:
            # Linux
            os.system(f"xdg-open '{path}'")

    # ── 内部方法 ──

    def _event_to_vcalendar(self, event: CalendarEvent) -> ics.Event:
        """CalendarEvent → ics.Event。"""
        from ics.event import Event as ICS_Event

        vevent = ICS_Event()
        vevent.name = event.title
        vevent.begin = event.start_datetime
        vevent.end = event.end_datetime
        vevent.description = event.description
        vevent.location = event.location

        # 重复规则
        if event.recurrence != EventRecurrence.NONE:
            rrule_data = RECURRENCE_MAP.get(event.recurrence, {})
            if rrule_data:
                if event.recurrence_count > 0:
                    rrule_data["count"] = event.recurrence_count
                vevent.rrules.append(ics.RecurrenceRule(**rrule_data))  # type: ignore[union-attr]

        # 提醒
        if event.reminder_minutes > 0:
            alarm = ics.DisplayAlarm()
            alarm.trigger = timedelta(minutes=-event.reminder_minutes)
            alarm.display_text = f"提醒: {event.title}"
            vevent.alarms.append(alarm)

        return vevent

    def _vcalendar_to_event(self, vevent: ics.Event) -> CalendarEvent:
        """ics.Event → CalendarEvent。"""
        from datetime import date as _date
        from datetime import time as _time

        start_dt = vevent.begin if hasattr(vevent.begin, "hour") else vevent.begin
        end_dt = vevent.end if hasattr(vevent.end, "hour") else start_dt

        return CalendarEvent(
            title=vevent.name or "未命名事件",
            start_date=start_dt.date() if hasattr(start_dt, "date") else _date.today(),
            start_time=start_dt.time() if hasattr(start_dt, "time") else _time(9, 0),
            end_date=end_dt.date() if hasattr(end_dt, "date") else None,
            end_time=end_dt.time() if hasattr(end_dt, "time") else None,
            description=vevent.description or "",
            location=vevent.location or "",
        )
