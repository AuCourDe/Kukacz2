#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${VENV_DIR:-${PROJECT_ROOT}/.venv}"
SKIP_VENV_SETUP="${SKIP_VENV_SETUP:-0}"
SKIP_REQUIREMENTS_INSTALL="${SKIP_REQUIREMENTS_INSTALL:-0}"
SKIP_APP_EXECUTION="${SKIP_APP_EXECUTION:-0}"

echo "Project root: ${PROJECT_ROOT}"
echo "Using virtual environment: ${VENV_DIR}"

if [[ "${SKIP_VENV_SETUP}" != "1" ]]; then
  if [[ ! -d "${VENV_DIR}" ]]; then
    echo "Creating virtual environment..."
    python3 -m venv "${VENV_DIR}"
  fi

  # shellcheck disable=SC1090
  source "${VENV_DIR}/bin/activate"
else
  echo "Skipping virtual environment setup (SKIP_VENV_SETUP=1)"
fi

if [[ "${SKIP_REQUIREMENTS_INSTALL}" != "1" ]]; then
  echo "Upgrading pip..."
  python -m pip install --upgrade pip

  echo "Installing dependencies..."
  python -m pip install -r "${PROJECT_ROOT}/requirements.txt"
else
  echo "Skipping dependency installation (SKIP_REQUIREMENTS_INSTALL=1)"
fi

if [[ -f "${PROJECT_ROOT}/.env" ]]; then
  echo "Loaded environment variables from .env"
else
  echo "No .env found. Create ${PROJECT_ROOT}/.env to configure secrets (see .env.example)."
fi

if [[ "${SKIP_APP_EXECUTION}" == "1" ]]; then
  echo "Skipping application execution (SKIP_APP_EXECUTION=1)"
  exit 0
fi

echo "Starting Whisper Analyzer Web Server (Flask + Backend)..."
python -m app.web_server

