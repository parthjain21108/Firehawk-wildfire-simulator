@echo off
setlocal
cd /d "%~dp0"
echo ===========================================
echo  FireHawk - Wildfire Response Lab
echo ===========================================
if not exist ".venv\Scripts\python.exe" (
  where py >nul 2>nul
  if %errorlevel%==0 (
    py -3 -m venv .venv
  ) else (
    python -m venv .venv
  )
)
if not exist ".venv\Scripts\python.exe" (
  echo Could not create virtual environment. Install Python 3.10+ and retry.
  pause
  exit /b 1
)
call ".venv\Scripts\activate.bat"
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
  echo Dependency installation failed. Check internet access and run this file again.
  pause
  exit /b 1
)
python -m streamlit run app.py
pause
