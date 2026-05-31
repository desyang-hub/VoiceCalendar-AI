from __future__ import annotations

"""NLU (自然语言理解) 解析服务。

使用 LLM (OpenAI Compatible API) 将自然语言转为结构化日程数据。
支持 LLM 解析 + 快速时间解析降级。

核心功能:
- 意图识别 (添加/查询/删除/列出)
- 时间归一化 (相对时间 → 绝对时间)
- 事件结构化提取
"""

import json
import logging
import os
from datetime import date, datetime

from voicecalendar.models.event import CalendarEvent, EventRecurrence, ParseIntent
from voicecalendar.services.errors import (
    NetworkError,
    NLUErrors,
    RateLimiter,
    RateLimitError,
    RequestTimeout,
    retry_on_failure,
)

logger = logging.getLogger("voicecalendar")


# ─────────────────────────────────────────────
# 系统提示词 — 指导 LLM 输出结构化 JSON
# ─────────────────────────────────────────────

SYSTEM_PROMPT = """\
你是一个智能日历助手。你的任务是将用户的自然语言指令解析为结构化 JSON 数据。

## 输出格式

你必须且只输出一个 JSON 对象，不要包含任何其他内容。格式如下：

```json
{{
    "action": "add|query|delete|list",
    "event": {{
        "title": "事件标题",
        "start_date": "YYYY-MM-DD",
        "start_time": "HH:MM",
        "end_time": "HH:MM",
        "description": "描述",
        "recurrence": "none|daily|weekly|monthly|yearly",
        "recurrence_count": 0,
        "location": "地点",
        "reminder_minutes": 15
    }},
    "query_date": "YYYY-MM-DD",
    "query_keyword": "关键词",
    "delete_keyword": "关键词",
    "confidence": 0.95
}}
```

## 时间归一化规则

当前日期: {current_date}
当前时间: {current_time}

- "明天" → 明天日期
- "后天" → 后天日期
- "下周一" → 下一个周一的日期
- "本周三下午" → 本周周三的日期
- "三天后" → 当前日期 + 3天
- "今天下午3点" → 今天日期 + 15:00

## 动作识别

- add: 创建新日程 ("明天下午三点开会" → add)
- query: 查询日程 ("今天有什么安排" → query)
- delete: 删除日程 ("取消明天的会议" → delete)
- list: 列出日程 ("这周的所有日程" → list)

## 注意事项

1. 如果用户说的是相对时间，请根据当前日期计算出绝对日期
2. start_time 和 end_time 使用 24 小时制 "HH:MM"
3. 如果没有指定结束时间，end_time 为空
4. title 应该简洁明确
5. confidence 表示你对解析结果的信心 (0.0-1.0)
6. 对于 list/query 操作，event 字段设为 null
"""


# ─────────────────────────────────────────────
# 快速时间解析规则 (无需 LLM)
# ─────────────────────────────────────────────

class QuickTimeParser:
    """轻量级时间解析器 (不依赖 LLM，用于简单场景)。"""

    @staticmethod
    def parse_relative(text: str, ref_date: date | None = None) -> date | None:
        """解析相对时间表达。

        Args:
            text: 时间表达 ("明天", "下周一", "三天后")
            ref_date: 参考日期，默认今天

        Returns:
            解析后的日期，失败返回 None
        """
        from datetime import timedelta

        ref = ref_date or date.today()

        weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

        # 今天
        if "今天" in text or "今日" in text:
            return ref

        # 明天
        if "明天" in text or "明日" in text:
            return ref + timedelta(days=1)

        # 后天
        if "后天" in text:
            return ref + timedelta(days=2)

        # 前天 / 大后天
        if "大后天" in text:
            return ref + timedelta(days=3)

        # 下星期X
        for i, day in enumerate(weekdays):
            if f"下{day}" in text or f"下个{day}" in text:
                days_ahead = i - ref.weekday()
                if days_ahead <= 0:
                    days_ahead += 7
                return ref + timedelta(days=days_ahead)

        # 本周X
        for i, day in enumerate(weekdays):
            if f"本{day}" in text or f"这个{day}" in text:
                days_ahead = i - ref.weekday()
                if days_ahead < 0:
                    days_ahead += 7
                return ref + timedelta(days=days_ahead)

        # X天后
        import re

        m = re.search(r"(\d+)天后", text)
        if m:
            return ref + timedelta(days=int(m.group(1)))

        # 中文数字 + 天后
        cn_to_num = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
        m = re.search(r"([一二三四五六七八九十]+)天后", text)
        if m:
            days = cn_to_num.get(m.group(1), 0)
            if days > 0:
                return ref + timedelta(days=days)

        return None

    @staticmethod
    def parse_time(text: str) -> tuple[int, int] | None:
        """解析时间表达为 (hour, minute)。

        Args:
            text: 时间文本 ("下午三点", "14:30", "早上九点")

        Returns:
            (hour, minute) 或 None
        """
        import re

        hour = 0
        minute = 0

        # AM/PM
        is_pm = "下午" in text or "晚上" in text or "傍晚" in text
        is_am = "早上" in text or "上午" in text or "凌晨" in text

        # 中文数字映射
        cn_digits = {
            "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
            "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
            "零": 0,
        }

        def parse_cn_digit(s: str) -> int | None:
            """解析中文数字。"""
            if s.isdigit():
                return int(s)
            return cn_digits.get(s)

        # "下午三点" / "晚上八点半"
        m = re.search(r"([一二三四五六七八九十两\d]{1,2})点([一二三四五六七八九十两\d]{1,2})分?", text)
        if m:
            hour = parse_cn_digit(m.group(1)) or 0
            minute = parse_cn_digit(m.group(2)) or 0
        else:
            m = re.search(r"([一二三四五六七八九十两\d]{1,2})点半", text)
            if m:
                hour = parse_cn_digit(m.group(1)) or 0
                minute = 30
            else:
                m = re.search(r"([一二三四五六七八九十两\d]{1,2})点", text)
                if m:
                    hour = parse_cn_digit(m.group(1)) or 0

        # 24小时制调整 (下午/晚上)
        if is_pm and hour < 12:
            hour += 12
        if is_am and hour == 12:
            hour = 0

        # 14:30 格式 (直接返回，已经是24小时制)
        m = re.search(r"(\d{1,2}):(\d{2})", text)
        if m:
            return (int(m.group(1)), int(m.group(2)))

        return (hour, minute) if hour > 0 else None


class NLUParser:
    """自然语言理解解析器。

    使用 LLM 将自然语言指令转为结构化数据。
    支持自动重试和快速解析降级。

    Args:
        api_key: OpenAI API 密钥
        base_url: API 基础 URL
        model: LLM 模型名称
        timeout: 请求超时时间（秒）
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str = "gpt-4o",
        timeout: int = 30,
    ) -> None:
        self._api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self._base_url = base_url or os.getenv("OPENAI_BASE_URL")
        self._model = model
        self._timeout = timeout
        self._client: object | None = None
        self._quick_parser = QuickTimeParser()
        self._rate_limiter = RateLimiter(max_tokens=10, refill_rate=2.0)

        self._init_client()

    def _init_client(self) -> None:
        """初始化 OpenAI 客户端。"""
        try:
            import openai as _openai

            kwargs: dict = {
                "api_key": self._api_key,
                "timeout": self._timeout,
            }
            if self._base_url:
                kwargs["base_url"] = self._base_url
            self._client = _openai.OpenAI(**kwargs)
        except Exception as e:
            self._client = None
            logger.error("NLU 客户端初始化失败: %s", e)

    @property
    def is_ready(self) -> bool:
        return self._client is not None and self._api_key != ""

    def parse(self, text: str, ref_date: date | None = None) -> ParseIntent:
        """解析自然语言指令。

        优先使用 LLM 解析，失败时自动降级到快速解析。

        Args:
            text: 用户语音文本
            ref_date: 参考日期 (默认今天)

        Returns:
            ParseIntent: 解析结果
        """
        if not self.is_ready:
            logger.info("LLM 未就绪，使用快速解析降级")
            return self._quick_parse(text, ref_date)

        try:
            return self._llm_parse(text, ref_date)
        except (NetworkError, RequestTimeout, RateLimitError) as e:
            logger.warning("LLM 解析失败 (%s)，降级到快速解析: %s", type(e).__name__, text)
            return self._quick_parse(text, ref_date)
        except NLUErrors as e:
            logger.error("LLM 解析错误: %s", e)
            return self._quick_parse(text, ref_date)
        except Exception as e:
            logger.error("LLM 解析未知错误: %s，降级到快速解析", e)
            return self._quick_parse(text, ref_date)

    @retry_on_failure(max_retries=2, base_delay=1.5)
    def _llm_parse(self, text: str, ref_date: date | None = None) -> ParseIntent:
        """使用 LLM 解析 — 带自动重试。"""
        ref = ref_date or date.today()
        now = datetime.now()

        prompt = SYSTEM_PROMPT.format(
            current_date=ref.isoformat(),
            current_time=now.strftime("%H:%M"),
        )

        # 等待限流器
        if not self._rate_limiter.wait(timeout=self._timeout):
            raise RequestTimeout("NLU 请求排队超时")

        try:
            assert self._client is not None
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": text},
                ],
                temperature=0.1,
                max_tokens=500,
                response_format={"type": "json_object"},
            )

            raw_content = response.choices[0].message.content or "{}"
            data = json.loads(raw_content)

            return self._build_intent(data, text, ref)

        except json.JSONDecodeError as e:
            raise NLUErrors(f"LLM 返回格式错误: {e}")
        except Exception as e:
            error_str = str(e).lower()
            if "timed out" in error_str or "timeout" in error_str:
                raise RequestTimeout("意图解析超时")
            if "rate" in error_str or "429" in error_str:
                raise RateLimitError("意图解析请求过于频繁", retry_after=30)
            if "connection" in error_str or "network" in error_str:
                raise NetworkError("网络连接失败，无法解析意图")
            raise NLUErrors(f"意图解析失败: {e}")

    def _build_intent(self, data: dict, raw_text: str, ref_date: date) -> ParseIntent:
        """从 LLM 返回的 JSON 构建 ParseIntent。"""
        action_map = {
            "add": ParseIntent.Action.ADD,
            "query": ParseIntent.Action.QUERY,
            "delete": ParseIntent.Action.DELETE,
            "list": ParseIntent.Action.LIST,
        }

        action_str = data.get("action", "unknown")
        action = action_map.get(action_str, ParseIntent.Action.UNKNOWN)
        confidence = data.get("confidence", 0.5)

        intent = ParseIntent(
            action=action,
            raw_text=raw_text,
            confidence=confidence,
        )

        # 构建事件
        if action == ParseIntent.Action.ADD and "event" in data and isinstance(data.get("event"), dict):
            event_data = data["event"]
            intent.event = self._build_event(event_data, ref_date)

        # 查询参数
        if action in (ParseIntent.Action.QUERY, ParseIntent.Action.LIST):
            if "query_date" in data and data["query_date"]:
                from datetime import datetime

                intent.query_date = datetime.fromisoformat(data["query_date"]).date()
            intent.query_keyword = data.get("query_keyword", "")

        # 删除参数
        if action == ParseIntent.Action.DELETE:
            intent.delete_keyword = data.get("delete_keyword", "")

        return intent

    def _build_event(self, data: dict, ref_date: date) -> CalendarEvent:
        """从 JSON 数据构建 CalendarEvent。"""
        from datetime import datetime, time

        # 日期
        if "start_date" in data and data["start_date"]:
            start_date = datetime.fromisoformat(data["start_date"]).date()
        else:
            start_date = ref_date

        # 时间
        start_time = time(9, 0)
        if "start_time" in data and data["start_time"]:
            parts = data["start_time"].split(":")
            start_time = time(int(parts[0]), int(parts[1]) if len(parts) > 1 else 0)

        end_time = None
        if "end_time" in data and data["end_time"]:
            parts = data["end_time"].split(":")
            end_time = time(int(parts[0]), int(parts[1]) if len(parts) > 1 else 0)

        # 结束日期
        end_date = None
        if "end_date" in data and data["end_date"]:
            end_date = datetime.fromisoformat(data["end_date"]).date()

        return CalendarEvent(
            title=data.get("title") or "新事件",
            start_date=start_date,
            start_time=start_time,
            end_date=end_date,
            end_time=end_time,
            description=data.get("description") or "",
            recurrence=EventRecurrence(data.get("recurrence") or "none"),
            recurrence_count=data.get("recurrence_count") or 0,
            location=data.get("location") or "",
            reminder_minutes=data.get("reminder_minutes") if data.get("reminder_minutes") is not None else 15,
        )

    def _quick_parse(self, text: str, ref_date: date | None = None) -> ParseIntent:
        """快速解析 (不依赖 LLM)。"""
        ref = ref_date or date.today()

        # 尝试解析日期
        parsed_date = self._quick_parser.parse_relative(text, ref)
        parsed_time = self._quick_parser.parse_time(text)

        intent = ParseIntent(raw_text=text, confidence=0.6)

        # 简单意图判断 (优先级: DELETE > LIST > ADD)
        if any(kw in text for kw in ["取消", "删除", "去掉"]):
            intent.action = ParseIntent.Action.DELETE
            intent.delete_keyword = text
        elif any(kw in text for kw in ["有什么", "安排", "日程"]):
            intent.action = ParseIntent.Action.LIST
            if parsed_date:
                intent.query_date = parsed_date
        else:
            # 默认为添加
            intent.action = ParseIntent.Action.ADD
            if parsed_date and parsed_time:
                intent.event = CalendarEvent(
                    title=text[:50],
                    start_date=parsed_date,
                    start_time=parsed_time[0],  # type: ignore[arg-type]
                )

        return intent


class MockNLUParser:
    """模拟 NLU 解析器 (用于测试)。"""

    def __init__(self) -> None:
        from datetime import date, time

        self._test_results: list[ParseIntent] = [
            ParseIntent(
                action=ParseIntent.Action.ADD,
                event=CalendarEvent(
                    title="团队会议",
                    start_date=date.today(),
                    start_time=time(15, 0),
                    description="讨论项目进度",
                ),
                raw_text="明天下午三点开会",
                confidence=0.95,
            ),
            ParseIntent(
                action=ParseIntent.Action.QUERY,
                query_date=date.today(),
                raw_text="今天有什么安排",
                confidence=0.9,
            ),
            ParseIntent(
                action=ParseIntent.Action.DELETE,
                delete_keyword="会议",
                raw_text="取消明天的会议",
                confidence=0.85,
            ),
        ]
        self._index = 0

    def parse(self, text: str, ref_date: date | None = None) -> ParseIntent:
        result = self._test_results[self._index % len(self._test_results)]
        self._index += 1
        return result
