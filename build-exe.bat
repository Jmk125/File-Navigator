@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv" (
    python -m venv .venv
)
call .venv\Scripts\activate.bat
pip install -q -r requirements.txt

pyinstaller --onefile --collect-submodules send2trash --windowed --name "Project Navigator" app.py

echo.
echo Build complete: dist\Project Navigator.exe
