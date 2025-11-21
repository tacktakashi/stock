@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 決算カレンダーからデータを抽出中...
python scrape_earnings_schedule.py
pause

