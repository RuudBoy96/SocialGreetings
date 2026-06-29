@echo off
echo ========================================
echo   SocialGreetings - Starting server
echo ========================================
echo.

cd /d "%~dp0"

echo Installing dependencies...
pip install -r requirements.txt -q

echo.
echo Starting at http://localhost:5000
echo Keep this window open while using the site.
echo.

start http://localhost:5000
python app.py
