#!/usr/bin/env bash

echo "=== Python Plotting Repo Setup (>=3.8) ==="

# Move to repo root
cd "$(dirname "$0")" || exit 1

VENV_DIR="venv"

# --- Find a suitable Python version ---
PYTHON_BIN=""
for ver in 3.8 3.9 3.10 3.11 3.12; do
    if command -v "python${ver}" >/dev/null 2>&1; then
        PYTHON_BIN="python${ver}"
        break
    fi
done

# Fallback to generic python3 if no specific version matched
if [ -z "$PYTHON_BIN" ]; then
    if command -v python3 >/dev/null 2>&1; then
        PYTHON_BIN="python3"
    else
        echo "Error: No suitable Python (>=3.8) installation found."
        return 1 2>/dev/null || exit 1
    fi
fi

# --- Check Python version ---
VERSION=$($PYTHON_BIN -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
MAJOR=${VERSION%%.*}
MINOR=${VERSION#*.}
if [ "$MAJOR" -lt 3 ] || [ "$MINOR" -lt 8 ]; then
    echo "Error: Python >= 3.8 required (found $VERSION)"
    return 1 2>/dev/null || exit 1
fi

echo "Using Python: $PYTHON_BIN ($VERSION)"

# --- Create venv if not present ---
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    "$PYTHON_BIN" -m venv "$VENV_DIR" || { echo "Failed to create venv"; return 1 2>/dev/null || exit 1; }

    echo "Activating virtual environment..."
    # shellcheck source=/dev/null
    source "$VENV_DIR/bin/activate"

    echo "Upgrading pip and setuptools..."
    python -m pip install --upgrade pip setuptools wheel

    if [ -f "requirements.txt" ]; then
        echo "Installing dependencies from requirements.txt..."
        pip install -r requirements.txt
    else
        echo "No requirements.txt found. Installing default plotting libraries..."
        pip install matplotlib seaborn numpy pandas plotly
    fi

    # --- Install your package in editable mode if pyproject.toml is present ---
    if [ -f "pyproject.toml" ]; then
        echo "Detected pyproject.toml — installing project in editable mode..."
        pip install -e .
    fi

    echo "=== Setup complete. ==="
else
    echo "Virtual environment already exists. Activating..."
    # shellcheck source=/dev/null
    source "$VENV_DIR/bin/activate"
    echo "Environment activated using $("$VENV_DIR/bin/python" -V)"
fi
