#!/usr/bin/env python3
"""
Self-hosted Computer Use MCP server.

Entry point that imports from the open_open_computer_use package.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from open_open_computer_use import server

if __name__ == "__main__":
    raise SystemExit(server.main())