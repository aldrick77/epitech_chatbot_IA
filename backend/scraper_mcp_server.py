# scraper_mcp_server.py
from pathlib import Path
import re

from fastmcp import FastMCP, Context
import httpx

from html_extract import extract_main_text

# Nom logique du serveur MCP
mcp = FastMCP("EpitechScraperServer")

DATA_DIR = Path(__file__).parent / "data" / "epitech"
DOC_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


@mcp.tool
async def scrape_url(url: str, ctx: Context):
    """
    Scrape une page web publique et renvoie le texte principal.
    - url : URL complète (https://...) à scraper.
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, timeout=20, follow_redirects=True)
    resp.raise_for_status()

    text = extract_main_text(resp.text)

    # On limite la taille pour éviter les contextes trop gros
    return {
        "url": url,
        "content": text[:8000],
    }


def _list_local_doc_names() -> list[str]:
    if not DATA_DIR.exists():
        return []
    return sorted({path.stem for path in DATA_DIR.glob("*.txt")})


@mcp.resource(
    "resource://epitech/index",
    name="epitech-index",
    title="Epitech local knowledge index",
    description="List available local EPITECH knowledge document names.",
    mime_type="text/plain",
)
async def local_docs_index(ctx: Context) -> str:
    names = _list_local_doc_names()
    return "\n".join(names)


@mcp.resource(
    "resource://epitech/{name}",
    name="epitech-doc",
    title="Epitech local knowledge document",
    description="Read a local EPITECH knowledge document by name.",
    mime_type="text/plain",
)
async def local_doc(name: str, ctx: Context) -> str:
    if not DOC_NAME_RE.match(name):
        return ""
    path = DATA_DIR / f"{name}.txt"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


if __name__ == "__main__":
    # Lance le serveur MCP (processus dédié)
    mcp.run(show_banner=False, log_level="WARNING")
