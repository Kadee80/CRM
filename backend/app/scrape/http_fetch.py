from __future__ import annotations

import httpx

DEFAULT_HEADERS = {
  "User-Agent": (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
  ),
  "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
  "Accept-Language": "en-US,en;q=0.9",
}


def fetch_html_httpx(url: str, timeout_seconds: float = 45.0) -> str:
  with httpx.Client(headers=DEFAULT_HEADERS, follow_redirects=True, timeout=timeout_seconds) as client:
    response = client.get(url)
    response.raise_for_status()
    return response.text


def fetch_html_playwright(url: str) -> str:
  try:
    from playwright.sync_api import sync_playwright
  except ImportError as exc:  # pragma: no cover
    raise RuntimeError("Playwright is not installed in this environment") from exc

  with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    try:
      page = browser.new_page()
      page.goto(url, wait_until="domcontentloaded", timeout=90_000)
      return page.content()
    finally:
      browser.close()


def fetch_html_with_fallback(url: str, min_links_hint: int = 3) -> tuple[str, str]:
  """
  Try lightweight HTTP first; if the listing looks empty, fall back to Playwright (worker image).
  """
  text = fetch_html_httpx(url)
  rough_count = text.lower().count("/news-releases/")
  if rough_count >= min_links_hint:
    return text, "httpx"
  try:
    return fetch_html_playwright(url), "playwright"
  except Exception:
    return text, "httpx"
