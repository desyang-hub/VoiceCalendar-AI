#!/usr/bin/env bash
# VoiceCalendar-Pro 构建脚本 (macOS / Linux)
# 使用 PyInstaller 打包为独立可执行文件

set -euo pipefail

echo -e "\033[36m=============================================\033[0m"
echo -e "\033[36m  VoiceCalendar-Pro 构建脚本 (macOS / Linux)\033[0m"
echo -e "\033[36m=============================================\033[0m"
echo ""

# ── 检查 Python ──
echo -e "\033[33m[1/5] 检查 Python...\033[0m"
if ! command -v python3 &> /dev/null; then
    echo -e "\033[31m错误: 未找到 Python 3，请先安装 Python 3.9+\033[0m"
    exit 1
fi
PYTHON_VERSION=$(python3 --version)
echo -e "  \033[32m$PYTHON_VERSION\033[0m"

# ── 检查依赖 ──
echo -e "\033[33m[2/5] 检查依赖...\033[0m"
if ! python3 -c "import PyQt6, openai, ics, pydantic" 2>/dev/null; then
    echo -e "  \033[33m安装依赖中...\033[0m"
    pip3 install PyQt6 openai ics pydantic sounddevice numpy
fi
echo -e "  \033[32m核心依赖已安装\033[0m"

# ── 检查 PyInstaller ──
echo -e "\033[33m[3/5] 检查 PyInstaller...\033[0m"
if ! command -v pyinstaller &> /dev/null; then
    echo -e "  \033[33m安装 PyInstaller...\033[0m"
    pip3 install pyinstaller
fi

# ── 清理旧构建 ──
echo -e "\033[33m[4/5] 清理旧构建...\033[0m"
rm -rf build dist VoiceCalendar.spec

# ── 构建 ──
echo -e "\033[33m[5/5] 打包中...\033[0m"
echo ""

pyinstaller \
    --name="VoiceCalendar-Pro" \
    --onefile \
    --windowed \
    --add-data "voicecalendar/resources:voicecalendar/resources" \
    --hidden-import=PyQt6 \
    --hidden-import=PyQt6.QtWidgets \
    --hidden-import=PyQt6.QtCore \
    --hidden-import=PyQt6.QtGui \
    --hidden-import=openai \
    --hidden-import=ics \
    --hidden-import=pydantic \
    --collect-all PyQt6 \
    --distpath dist \
    voicecalendar/main.py

if [ $? -eq 0 ]; then
    echo ""
    echo -e "\033[36m=============================================\033[0m"
    echo -e "\033[32m  构建成功！\033[0m"
    echo -e "\033[32m  可执行文件: dist/VoiceCalendar-Pro\033[0m"
    echo -e "\033[36m=============================================\033[0m"
else
    echo ""
    echo -e "\033[31m构建失败！请检查错误信息。\033[0m"
    exit 1
fi
