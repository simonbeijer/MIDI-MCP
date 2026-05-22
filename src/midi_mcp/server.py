from mcp.server.fastmcp import FastMCP

from .config import ensure_output_dir

mcp = FastMCP("midi-mcp")


def run() -> None:
    ensure_output_dir()
    mcp.run()
