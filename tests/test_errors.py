from __future__ import annotations

"""测试错误处理模块。"""

import time
from voicecalendar.services.errors import (
    VoiceCalendarError,
    NetworkError,
    RequestTimeout,
    RateLimitError,
    APIError,
    ASRError,
    NLUErrors,
    ConfigurationError,
    CalendarError,
    get_user_message,
    retry_on_failure,
    RateLimiter,
    parse_http_error,
)


class TestErrorHierarchy:
    """测试错误类型层次结构。"""

    def test_network_error(self) -> None:
        err = NetworkError("测试网络错误")
        assert err.message == "测试网络错误"
        assert err.recoverable is True

    def test_timeout_error(self) -> None:
        err = RequestTimeout()
        assert "超时" in err.message
        assert err.recoverable is True

    def test_rate_limit_error(self) -> None:
        err = RateLimitError(retry_after=30)
        assert err.retry_after == 30
        assert err.recoverable is True

    def test_api_error(self) -> None:
        err = APIError("API 错误", status_code=500)
        assert err.status_code == 500

    def test_configuration_error(self) -> None:
        err = ConfigurationError("缺少配置")
        assert err.recoverable is False


class TestUserFriendlyMessages:
    """测试用户友好错误提示。"""

    def test_network_message(self) -> None:
        msg = get_user_message(NetworkError())
        assert "网络" in msg

    def test_timeout_message(self) -> None:
        msg = get_user_message(RequestTimeout())
        assert "超时" in msg

    def test_asr_message(self) -> None:
        msg = get_user_message(ASRError())
        assert "语音识别" in msg

    def test_nlu_message(self) -> None:
        msg = get_user_message(NLUErrors())
        assert "理解" in msg or "解析" in msg

    def test_unknown_error(self) -> None:
        msg = get_user_message(Exception("未知"))
        assert msg  # 应该返回默认提示


class TestRetryDecorator:
    """测试重试装饰器。"""

    def test_retry_success_immediately(self) -> None:
        @retry_on_failure(max_retries=3, base_delay=0.01)
        def success_func() -> str:
            return "ok"

        assert success_func() == "ok"

    def test_retry_after_failure(self) -> None:
        call_count = 0

        @retry_on_failure(max_retries=3, base_delay=0.01)
        def fail_twice() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise NetworkError("临时故障")
            return "ok"

        assert fail_twice() == "ok"
        assert call_count == 3

    def test_retry_exhausted(self) -> None:
        @retry_on_failure(max_retries=2, base_delay=0.01)
        def always_fail() -> str:
            raise NetworkError("持续故障")

        try:
            always_fail()
            assert False, "应该抛出异常"
        except NetworkError:
            pass

    def test_retry_non_retryable(self) -> None:
        @retry_on_failure(max_retries=3, base_delay=0.01)
        def value_error() -> str:
            raise ValueError("不可重试")

        try:
            value_error()
            assert False, "应该抛出异常"
        except ValueError:
            pass


class TestRateLimiter:
    """测试令牌桶限流器。"""

    def test_acquire_within_limit(self) -> None:
        limiter = RateLimiter(max_tokens=5, refill_rate=1.0)
        assert limiter.acquire() is True
        assert limiter.acquire() is True

    def test_acquire_exceed_limit(self) -> None:
        limiter = RateLimiter(max_tokens=2, refill_rate=0.1)
        assert limiter.acquire() is True
        assert limiter.acquire() is True
        assert limiter.acquire() is False

    def test_wait_success(self) -> None:
        limiter = RateLimiter(max_tokens=1, refill_rate=10.0)
        limiter.acquire()
        assert limiter.wait(timeout=2.0) is True

    def test_refill(self) -> None:
        limiter = RateLimiter(max_tokens=2, refill_rate=100.0)
        limiter.acquire()
        limiter.acquire()
        time.sleep(0.05)  # 等待补充
        assert limiter.acquire() is True


class TestHTTPErrorParsing:
    """测试 HTTP 错误解析。"""

    def test_rate_limit_429(self) -> None:
        err = parse_http_error(429)
        assert isinstance(err, RateLimitError)

    def test_server_error_500(self) -> None:
        err = parse_http_error(500)
        assert isinstance(err, APIError)
        assert err.status_code == 500
        assert err.recoverable is True

    def test_auth_error_401(self) -> None:
        err = parse_http_error(401)
        assert isinstance(err, ConfigurationError)

    def test_bad_request_400(self) -> None:
        err = parse_http_error(400)
        assert isinstance(err, APIError)

    def test_unknown_status(self) -> None:
        err = parse_http_error(418)
        assert isinstance(err, APIError)
        assert "418" in err.message
