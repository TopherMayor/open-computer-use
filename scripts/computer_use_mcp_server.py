#!/usr/bin/env python3
"""
Self-hosted Computer Use MCP server.

Entry point that imports from the computer_use package.
"""

from computer_use import server

if __name__ == "__main__":
    raise SystemExit(server.main())