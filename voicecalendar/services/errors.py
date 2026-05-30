from __future__ import annotations

"""VoiceCalendar-Pro 集中式错误处理。

设计要点:
- 统一错误类型层次结构，便于分类处理
- 每种错误携带用户友好的中文提示
- 支持网络超时重试（指数退避）
- 支持 API 限流检测与自动等待
"""

import time
import logging
from abc import ABC
from functools import wraps
from typing import Any, Callable

logger = logging.getLogger("voicecalendar")


# ═══════════════════════════════════════════════════════════
# 错误类型层次结构
# ═══════════════════════════════════════════════════════════


class VoiceCalendarError(Exception):
    """基础异常类 — 所有 VoiceCalendar 异常的基类。"""

    def __init__(self, message: str, recoverable: bool = False) -> None:
        super().__init__(message)
        self.message = message
        self.recoverable = recoverable


class NetworkError(VoiceCalendarError):
    """网络连接错误。"""

    def __init__(self, message: str = "网络连接失败") -> None:
        super().__init__(message, recoverable=True)


class RequestTimeout(NetworkError):
    """请求超时。"""

    def __init__(self, message: str = "请求超时，请检查网络连接") -> None:
        super().__init__(message)


# 别名 — 保持向后兼容
TimeoutError = RequestTimeout  # type: ignore[misc]


class RateLimitError(VoiceCalendarError):
    """API 限流。"""

    def __init__(
        self,
        message: str = "请求过于频繁，请稍后重试",
        retry_after: int = 60,
    ) -> None:
        super().__init__(message, recoverable=True)
        self.retry_after = retry_after


class APIError(VoiceCalendarError):
    """API 调用错误。"""

    def __init__(
        self,
        message: str = "API 调用失败",
        status_code: int = 0,
        recoverable: bool = False,
    ) -> None:
        super().__init__(message, recoverable=recoverable)
        self.status_code = status_code


class ASRError(VoiceCalendarError):
    """语音识别错误。"""

    def __init__(self, message: str = "语音识别失败") -> None:
        super().__init__(message)


class NLUErrors(VoiceCalendarError):
    """意图解析错误。"""

    def __init__(self, message: str = "意图解析失败") -> None:
        super().__init__(message)


class ConfigurationError(VoiceCalendarError):
    """配置错误。"""

    def __init__(self, message: str = "配置错误") -> None:
        super().__init__(message, recoverable=False)


class CalendarError(VoiceCalendarError):
    """日历操作错误。"""

    def __init__(self, message: str = "日历操作失败") -> None:
        super().__init__(message)


# ═══════════════════════════════════════════════════════════
# 用户友好错误提示映射
# ═══════════════════════════════════════════════════════════

USER_FRIENDLY_MESSAGES = {
    NetworkError: "网络连接失败，请检查网络后重试",
    RequestTimeout: "请求超时，请稍后重试",
    RateLimitError: "请求过于频繁，请稍等片刻",
    APIError: "服务暂时不可用，请稍后重试",
    ASRError: "语音识别失败，请重新录音",
    NLUErrors: "无法理解您的指令，请换一种说法",
    ConfigurationError: "服务未配置，请检查 API Key 设置",
    CalendarError: "日历保存失败，请检查存储空间",
}


def get_user_message(error: Exception) -> str:
    """获取用户友好的错误提示。

    Args:
        error: 异常对象

    Returns:
        适合在 UI 中显示的中文错误提示
    """
    # 精确类型匹配优先（子类优先于父类）
    error_cls = type(error)
    for error_type, message in USER_FRIENDLY_MESSAGES.items():
        if error_cls is error_type:
            return message
    # 退回到 isinstance 匹配（按 MRO 顺序查找最近的匹配）
    for cls in error_cls.__mro__:
        if cls in USER_FRIENDLY_MESSAGES:
            return USER_FRIENDLY_MESSAGES[cls]
    return "操作失败，请稍后重试"


# ═══════════════════════════════════════════════════════════
# 重试装饰器（指数退避）
# ═══════════════════════════════════════════════════════════

RETRYABLE_EXCEPTIONS = (NetworkError, RequestTimeout, RateLimitError)


def retry_on_failure(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    backoff_factor: float = 2.0,
) -> Callable:
    """重试装饰器 — 指数退避策略。

    对网络相关错误自动重试，每次等待时间翻倍。

    Args:
        max_retries: 最大重试次数
        base_delay: 初始等待时间（秒）
        max_delay: 最大等待时间（秒）
        backoff_factor: 退避倍数

    Usage:
        @retry_on_failure(max_retries=3)
        def call_api():
            ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_error: Exception | None = None
            delay = base_delay

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except RETRYABLE_EXCEPTIONS as e:
                    last_error = e
                    if attempt < max_retries:
                        # RateLimitError 使用 retry_after
                        if isinstance(e, RateLimitError) and e.retry_after:
                            actual_delay = min(e.retry_after, max_delay)
                        else:
                            actual_delay = min(delay * (backoff_factor ** attempt), max_delay)

                        logger.warning(
                            "请求失败，第 %d/%d 次重试，%.1f 秒后重试: %s",
                            attempt + 1,
                            max_retries,
                            actual_delay,
                            e.message,
                        )
                        time.sleep(actual_delay)
                    else:
                        logger.error("请求失败，已达最大重试次数: %s", e.message)
                except Exception:
                    # 非重试异常直接抛出
                    raise

            raise last_error  # type: ignore[misc]

        return wrapper

    return decorator


# ═══════════════════════════════════════════════════════════
# 限流器（令牌桶算法）
# ═══════════════════════════════════════════════════════════


class RateLimiter:
    """简单令牌桶限流器。

    控制 API 调用频率，避免触发服务端限流。

    Args:
        max_tokens: 令牌桶容量（最大并发请求数）
        refill_rate: 每秒补充令牌数

    Usage:
        limiter = RateLimiter(max_tokens=5, refill_rate=2)
        limiter.acquire()  # 等待获取令牌
        # 执行 API 调用
    """

    def __init__(
        self,
        max_tokens: int = 10,
        refill_rate: float = 2.0,
    ) -> None:
        self.max_tokens = max_tokens
        self.refill_rate = refill_rate
        self._tokens = float(max_tokens)
        self._last_refill = time.monotonic()

    def acquire(self, tokens: int = 1) -> bool:
        """尝试获取令牌。

        Args:
            tokens: 需要获取的令牌数

        Returns:
            True = 获取成功，False = 令牌不足
        """
        self._refill()
        if self._tokens >= tokens:
            self._tokens -= tokens
            return True
        return False

    def wait(self, tokens: int = 1, timeout: float = 30.0) -> bool:
        """等待获取令牌。

        Args:
            tokens: 需要获取的令牌数
            timeout: 最长等待时间（秒）

        Returns:
            True = 获取成功，False = 超时
        """
        start = time.monotonic()
        while True:
            if self.acquire(tokens):
                return True
            if time.monotonic() - start > timeout:
                return False
            time.sleep(0.1)

    def _refill(self) -> None:
        """补充令牌。"""
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(
            self.max_tokens,
            self._tokens + elapsed * self.refill_rate,
        )
        self._last_refill = now


# ═══════════════════════════════════════════════════════════
# HTTP 错误解析
# ═══════════════════════════════════════════════════════════


def parse_http_error(status_code: int, response_text: str = "") -> VoiceCalendarError:
    """根据 HTTP 状态码创建对应的异常。

    Args:
        status_code: HTTP 状态码
        response_text: 响应内容

    Returns:
        对应的 VoiceCalendarError 子类
    """
    messages = {
        400: f"请求参数错误: {response_text}",
        401: "API Key 无效，请检查配置",
        403: "API 访问被拒绝，请检查权限",
        404: "API 端点不存在",
        429: "请求过于频繁",
        500: "服务器内部错误",
        502: "网关错误，请稍后重试",
        503: "服务暂时不可用",
        504: "网关超时",
    }

    if status_code == 429:
        return RateLimitError(
            message=messages.get(status_code, "请求过于频繁"),
            retry_after=60,
        )

    if status_code >= 500:
        return APIError(
            message=messages.get(status_code, f"服务器错误: {status_code}"),
            status_code=status_code,
            recoverable=True,
        )

    if status_code == 401:
        return ConfigurationError(
            message=messages.get(status_code, "API Key 无效"),
        )

    return APIError(
        message=messages.get(status_code, f"HTTP {status_code}: {response_text}"),
        status_code=status_code,
    )
