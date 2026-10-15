#!/usr/bin/env bash
# Start the Smart Budgeter app. Set PYTHON to use a specific interpreter.
cd "$(dirname "$0")"
PYTHON="${PYTHON:-$(command -v python3.11 || command -v python3)}"
exec "$PYTHON" -m streamlit run app.py --server.headless true "$@"
