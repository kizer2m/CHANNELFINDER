@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Installing / updating dependencies...
pip install -r requirements.txt --quiet
echo.
python youtube_finder.py
pause
