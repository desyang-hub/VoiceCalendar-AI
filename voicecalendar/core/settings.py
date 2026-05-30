from __future__ import annotations

"""本地配置持久化管理。

将用户设置保存到 ~/.voicecalendar/settings.json，支持读写。
"""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("voicecalendar")

# 配置文件路径
SETTINGS_DIR = Path.home() / ".voicecalendar"
SETTINGS_FILE = SETTINGS_DIR / "settings.json"

# 默认配置
DEFAULT_SETTINGS: dict[str, Any] = {
    "asr": {
        "api_key": "",
        "base_url": "https://api.openai.com/v1",
        "model": "whisper-1",
    },
    "nlu": {
        "api_key": "",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o",
    },
    "ui": {
        "dark_mode": True,
    },
}


def _ensure_dir() -> None:
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)


def load_settings() -> dict[str, Any]:
    """从文件加载配置，不存在则返回默认值。"""
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            # 合并默认值（补充新字段）
            merged = DEFAULT_SETTINGS.copy()
            for key in merged:
                if key in data:
                    if isinstance(merged[key], dict):
                        merged[key] = {**merged[key], **data[key]}
                    else:
                        merged[key] = data[key]
            return merged
        except Exception as e:
            logger.error("加载配置失败: %s", e)
    return DEFAULT_SETTINGS.copy()


def save_settings(data: dict[str, Any]) -> None:
    """保存配置到文件。"""
    _ensure_dir()
    try:
        SETTINGS_FILE.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("配置已保存到 %s", SETTINGS_FILE)
    except Exception as e:
        logger.error("保存配置失败: %s", e)


def get_asr_config() -> dict[str, str]:
    """获取 ASR 配置。"""
    data = load_settings()
    env_key = __import__("os").getenv("OPENAI_API_KEY", "")
    env_url = __import__("os").getenv("OPENAI_BASE_URL", "")

    asr = data.get("asr", {})
    return {
        "api_key": env_key or asr.get("api_key", ""),
        "base_url": env_url or asr.get("base_url", ""),
        "model": asr.get("model", "whisper-1"),
    }


def get_nlu_config() -> dict[str, str]:
    """获取 NLU 配置。"""
    data = load_settings()
    env_key = __import__("os").getenv("OPENAI_API_KEY", "")
    env_url = __import__("os").getenv("OPENAI_BASE_URL", "")

    nlu = data.get("nlu", {})
    return {
        "api_key": env_key or nlu.get("api_key", ""),
        "base_url": env_url or nlu.get("base_url", ""),
        "model": nlu.get("model", "gpt-4o"),
    }


def set_asr_config(api_key: str = "", base_url: str = "", model: str = "") -> None:
    """更新 ASR 配置。"""
    data = load_settings()
    if api_key:
        data["asr"]["api_key"] = api_key
    if base_url:
        data["asr"]["base_url"] = base_url
    if model:
        data["asr"]["model"] = model
    save_settings(data)


def set_nlu_config(api_key: str = "", base_url: str = "", model: str = "") -> None:
    """更新 NLU 配置。"""
    data = load_settings()
    if api_key:
        data["nlu"]["api_key"] = api_key
    if base_url:
        data["nlu"]["base_url"] = base_url
    if model:
        data["nlu"]["model"] = model
    save_settings(data)


def get_dark_mode() -> bool:
    data = load_settings()
    return data.get("ui", {}).get("dark_mode", True)
