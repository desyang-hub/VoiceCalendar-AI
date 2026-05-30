from __future__ import annotations

"""音频录制服务 — 麦克风录音 + WAV 文件生成。

纯 Python 模块，不依赖 Qt。使用 sounddevice + scipy 实现。

使用方式:
    capture = AudioCapture()
    capture.start()
    capture.stop()
    wav_path = capture.output_path  # Path to generated .wav file
"""

import wave
import tempfile
import os
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

from voicecalendar.config import AudioConfig

audio_cfg = AudioConfig()


@dataclass
class AudioSegment:
    """一段录制的音频数据。"""

    raw_bytes: bytes = b""
    duration_seconds: float = 0.0
    sample_rate: int = audio_cfg.SAMPLE_RATE
    channels: int = audio_cfg.CHANNELS
    sample_width: int = audio_cfg.SAMPLE_WIDTH

    @property
    def is_valid(self) -> bool:
        """音频数据是否有效。"""
        return len(self.raw_bytes) > 0


class AudioCaptureError(Exception):
    """音频录制异常。"""

    pass


class AudioCapture:
    """麦克风音频录制器。

    功能:
    - 从默认麦克风捕获音频
    - 生成标准 WAV 文件
    - 支持实时音频数据回调

    Signal 接口 (后续与 Qt 集成):
    - started: 录制开始
    - stopped: 录制结束
    - data_available: 新音频数据可用
    - rms_level: 当前 RMS 音量水平
    """

    def __init__(
        self,
        output_dir: Optional[Path] = None,
        sample_rate: int = audio_cfg.SAMPLE_RATE,
        channels: int = audio_cfg.CHANNELS,
        sample_width: int = audio_cfg.SAMPLE_WIDTH,
        chunk_size: int = audio_cfg.CHUNK_SIZE,
    ) -> None:
        self._sample_rate = sample_rate
        self._channels = channels
        self._sample_width = sample_width
        self._chunk_size = chunk_size
        self._output_dir = output_dir or Path(tempfile.gettempdir()) / "voicecalendar"

        self._is_recording: bool = False
        self._frames: list[bytes] = []
        self._segment: Optional[AudioSegment] = None
        self._output_path: Optional[Path] = None

        # RMS 回调 (供波形可视化使用)
        self._rms_callback: Optional[callable] = None  # type: ignore[name-defined]

        # 确保输出目录存在
        self._output_dir.mkdir(parents=True, exist_ok=True)

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    @property
    def output_path(self) -> Optional[Path]:
        """生成的 WAV 文件路径。"""
        return self._output_path

    @property
    def segment(self) -> Optional[AudioSegment]:
        """当前录制的音频数据。"""
        return self._segment

    def set_rms_callback(self, callback: Optional[callable]) -> None:  # type: ignore[name-defined]
        """设置 RMS 音量回调 (用于波形可视化)。"""
        self._rms_callback = callback

    def start(self) -> None:
        """开始录制。"""
        if self._is_recording:
            return

        self._is_recording = True
        self._frames = []

        try:
            import sounddevice as sd  # type: ignore[import-not-found]
        except ImportError:
            raise AudioCaptureError(
                "sounddevice 未安装。请运行: pip install sounddevice"
            )

        self._stream = sd.InputStream(
            samplerate=self._sample_rate,
            channels=self._channels,
            blocksize=self._chunk_size,
            callback=self._audio_callback,
        )
        self._stream.start()

    def stop(self) -> Path:
        """停止录制并生成 WAV 文件。

        Returns:
            WAV 文件路径
        """
        if not self._is_recording:
            raise AudioCaptureError("当前未在录制中")

        try:
            if hasattr(self, "_stream"):
                self._stream.stop()
                self._stream.close()
        except Exception:
            pass

        self._is_recording = False

        # 生成 WAV 文件
        self._segment = AudioSegment(
            raw_bytes=b"".join(self._frames),
            duration_seconds=len(self._frames) / self._sample_rate
            * self._chunk_size,
            sample_rate=self._sample_rate,
            channels=self._channels,
            sample_width=self._sample_width,
        )

        self._output_path = self._save_wav()
        self._frames = []

        return self._output_path

    def _audio_callback(self, samples: "import numpy as np; np.ndarray", frame_info) -> None:  # type: ignore[return]
        """音频数据回调。"""
        import numpy as np

        # 计算 RMS 音量
        rms = float(np.sqrt(np.mean(samples.astype(float) ** 2)))

        if self._rms_callback is not None:
            self._rms_callback(rms)

        # 将浮点数据转换为 16-bit int
        int16_samples = np.clip(samples * 32768, -32768, 32767).astype(np.int16)
        self._frames.append(int16_samples.tobytes())

    def _save_wav(self) -> Path:
        """将录制的音频保存为 WAV 文件。

        Returns:
            WAV 文件路径
        """
        import uuid

        filename = f"recording_{uuid.uuid4().hex[:12]}.wav"
        filepath = self._output_dir / filename

        with wave.open(str(filepath), "wb") as wf:
            wf.setnchannels(self._channels)
            wf.setsampwidth(self._sample_width)
            wf.setframerate(self._sample_rate)
            wf.writeframes(b"".join(self._frames))

        return filepath

    def get_rms_data(self, raw_bytes: bytes, chunk_size: int = 1024) -> list[float]:
        """从原始音频数据中提取 RMS 值序列。

        Args:
            raw_bytes: 原始音频字节数据
            chunk_size: 每块大小

        Returns:
            RMS 值列表
        """
        import numpy as np

        samples = np.frombuffer(raw_bytes, dtype=np.int16)
        rms_values = []

        for i in range(0, len(samples), chunk_size):
            chunk = samples[i : i + chunk_size].astype(float)
            rms = np.sqrt(np.mean(chunk**2))
            rms_values.append(float(rms))

        return rms_values
