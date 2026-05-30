# VoiceCalendar-Pro Windows 构建脚本
# 使用 PyInstaller 打包为独立可执行文件

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Stop"

Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "  VoiceCalendar-Pro Build Script" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""

# 1. Check Python
Write-Host "[1/5] Checking Python..." -ForegroundColor Yellow
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Python not found. Install Python 3.9+ first." -ForegroundColor Red
    exit 1
}
Write-Host "  $pythonVersion" -ForegroundColor Green

# 2. Check dependencies
Write-Host "[2/5] Checking dependencies..." -ForegroundColor Yellow
try {
    python -c "import PyQt6, openai, ics, pydantic" | Out-Null
    Write-Host "  Core dependencies OK" -ForegroundColor Green
} catch {
    Write-Host "  Installing dependencies..." -ForegroundColor Yellow
    pip install PyQt6 openai ics pydantic sounddevice numpy
}

# 3. Check PyInstaller
Write-Host "[3/5] Checking PyInstaller..." -ForegroundColor Yellow
try {
    pyinstaller --version | Out-Null
} catch {
    Write-Host "  Installing PyInstaller..." -ForegroundColor Yellow
    pip install pyinstaller
}

# 4. Clean old build
Write-Host "[4/5] Cleaning old build..." -ForegroundColor Yellow
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
if (Test-Path "VoiceCalendar.spec") { Remove-Item "VoiceCalendar.spec" }

# 5. Build
Write-Host "[5/5] Building..." -ForegroundColor Yellow
Write-Host ""

# Use backtick line-continuation to avoid PowerShell parsing issues with ;
$addDataValue = 'voicecalendar/resources' + ';' + 'voicecalendar/resources'

& pyinstaller `
    --name=VoiceCalendar-Pro `
    --onefile `
    --windowed `
    --icon=NONE `
    --add-data $addDataValue `
    --hidden-import=PyQt6 `
    --hidden-import=PyQt6.QtWidgets `
    --hidden-import=PyQt6.QtCore `
    --hidden-import=PyQt6.QtGui `
    --hidden-import=openai `
    --hidden-import=ics `
    --hidden-import=pydantic `
    --collect-all PyQt6 `
    --exclude PyQt5 `
    --exclude PySide2 `
    --exclude PySide6 `
    --distpath dist `
    voicecalendar/main.py

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "=============================================" -ForegroundColor Cyan
    Write-Host "  Build SUCCESS!" -ForegroundColor Green
    Write-Host "  Output: dist\VoiceCalendar-Pro.exe" -ForegroundColor Green
    Write-Host "=============================================" -ForegroundColor Cyan
} else {
    Write-Host ""
    Write-Host "Build FAILED. Check errors above." -ForegroundColor Red
    exit 1
}
