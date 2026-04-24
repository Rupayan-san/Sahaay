@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0" || (
  echo Error: Could not open the backend folder.
  exit /b 1
)

echo Setting up the Sahaay backend...

where py >nul 2>nul
if %errorlevel%==0 (
  set "PYTHON_CMD=py -3"
) else (
  where python >nul 2>nul
  if errorlevel 1 (
    echo Error: Python 3.11+ is not installed. Download it from https://python.org
    exit /b 1
  )
  set "PYTHON_CMD=python"
)

%PYTHON_CMD% -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"
if errorlevel 1 (
  echo Error: Python 3.11+ is required.
  exit /b 1
)

for /f "tokens=2" %%v in ('%PYTHON_CMD% --version 2^>^&1') do set "PYTHON_VERSION=%%v"
echo Using Python %PYTHON_VERSION%

echo Creating virtual environment...
%PYTHON_CMD% -m venv venv
if errorlevel 1 (
  echo Error: Could not create the virtual environment.
  exit /b 1
)

call venv\Scripts\activate.bat
if errorlevel 1 (
  echo Error: Could not activate the virtual environment.
  exit /b 1
)

echo Installing Python dependencies...
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo Error: Dependency installation failed.
  exit /b 1
)

where tesseract >nul 2>nul
if errorlevel 1 (
  echo Warning: Tesseract was not found.
  echo Please install Tesseract from https://github.com/UB-Mannheim/tesseract/wiki
) else (
  echo Tesseract is already installed.
)

where ffmpeg >nul 2>nul
if errorlevel 1 (
  echo Warning: ffmpeg was not found.
  echo Please install ffmpeg from https://ffmpeg.org/download.html
) else (
  echo ffmpeg is already installed.
)

echo Backend setup complete! Run start.bat to launch.
endlocal
