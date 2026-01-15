# mcp_client.py
from typing import Optional, Dict
import asyncio
from pathlib import Path
import sys

from mcp import ClientSession, StdioServerParameters, stdio_client


SCRAPER_SERVER = StdioServerParameters(
    command=sys.executable,
    args=[str(Path(__file__).parent / "scraper_mcp_server.py")],
    env=None,
    cwd=str(Path(__file__).parent),
)


async def call_scrape_url(url: str) -> Optional[str]:
    try:
        async with stdio_client(SCRAPER_SERVER) as streams:
            async with ClientSession(*streams) as session:
                await session.initialize()
                result = await session.call_tool(
                    "scrape_url",
                    arguments={"url": url},
                )
                if result.isError:
                    return None
                if result.structuredContent:
                    return result.structuredContent.get("content", "")
                text_parts = []
                for block in result.content:
                    if getattr(block, "type", None) == "text":
                        text_parts.append(block.text)
                if text_parts:
                    return "\n".join(text_parts)
                return ""
    except Exception:
        return None


def _read_resource_text(result) -> str:
    texts = []
    for content in result.contents:
        text = getattr(content, "text", None)
        if text:
            texts.append(text)
    return "\n".join(texts)


async def fetch_local_knowledge() -> Optional[Dict[str, str]]:
    try:
        async with stdio_client(SCRAPER_SERVER) as streams:
            async with ClientSession(*streams) as session:
                await session.initialize()
                index_result = await session.read_resource("resource://epitech/index")
                index_text = _read_resource_text(index_result).strip()
                if not index_text:
                    return {}
                names = [line.strip() for line in index_text.splitlines() if line.strip()]
                knowledge: Dict[str, str] = {}
                for name in names:
                    doc_result = await session.read_resource(f"resource://epitech/{name}")
                    doc_text = _read_resource_text(doc_result).strip()
                    if doc_text:
                        knowledge[name] = doc_text
                return knowledge
    except Exception:
        return None


