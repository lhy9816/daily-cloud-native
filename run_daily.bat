@echo off
cd /d D:\lihangyu\2026\2026Q1\每日云原生

REM Check if RSSHub is running
curl -s -o nul -w "" http://localhost:1200 2>nul
if errorlevel 1 (
    echo [%date% %time%] Starting RSSHub...
    start /b cmd /c "cd /d D:\lihangyu\xcode\opencode-playground\RSSHub && npm start > nul 2>&1"
    timeout /t 10 /nobreak > nul
)

.venv\Scripts\python.exe main.py >> logs\scheduler.log 2>&1
