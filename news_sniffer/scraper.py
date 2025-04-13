from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

def fetch_full_text_with_playwright(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, timeout=60000)
        content = page.content()
        browser.close()
        return content

def extract_text_from_html(html):
    soup = BeautifulSoup(html, 'html.parser')
    
    # Try to get the main article, or fallback to the body
    article = soup.find('article') or soup.find('main') or soup.body
    if not article:
        return ""

    text = article.get_text(separator="\n", strip=True)
    return text


import time

def fetch_full_text_from_archive_md(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
            java_script_enabled=True,
        )
        page = context.new_page()
        page.goto(url, timeout=60000)
        page.wait_for_load_state("networkidle")

        # Archive.md loads content dynamically — pause to allow full render
        time.sleep(4)

        html = page.content()
        browser.close()

        # Extract actual content from archive
        soup = BeautifulSoup(html, "html.parser")

        # Find the archived content area
        content_container = soup.find("div", id="CONTENT") or soup.find("div", class_="TEXT-BLOCK")
        text = content_container.get_text(separator="\n", strip=True) if content_container else soup.get_text()
        return text
