@echo off
chcp 65001 >nul
cd /d "%~dp0"
pip install -r requirements.txt --quiet 2>nul
python youtube_finder.py
pause
