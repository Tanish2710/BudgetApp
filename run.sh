#!/usr/bin/env bash
cd "$(dirname "$0")"
exec /home/tanishagrawal/.local/bin/python3.11 -m streamlit run app.py --server.headless true "$@"
