"""配置模块测试。"""

from voicecalendar.config import (
    AnimationConfig,
    AudioConfig,
    DarkThemeColors,
    LightThemeColors,
    ToastConfig,
    WindowConfig,
)


def test_window_config_defaults() -> None:
    cfg = WindowConfig()
    assert cfg.DEFAULT_WIDTH == 1000
    assert cfg.DEFAULT_HEIGHT == 700
    assert cfg.MIN_WIDTH == 800
    assert cfg.MIN_HEIGHT == 550
    assert cfg.CORNER_RADIUS == 16
    assert cfg.TITLEBAR_HEIGHT == 40


def test_animation_config() -> None:
    cfg = AnimationConfig()
    assert cfg.FAST < cfg.NORMAL < cfg.SLOW < cfg.VERY_SLOW
    assert cfg.TOAST_DURATION == 3000


def test_toast_config() -> None:
    cfg = ToastConfig()
    assert cfg.MAX_VISIBLE == 3
    assert cfg.WIDTH == 300
    assert cfg.HEIGHT == 48


def test_audio_config() -> None:
    cfg = AudioConfig()
    assert cfg.SAMPLE_RATE == 16000
    assert cfg.CHANNELS == 1
    assert cfg.SAMPLE_WIDTH == 2


def test_light_theme_colors() -> None:
    colors = LightThemeColors()
    assert colors.BG_PRIMARY == "#FFFFFF"
    assert colors.TEXT_PRIMARY == "#1A1D23"
    assert colors.ACCENT_PRIMARY == "#4A6CF7"


def test_dark_theme_colors() -> None:
    colors = DarkThemeColors()
    assert colors.BG_PRIMARY == "#1A1D23"
    assert colors.TEXT_PRIMARY == "#E8EAED"
    assert colors.ACCENT_PRIMARY == "#6B8AFF"
