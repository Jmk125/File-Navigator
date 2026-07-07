@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv" (
    python -m venv .venv
    call .venv\Scripts\activate.bat
    pip install -r requirements.txt
) else (
    call .venv\Scripts\activate.bat
)

pyinstaller --onefile --windowed --name "Project Navigator" app.py

echo.
echo Build complete: dist\Project Navigator.exe
