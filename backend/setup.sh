#!/bin/bash

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || {
  echo "Error: Could not open the backend folder."
  exit 1
}

WARNINGS=0

echo "Setting up the Sahaay backend..."

if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
else
  echo "Error: Python 3.11+ is not installed. Download it from https://python.org"
  exit 1
fi

if ! "$PYTHON_BIN" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >/dev/null 2>&1; then
  CURRENT_VERSION="$("$PYTHON_BIN" -c "import sys; print('.'.join(map(str, sys.version_info[:3])))")"
  echo "Error: Python 3.11+ is required. Found Python $CURRENT_VERSION."
  exit 1
fi

echo "Using $("$PYTHON_BIN" --version 2>&1)"

echo "Creating virtual environment..."
if ! "$PYTHON_BIN" -m venv venv; then
  echo "Error: Could not create the virtual environment."
  exit 1
fi

# shellcheck disable=SC1091
if ! source "venv/bin/activate"; then
  echo "Error: Could not activate the virtual environment."
  exit 1
fi

echo "Installing Python dependencies..."
if ! python -m pip install -r requirements.txt; then
  echo "Error: Dependency installation failed."
  exit 1
fi

if command -v tesseract >/dev/null 2>&1; then
  echo "Tesseract is already installed."
else
  echo "Tesseract was not found."
  if [[ "$OSTYPE" == darwin* ]]; then
    if command -v brew >/dev/null 2>&1; then
      echo "Installing Tesseract with Homebrew..."
      if ! brew install tesseract; then
        echo "Error: Homebrew could not install Tesseract."
        exit 1
      fi
    else
      echo "Error: Homebrew is required to install Tesseract on macOS."
      echo "Install Homebrew first, then run: brew install tesseract"
      exit 1
    fi
  else
    echo "Warning: Please install Tesseract using your Linux package manager."
    WARNINGS=1
  fi
fi

if command -v ffmpeg >/dev/null 2>&1; then
  echo "ffmpeg is already installed."
else
  echo "ffmpeg was not found."
  if [[ "$OSTYPE" == darwin* ]]; then
    if command -v brew >/dev/null 2>&1; then
      echo "Installing ffmpeg with Homebrew..."
      if ! brew install ffmpeg; then
        echo "Error: Homebrew could not install ffmpeg."
        exit 1
      fi
    else
      echo "Error: Homebrew is required to install ffmpeg on macOS."
      echo "Install Homebrew first, then run: brew install ffmpeg"
      exit 1
    fi
  else
    echo "Warning: Please install ffmpeg using your Linux package manager."
    WARNINGS=1
  fi
fi

if [[ "$WARNINGS" -eq 1 ]]; then
  echo "Setup finished with warnings. Install the missing system tools above before using OCR or audio features."
fi

echo "Running backend tests..."
if ! pytest tests/ -v --tb=short 2>&1; then
  echo "Error: Backend tests failed."
  exit 1
fi

echo "✅ Backend setup complete! Run start.sh to launch."
