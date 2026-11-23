"""Stdio MCP server entrypoint for GujRERA Sovereign Real Estate Intelligence.

Executable via:
    python -m real_estate_intelligence.mcp.stdio_server
"""

import sys
from .fastmcp_app import mcp


def main():
    """Run FastMCP over standard I/O (stdio)."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
