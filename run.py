#!/usr/bin/env python3
"""启动入口：python3 run.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.main import app, main  # noqa: E402,F401

if __name__ == "__main__":
    main()
