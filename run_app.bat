@echo off
title NexusAI Dubber Studio (Windows & Android Server)
color 0B
cd /d "%~dp0"

echo ==========================================================
echo        ⚡ NexusAI Dubber Studio — Launching ⚡
echo ==========================================================
echo.
echo Starting local engine on Windows...
echo.

start "" "http://localhost:8000"

".venv\Scripts\python.exe" -m uvicorn web.app:app --host 0.0.0.0 --port 8000 --reload

pause
