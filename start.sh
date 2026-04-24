#!/bin/bash

set -u

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR" || {
  echo "Error: Could not open the project root."
  exit 1
}

BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
  if [[ -n "${BACKEND_PID}" ]] && kill -0 "${BACKEND_PID}" >/dev/null 2>&1; then
    kill "${BACKEND_PID}" >/dev/null 2>&1
  fi

  if [[ -n "${FRONTEND_PID}" ]] && kill -0 "${FRONTEND_PID}" >/dev/null 2>&1; then
    kill "${FRONTEND_PID}" >/dev/null 2>&1
  fi
}

trap cleanup INT TERM EXIT

echo "🚀 Starting Sahaay..."

if ! command -v npm >/dev/null 2>&1; then
  echo "❌ npm was not found. Please install Node.js 18+ from https://nodejs.org"
  exit 1
fi

if [[ ! -f "backend/.env" ]]; then
  echo "❌ Missing backend/.env. Create it first and fill in your keys."
  exit 1
fi

if [[ ! -d "backend/venv" ]]; then
  echo "❌ Missing backend virtual environment. Run backend/setup.sh first."
  exit 1
fi

if [[ ! -f "frontend/package.json" ]]; then
  echo "❌ Frontend package.json was not found."
  exit 1
fi

if [[ ! -d "frontend/node_modules" ]]; then
  echo "❌ Frontend dependencies are missing. Run 'cd frontend && npm install' first."
  exit 1
fi

if command -v mongod >/dev/null 2>&1; then
  if ! pgrep -x "mongod" >/dev/null 2>&1; then
    echo "⚠️  MongoDB not running. Starting..."
    mkdir -p "$HOME/data/db"
    mongod --fork --logpath /tmp/mongodb.log --dbpath "$HOME/data/db" 2>/dev/null || \
      echo "❌ Could not start MongoDB. Please start it manually: mongod"
  else
    echo "✅ MongoDB is already running."
  fi
else
  echo "⚠️  mongod was not found on PATH. Please start MongoDB manually before using the app."
fi

cd backend || {
  echo "❌ Could not open the backend folder."
  exit 1
}

# shellcheck disable=SC1091
if ! source "venv/bin/activate"; then
  echo "❌ Could not activate the backend virtual environment."
  exit 1
fi

set -a
# shellcheck disable=SC1091
source ".env"
set +a

if ! command -v uvicorn >/dev/null 2>&1; then
  echo "❌ uvicorn is not available in the backend virtual environment."
  echo "Run backend/setup.sh again to install dependencies."
  exit 1
fi

uvicorn app.main:app --reload --port 8000 &
BACKEND_PID=$!
echo "✅ Backend running at http://localhost:8000"

cd ../frontend || {
  echo "❌ Could not open the frontend folder."
  exit 1
}

npm start &
FRONTEND_PID=$!
echo "✅ Frontend running at http://localhost:3000"

echo ""
echo "🎉 Sahaay is running!"
echo "   Frontend: http://localhost:3000"
echo "   Backend API: http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop all services"

wait
