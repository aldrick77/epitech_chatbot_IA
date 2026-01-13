from bs4 import BeautifulSoup


def extract_main_text(html: str) -> str:
    """
    Extract the main text content from an HTML document.
    """
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("main") or soup.body
    return " ".join(main.stripped_strings) if main else ""
