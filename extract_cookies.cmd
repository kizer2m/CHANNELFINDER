@echo off
chcp 65001 >nul
cd /d "%~dp0"
title YouTube Cookie Extractor
pip install websocket-client yt-dlp --quiet 2>nul
python cookie_extractor.py %*
pause
