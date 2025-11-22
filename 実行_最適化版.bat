@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ========================================
echo 最適化版：決算カレンダーデータ抽出
echo ========================================
echo.
echo パッケージを確認中...
pip install aiohttp beautifulsoup4 lxml psutil --quiet 2>nul
echo.
echo データを抽出中...
python scrape_earnings_schedule_optimized.py
echo.
echo ========================================
echo 処理が完了しました
echo ========================================
pause