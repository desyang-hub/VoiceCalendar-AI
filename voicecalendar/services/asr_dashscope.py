from __future__ import annotations

"""DashScope Qwen-ASR 语音识别服务。

使用 DashScope OpenAI 兼容模式 /chat/completions 端点调用 qwen3-asr-flash 模型。

请求格式:
    client.chat.completions.create(
        model="qwen3-asr-flash",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_audio",
                        "input_audio": {
                            "data": "data:audio/wav;base64,..."
                        }
                    }
                ]
            }
        ],
        extra_body={
            "asr_options": {
                "enable_itn": False
            }
        }
    )

支持的模型:
    - qwen3-asr-flash (推荐)

使用方式:
    asr = DashScopeASR(api_key="sk-xxx", model="qwen3-asr-flash")
    result = asr.transcribe("recording.wav")
    print(result.text)
"""

import base64
import logging
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from voicecalendar.services.errors import (
    ASRError,
    ConfigurationError,
    NetworkError,
    RequestTimeout,
    RateLimiter,
)

logger = logging.getLogger("voicecalendar")


@dataclass
class ASRResult:
    """语音识别结果。"""

    text: str
    language: str = "zh"
    duration: float = 0.0
    success: bool = True
    error_message: str = ""


class DashScopeASR:
    """DashScope Qwen-ASR 语音识别服务。

    使用 OpenAI 兼容模式 /chat/completions 端点调用 qwen3-asr-flash 模型。
    音频文件编码为 base64 data URL 传入。

    Args:
        api_key: DashScope API Key
        model: ASR 模型名称（默认 qwen3-asr-flash）
        timeout: 请求超时时间（秒）
    """

    DEFAULT_MODEL = "qwen3-asr-flash"
    BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: int = 60,
    ) -> None:
        self._api_key = api_key or os.getenv("DASHSCOPE_API_KEY", "") or os.getenv("OPENAI_API_KEY", "")
        self._model = model or self.DEFAULT_MODEL
        self._timeout = timeout
        self._rate_limiter = RateLimiter(max_tokens=10, refill_rate=2.0)
        self._lock = threading.Lock()

    @property
    def is_ready(self) -> bool:
        """服务是否就绪。"""
        return bool(self._api_key)

    def _encode_audio(self, audio_path: str | Path) -> str:
        """将音频文件编码为 base64 data URL。

        Args:
            audio_path: 音频文件路径

        Returns:
            data:audio/wav;base64,<base64_data>
        """
        audio_file = Path(audio_path)
        suffix = audio_file.suffix.lower().lstrip(".")
        # 默认按 wav 处理
        mime_type = f"audio/{suffix if suffix in ('wav', 'mp3', 'ogg', 'flac', 'm4a', 'webm') else 'wav'}"

        raw = audio_file.read_bytes()
        b64 = base64.b64encode(raw).decode("ascii")
        return f"data:{mime_type};base64,{b64}"

    def transcribe(self, audio_path: str | Path) -> ASRResult:
        """将音频文件转为文字。

        Args:
            audio_path: 音频文件路径 (支持 WAV/MP3/OGG/FLAC 等)

        Returns:
            ASRResult: 识别结果
        """
        if not self.is_ready:
            return ASRResult(
                text="",
                success=False,
                error_message="DashScope API Key 未配置",
            )

        audio_file = Path(audio_path)
        if not audio_file.exists():
            return ASRResult(
                text="",
                success=False,
                error_message=f"音频文件不存在: {audio_file}",
            )

        file_size = audio_file.stat().st_size
        if file_size < 200:
            return ASRResult(
                text="",
                success=False,
                error_message="音频文件太小，可能为空",
            )

        # 等待限流器
        if not self._rate_limiter.wait(timeout=self._timeout):
            return ASRResult(
                text="",
                success=False,
                error_message="请求排队超时，请稍后重试",
            )

        try:
            # 线程安全初始化 OpenAI 客户端
            from openai import OpenAI

            client = OpenAI(
                api_key=self._api_key,
                base_url=self.BASE_URL,
            )

            # 编码音频为 data URL
            logger.info("正在编码音频文件: %s (%.1f KB)", audio_file.name, file_size / 1024)
            audio_data_url = self._encode_audio(audio_file)
            logger.info("音频编码完成: %d 字符", len(audio_data_url))

            # 构建请求
            completion = client.chat.completions.create(
                model=self._model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_audio",
                                "input_audio": {
                                    "data": audio_data_url
                                }
                            }
                        ]
                    }
                ],
                stream=False,
                timeout=self._timeout,
                extra_body={
                    "asr_options": {
                        "enable_itn": False
                    }
                }
            )

            # 解析响应
            text = completion.choices[0].message.content
            if not text or not text.strip():
                return ASRResult(
                    text="",
                    success=False,
                    error_message="未识别到有效语音内容",
                )

            logger.info("ASR 识别成功: %s", self._model)
            logger.info("识别文本: %s", text[:100])

            return ASRResult(
                text=text.strip(),
                language="zh",
                success=True,
            )

        except (RequestTimeout, ASRError, ConfigurationError, NetworkError):
            raise
        except Exception as e:
            error_str = str(e).lower()
            if "timeout" in error_str:
                raise RequestTimeout(f"语音识别超时: {e}")
            if "connection" in error_str or "network" in error_str:
                raise NetworkError(f"网络连接失败: {e}")
            if "authentication" in error_str or "unauthorized" in error_str or "401" in error_str:
                raise ConfigurationError(f"API Key 无效: {e}")
            raise ASRError(f"语音识别失败 ({self._model}): {e}")
