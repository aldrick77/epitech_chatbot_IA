# mcp_client.py
from typing import Optional, Dict, Any
import asyncio
from pathlib import Path
import sys

from mcp.client import Client, StdioServerParameters  # <-- ligne corrigée


SCRAPER_SERVER = StdioServerParameters(
    command=sys.executable,
    args=[str(Path(__file__).parent / "scraper_mcp_server.py")],
    env=None,
    cwd=str(Path(__file__).parent),
)


async def call_scrape_url(url: str) -> Optional[str]:
    try:
        async with Client(SCRAPER_SERVER) as client:
            result: Dict[str, Any] = await client.call_tool(
                "scrape_url",
                arguments={"url": url},
            )
            return result.get("content", "")
    except Exception:
        return None


def scrape_url_sync(url: str) -> Optional[str]:
    try:
        return asyncio.run(call_scrape_url(url))
    except RuntimeError:
        return None
