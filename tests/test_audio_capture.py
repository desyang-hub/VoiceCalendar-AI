#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""音频录制诊断脚本。

用于排查「录音文件无声」问题。

用法:
    python tests/test_audio_capture.py          # 录制 5 秒并播放
    python tests/test_audio_capture.py --list   # 列出所有输入设备
    python tests/test_audio_capture.py --duration 3  # 录制 3 秒
    python tests/test_audio_capture.py --device 2     # 指定设备 ID
"""

import sys
import argparse
from pathlib import Path

# 将项目根目录加入 path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def list_devices():
    """列出所有音频输入设备。"""
    import sounddevice as sd

    devices = sd.query_devices()
    print("\n音频设备列表:")
    print("=" * 80)
    print(f"{'ID':<5} {'名称':<35} {'输入通道':<10} {'采样率':<10} {'状态'}")
    print("-" * 80)

    for i, d in enumerate(devices):
        input_ch = d.get('max_input_channels', 0)
        if input_ch > 0:
            status = "[OK]" if d.get('default_samplerate') else "[ERR]"
            print(f"{i:<5} {d['name'][:34]:<35} {input_ch:<10} {d['default_samplerate']:<10} {status}")

    print("=" * 80)

    # 默认设备
    default_in = sd.default.device[0]
    default_info = sd.query_devices(default_in, 'input')
    print(f"\n默认输入设备: [{default_in}] {default_info['name']}")
    print(f"  输入通道: {default_info['max_input_channels']}")
    print(f"  默认采样率: {default_info['default_samplerate']}")
    print()


def record_and_save(duration=5, device_id=None):
    """录制音频并保存为 WAV。"""
    import sounddevice as sd
    import numpy as np
    import wave
    import tempfile
    import os

    print(f"\n{'='*60}")
    print(f"  音频录制诊断")
    print(f"{'='*60}")

    # 确认设备
    if device_id is not None:
        dev_info = sd.query_devices(device_id, 'input')
        print(f"输入设备: [{device_id}] {dev_info['name']}")
    else:
        default_in = sd.default.device[0]
        dev_info = sd.query_devices(default_in, 'input')
        print(f"输入设备: [{default_in}] {dev_info['name']}")
        device_id = default_in

    print(f"采样率: 16000 Hz")
    print(f"声道: 1 (mono)")
    print(f"录制时长: {duration} 秒")
    print(f"{'='*60}\n")

    # 先检测是否有声音输入
    print("正在检测麦克风...")
    test_duration = 2
    print(f"  请说话 {test_duration} 秒...")

    test_data = sd.rec(int(test_duration * 16000), samplerate=16000,
                       channels=1, dtype='int16', device=device_id)
    sd.wait()
    test_data = test_data.squeeze()

    # 分析测试数据
    max_val = np.max(np.abs(test_data))
    rms_val = np.sqrt(np.mean(test_data.astype(float) ** 2))
    nonzero_pct = np.count_nonzero(test_data) / len(test_data) * 100

    print(f"\n  麦克风检测结果:")
    print(f"    峰值: {max_val} / 32767 ({max_val/32767*100:.1f}%)")
    print(f"    RMS: {rms_val:.0f} / 32767 ({rms_val/32767*100:.1f}%)")
    print(f"    非零数据比例: {nonzero_pct:.1f}%")

    if max_val < 10:
        print("\n  [WARNING] 检测不到任何声音信号！")
        print("  可能原因:")
        print("    1. 麦克风硬件故障或未连接")
        print("    2. Windows 系统未授权麦克风访问")
        print("    3. 选择了错误的音频输入设备")
        print("    4. 麦克风音量被系统静音")
        return None
    elif max_val < 100:
        print("\n  [WARNING] 声音信号极弱，音量可能太低")
        print("  建议: 检查系统麦克风音量设置")
    else:
        print("\n  [OK] 麦克风声音信号正常")

    # 正式录制
    print(f"\n  正在录制 {duration} 秒...")
    print("  请现在开始说话...")

    frames = []
    callback_called = [0]

    def callback(indata, frames_count, time_info, status):
        if status:
            print(f"    回调状态: {status}")
        callback_called[0] += 1
        frame = indata[:frames_count].squeeze().astype(np.int16)
        frames.append(frame.tobytes())
        rms = np.sqrt(np.mean(frame.astype(float) ** 2))
        # 每 0.1 秒打印一次 RMS
        if callback_called[0] % 2 == 0:
            print(f"    RMS: {rms:.0f}")

    print()
    with sd.InputStream(
        samplerate=16000,
        channels=1,
        blocksize=1600,
        device=device_id,
        callback=callback
    ) as stream:
        sd.sleep(duration * 1000)

    print(f"\n  录制完成，共 {callback_called[0]} 个音频块")

    # 保存
    tmp_dir = Path(tempfile.gettempdir()) / "voicecalendar"
    tmp_dir.mkdir(exist_ok=True)
    filepath = tmp_dir / "diagnostic_recording.wav"

    raw_data = b"".join(frames)
    print(f"  原始数据量: {len(raw_data)} bytes ({len(raw_data)/1024:.1f} KB)")

    with wave.open(str(filepath), 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(raw_data)

    print(f"\n  WAV 文件已保存: {filepath}")
    print(f"  文件大小: {filepath.stat().st_size / 1024:.1f} KB")

    # 验证 WAV 文件
    with wave.open(str(filepath), 'rb') as wf:
        print(f"\n  WAV 文件属性:")
        print(f"    声道: {wf.getnchannels()}")
        print(f"    位深: {wf.getsampwidth() * 8} bit")
        print(f"    采样率: {wf.getframerate()} Hz")
        print(f"    帧数: {wf.getnframes()}")
        print(f"    时长: {wf.getnframes() / wf.getframerate():.2f} 秒")

        # 读取并分析
        audio = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)
        max_val = np.max(np.abs(audio))
        rms_val = np.sqrt(np.mean(audio.astype(float) ** 2))
        print(f"\n  WAV 文件分析:")
        print(f"    峰值: {max_val} / 32767 ({max_val/32767*100:.1f}%)")
        print(f"    RMS: {rms_val:.0f} / 32767 ({rms_val/32767*100:.1f}%)")

        if max_val < 10:
            print("\n  [ERROR] WAV 文件几乎没有声音数据！")
            print("  这是代码问题或系统权限问题。")
        else:
            print("\n  [OK] WAV 文件包含有效声音数据")

    # 尝试播放
    try:
        print(f"\n  尝试播放...")
        play_data = np.frombuffer(raw_data, dtype=np.int16).astype(np.float32) / 32768.0
        sd.play(play_data, 16000)
        print("  播放中... (按 Ctrl+C 停止)")
        sd.wait()
        print("  播放完成")
    except Exception as e:
        print(f"\n  播放失败 (可能没有输出设备): {e}")
        print(f"\n  请用外部播放器打开: {filepath}")

    return filepath


def test_app_audio_capture(duration=5, device_id=None):
    """用应用实际的 AudioCapture 类测试。"""
    import time
    from voicecalendar.services.audio_capture import AudioCapture, AudioCaptureError

    print(f"\n{'='*60}")
    print(f"  测试应用 AudioCapture 类")
    print(f"{'='*60}\n")

    capture = AudioCapture()

    # 检查配置
    print(f"  采样率: {capture._sample_rate}")
    print(f"  声道: {capture._channels}")
    print(f"  位深: {capture._sample_width * 8} bit")
    print(f"  块大小: {capture._chunk_size}")

    print(f"\n  正在录制 {duration} 秒...")
    capture.start()

    # 等待
    for i in range(duration, 0, -1):
        print(f"    剩余 {i} 秒...", end='\r')
        time.sleep(1)
    print("    录制完成       ")

    # 停止
    wav_path = capture.stop()
    print(f"\n  WAV 文件: {wav_path}")
    print(f"  文件大小: {wav_path.stat().st_size / 1024:.1f} KB")

    # 分析
    import wave
    import numpy as np
    with wave.open(str(wav_path), 'rb') as wf:
        print(f"\n  WAV 属性:")
        print(f"    声道: {wf.getnchannels()}")
        print(f"    位深: {wf.getsampwidth() * 8} bit")
        print(f"    采样率: {wf.getframerate()} Hz")
        print(f"    帧数: {wf.getnframes()}")
        print(f"    时长: {wf.getnframes() / wf.getframerate():.2f} 秒")

        audio = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)
        max_val = np.max(np.abs(audio))
        rms_val = np.sqrt(np.mean(audio.astype(float) ** 2))

        print(f"\n  音频分析:")
        print(f"    峰值: {max_val} / 32767 ({max_val/32767*100:.1f}%)")
        print(f"    RMS: {rms_val:.0f} / 32767 ({rms_val/32767*100:.1f}%)")

        if max_val < 10:
            print("\n  [ERROR] AudioCapture 录制无声！")
            return False
        else:
            print("\n  [OK] AudioCapture 录制正常")
            return True


def main():
    parser = argparse.ArgumentParser(description="音频录制诊断")
    parser.add_argument("--list", action="store_true", help="列出所有音频输入设备")
    parser.add_argument("--duration", type=int, default=5, help="录制时长 (秒)")
    parser.add_argument("--device", type=int, default=None, help="指定输入设备 ID")
    parser.add_argument("--app", action="store_true", help="测试应用的 AudioCapture 类")
    args = parser.parse_args()

    # 检查依赖
    try:
        import sounddevice
    except ImportError:
        print("错误: sounddevice 未安装")
        print("  pip install sounddevice")
        sys.exit(1)

    try:
        import numpy
    except ImportError:
        print("错误: numpy 未安装")
        print("  pip install numpy")
        sys.exit(1)

    if args.list:
        list_devices()
        return

    if args.app:
        # 先检测麦克风
        record_and_save(2, args.device)
        print()
        ok = test_app_audio_capture(args.duration, args.device)
        if not ok:
            print("\n建议排查:")
            print("  1. 运行 --list 查看可用设备")
            print("  2. 运行 --device <ID> 指定正确的设备")
            print("  3. 检查 Windows 系统麦克风权限")
            print("  4. 检查麦克风音量设置")
    else:
        record_and_save(args.duration, args.device)


if __name__ == "__main__":
    main()
