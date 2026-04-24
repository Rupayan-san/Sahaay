@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0" || (
  echo Error: Could not open the project root.
  exit /b 1
)

echo Starting Sahaay...

if not exist "backend\.env" (
  echo Error: Missing backend\.env. Create it first and fill in your keys.
  exit /b 1
)

if not exist "backend\venv\Scripts\activate.bat" (
  echo Error: Missing backend virtual environment. Run backend\setup.bat first.
  exit /b 1
)

where npm >nul 2>nul
if errorlevel 1 (
  echo Error: npm was not found. Please install Node.js 18+ from https://nodejs.org
  exit /b 1
)

if not exist "frontend\node_modules" (
  echo Error: Frontend dependencies are missing. Run "cd frontend && npm install" first.
  exit /b 1
)

where mongod >nul 2>nul
if errorlevel 1 (
  echo Warning: mongod was not found on PATH. Make sure MongoDB is installed and running manually.
) else (
  tasklist /FI "IMAGENAME eq mongod.exe" | find /I "mongod.exe" >nul
  if errorlevel 1 (
    echo Warning: MongoDB does not appear to be running. Start it manually with: mongod
  ) else (
    echo MongoDB appears to be running.
  )
)

cd backend || (
  echo Error: Could not open the backend folder.
  exit /b 1
)

for /f "usebackq tokens=* delims=" %%i in (".env") do (
  set "line=%%i"
  if defined line (
    if not "!line:~0,1!"=="#" set "!line!"
  )
)

start "Sahaay Backend" cmd /k "call venv\Scripts\activate.bat && uvicorn app.main:app --reload --port 8000"
echo Backend starting at http://localhost:8000

cd ..\frontend || (
  echo Error: Could not open the frontend folder.
  exit /b 1
)

start "Sahaay Frontend" cmd /k "npm start"
echo Frontend starting at http://localhost:3000

echo.
echo Sahaay is running!
echo Frontend:  http://localhost:3000
echo Backend:   http://localhost:8000
echo API Docs:  http://localhost:8000/docs
endlocal
