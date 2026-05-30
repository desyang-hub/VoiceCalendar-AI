from __future__ import annotations

"""ASR (自动语音识别) 服务。

使用 OpenAI Whisper API 将音频文件转为文字。
支持自动重试、限流处理、优雅降级。

使用方式:
    asr = ASRService(api_key="sk-xxx")
    text = asr.transcribe("recording.wav")
    print(text)  # "明天下午三点开会"
"""

import os
import logging
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from voicecalendar.services.errors import (
    ASRError,
    ConfigurationError,
    NetworkError,
    RequestTimeout,
    parse_http_error,
    retry_on_failure,
    RateLimiter,
)

logger = logging.getLogger("voicecalendar")


@dataclass
class TranscriptionResult:
    """语音识别结果。"""

    text: str
    language: str = "zh"
    duration: float = 0.0
    success: bool = True
    error_message: str = ""


class ASRService:
    """语音转文字服务。

    使用 OpenAI Whisper API 进行语音识别。
    支持自动重试（网络错误 / 限流）、限流控制、优雅降级。

    Args:
        api_key: OpenAI API 密钥
        base_url: API 基础 URL (默认 OpenAI)
        model: Whisper 模型名称
        language: 目标语言
        max_retries: 最大重试次数
        timeout: 请求超时时间（秒）
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = "whisper-1",
        language: str = "zh",
        max_retries: int = 3,
        timeout: int = 30,
    ) -> None:
        self._api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self._base_url = base_url or os.getenv("OPENAI_BASE_URL")
        self._model = model
        self._language = language
        self._max_retries = max_retries
        self._timeout = timeout
        self._client: Optional[object] = None
        self._rate_limiter = RateLimiter(max_tokens=10, refill_rate=2.0)
        self._error: str = ""

        # 初始化 API 客户端
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
            self._error = str(e)
            logger.error("ASR 客户端初始化失败: %s", e)

    @property
    def is_ready(self) -> bool:
        """服务是否就绪。"""
        return self._client is not None and self._api_key != ""

    @retry_on_failure(max_retries=3, base_delay=1.0)
    def transcribe(self, audio_path: str | Path) -> TranscriptionResult:
        """将音频文件转为文字。

        Args:
            audio_path: 音频文件路径 (支持 WAV, MP3, M4A, FLAC)

        Returns:
            TranscriptionResult: 识别结果
        """
        if not self.is_ready:
            return TranscriptionResult(
                text="",
                success=False,
                error_message="ASR 服务未配置，请设置 OPENAI_API_KEY",
            )

        audio_file = Path(audio_path)
        if not audio_file.exists():
            return TranscriptionResult(
                text="",
                success=False,
                error_message=f"音频文件不存在: {audio_file}",
            )

        # 等待限流器
        if not self._rate_limiter.wait(timeout=self._timeout):
            return TranscriptionResult(
                text="",
                success=False,
                error_message="请求排队超时，请稍后重试",
            )

        try:
            assert self._client is not None
            with open(audio_file, "rb") as f:
                transcript = self._client.audio.transcriptions.create(
                    model=self._model,
                    file=f,
                    language=self._language,
                    response_format="text",
                )

            text = transcript.strip() if isinstance(transcript, str) else str(transcript)

            if not text:
                return TranscriptionResult(
                    text="",
                    success=False,
                    error_message="未识别到有效语音内容",
                )

            return TranscriptionResult(
                text=text,
                language=self._language,
                success=True,
            )

        except Exception as e:
            error_str = str(e).lower()
            # 分类错误类型
            if "timed out" in error_str or "timeout" in error_str:
                raise RequestTimeout("语音识别超时，请检查网络连接")
            if "rate" in error_str or "429" in error_str:
                raise RateLimitError("语音识别请求过于频繁", retry_after=30)
            if "connection" in error_str or "network" in error_str:
                raise NetworkError("网络连接失败，无法识别语音")

            # 尝试解析 HTTP 状态码
            if hasattr(e, "status_code"):
                code = e.status_code
                if code == 404:
                    raise ASRError(
                        f"语音识别 API 不可用 (404)。"
                        f"当前模型 '{self._model}' 可能不支持标准 Whisper API。"
                        f"请确认模型名称或改用 OpenAI whisper-1。"
                    )
                http_error = parse_http_error(code, str(e))
                raise http_error

            raise ASRError(f"语音识别失败: {e}")

    def transcribe_with_details(self, audio_path: str | Path) -> dict:
        """获取详细识别结果 (包含时间戳)。

        Args:
            audio_path: 音频文件路径

        Returns:
            包含识别详情和单词级时间戳的字典
        """
        if not self.is_ready:
            return {"text": "", "error": "ASR 服务未配置"}

        audio_file = Path(audio_path)
        try:
            assert self._client is not None
            with open(audio_file, "rb") as f:
                transcript = self._client.audio.transcriptions.create(
                    model=self._model,
                    file=f,
                    language=self._language,
                    response_format="verbose_json",
                    timestamp_granularities=["word"],
                )

            return transcript.to_dict() if hasattr(transcript, "to_dict") else {}

        except Exception as e:
            logger.error("详细识别失败: %s", e)
            return {"text": "", "error": str(e)}


class MockASRService:
    """模拟 ASR 服务 (用于测试，无需 API Key)。

    返回预设的文本，用于开发和调试。
    """

    def __init__(self) -> None:
        self._test_cases: list[str] = [
            "明天下午三点开会",
            "下周一上午十点有个面试",
            "本周五下午两点到四点做项目评审",
        ]
        self._index = 0

    @property
    def is_ready(self) -> bool:
        return True

    def transcribe(self, audio_path: str | Path) -> TranscriptionResult:
        """模拟语音识别，返回预设文本。"""
        text = self._test_cases[self._index % len(self._test_cases)]
        self._index += 1

        return TranscriptionResult(text=text, success=True, language="zh")
