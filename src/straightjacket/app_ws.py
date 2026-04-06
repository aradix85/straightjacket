#!/usr/bin/env python3
"""Straightjacket — Starlette entry point.

Start with: python src/straightjacket/app_ws.py
Or via uvicorn: uvicorn straightjacket.web.server:app --reload
"""

import sys
from pathlib import Path

_src = Path(__file__).resolve().parent.parent
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from straightjacket.engine import cfg, log, setup_file_logging

setup_file_logging()

port = cfg().server.port
log(f"[Server] Starting Straightjacket on port {port}")

import uvicorn

from straightjacket.web.server import app

uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
