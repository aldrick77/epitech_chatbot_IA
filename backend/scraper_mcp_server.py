# scraper_mcp_server.py
from fastmcp import FastMCP, Context
import httpx

from html_extract import extract_main_text

# Nom logique du serveur MCP
mcp = FastMCP("EpitechScraperServer")


@mcp.tool
async def scrape_url(url: str, ctx: Context):
    """
    Scrape une page web publique et renvoie le texte principal.
    - url : URL complète (https://...) à scraper.
    """
    await ctx.info(f"Scraping {url}")

    async with httpx.AsyncClient() as client:
        resp = await client.get(url, timeout=20)
    resp.raise_for_status()

    text = extract_main_text(resp.text)

    # On limite la taille pour éviter les contextes trop gros
    return {
        "url": url,
        "content": text[:8000],
    }


if __name__ == "__main__":
    # Lance le serveur MCP (processus dédié)
    mcp.run()
