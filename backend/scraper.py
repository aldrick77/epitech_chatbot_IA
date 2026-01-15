# scraper.py
import httpx

from html_extract import extract_main_text

BASE_URL = "https://www.epitech.eu"

def scrape_epitech_page(path: str) -> str:
    """
    Récupère le texte principal d'une page EPITECH (path commençant par /fr/...)
    """
    url = BASE_URL + path
    resp = httpx.get(url, timeout=20, follow_redirects=True)
    resp.raise_for_status()

    return extract_main_text(resp.text)
