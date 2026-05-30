# VoiceCalendar-Pro 构建脚本 (Windows)
# 使用 PyInstaller 打包为独立可执行文件

$ErrorActionPreference = "Stop"

Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "  VoiceCalendar-Pro 构建脚本 (Windows)" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""

# ── 检查 Python ──
Write-Host "[1/5] 检查 Python..." -ForegroundColor Yellow
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "错误: 未找到 Python，请先安装 Python 3.9+" -ForegroundColor Red
    exit 1
}
Write-Host "  $pythonVersion" -ForegroundColor Green

# ── 检查依赖 ──
Write-Host "[2/5] 检查依赖..." -ForegroundColor Yellow
try {
    python -c "import PyQt6, openai, ics, pydantic" | Out-Null
    Write-Host "  核心依赖已安装" -ForegroundColor Green
} catch {
    Write-Host "  安装依赖中..." -ForegroundColor Yellow
    pip install PyQt6 openai ics pydantic sounddevice numpy
}

# ── 检查 PyInstaller ──
Write-Host "[3/5] 检查 PyInstaller..." -ForegroundColor Yellow
try {
    pyinstaller --version | Out-Null
} catch {
    Write-Host "  安装 PyInstaller..." -ForegroundColor Yellow
    pip install pyinstaller
}

# ── 清理旧构建 ──
Write-Host "[4/5] 清理旧构建..." -ForegroundColor Yellow
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
if (Test-Path "VoiceCalendar.spec") { Remove-Item "VoiceCalendar.spec" }

# ── 构建 ──
Write-Host "[5/5] 打包中..." -ForegroundColor Yellow
Write-Host ""

$pyinstallerArgs = @(
    "--name=VoiceCalendar-Pro",
    "--onefile",
    "--windowed",
    "--icon=NONE",
    "--add-data", "voicecalendar/resources;voicecalendar/resources",
    "--hidden-import=PyQt6",
    "--hidden-import=PyQt6.QtWidgets",
    "--hidden-import=PyQt6.QtCore",
    "--hidden-import=PyQt6.QtGui",
    "--hidden-import=openai",
    "--hidden-import=ics",
    "--hidden-import=pydantic",
    "--collect-all PyQt6",
    "--distpath", "dist",
    "voicecalendar/main.py"
)

pyinstaller $pyinstallerArgs

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "=============================================" -ForegroundColor Cyan
    Write-Host "  构建成功！" -ForegroundColor Green
    Write-Host "  可执行文件: dist\VoiceCalendar-Pro.exe" -ForegroundColor Green
    Write-Host "=============================================" -ForegroundColor Cyan
} else {
    Write-Host ""
    Write-Host "构建失败！请检查错误信息。" -ForegroundColor Red
    exit 1
}
