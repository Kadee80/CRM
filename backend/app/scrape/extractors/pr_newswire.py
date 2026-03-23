from __future__ import annotations

from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


def extract_news_release_items(html: str, seed_url: str, max_items: int) -> list[dict[str, str]]:
  """
  Parse PR Newswire listing HTML and return candidate release URLs + link text.
  Heuristic-based: stable enough for MVP; tune selectors if the site layout changes.
  """
  soup = BeautifulSoup(html, "html.parser")
  items: list[dict[str, str]] = []
  seen: set[str] = set()
  for tag in soup.find_all("a", href=True):
    href = (tag.get("href") or "").strip()
    if not href or href.startswith("#"):
      continue
    full = urljoin(seed_url, href)
    parsed = urlparse(full)
    if parsed.scheme not in {"http", "https"}:
      continue
    host = parsed.netloc.lower()
    if "prnewswire.com" not in host:
      continue
    path = parsed.path or ""
    if "/news-releases/" not in path:
      continue
    if path.rstrip("/").endswith("news-releases-list"):
      continue
    if full in seen:
      continue
    title = (tag.get_text(" ", strip=True) or "").strip() or full
    seen.add(full)
    items.append({"url": full, "title": title[:500]})
    if len(items) >= max_items:
      break

  return items
