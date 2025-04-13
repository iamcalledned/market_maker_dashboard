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
