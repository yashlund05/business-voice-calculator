@echo off
setlocal
echo ===================================================
echo Starting Voice Calculator...
echo ===================================================

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found in .venv\
    echo Please create the virtual environment first:
    echo   python -m venv .venv
    echo   .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

".venv\Scripts\python.exe" main.py %*
