"""Collects articles from the RSS feeds in settings.yaml, tags them by theme
and measures their length."""
from __future__ import annotations

import hashlib
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import feedparser
import requests
import trafilatura
from bs4 import BeautifulSoup

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)
WORDS_PER_MINUTE = 220
EXCERPT_CHARS = 320

# Remembers measured lengths while the app is running, so a refresh only
# measures new articles.
_length_cache: dict[str, int | None] = {}


# ----------------------------------------------------------------- helpers
def normalize(text: str) -> str:
    """Lower-case and remove accents, so 'Migración' matches 'migracion'."""
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c))


def clean_html(raw: str) -> str:
    text = BeautifulSoup(raw or "", "html.parser").get_text(" ")
    return re.sub(r"\s+", " ", text).strip()


def shorten(text: str, limit: int = EXCERPT_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(",.;:") + "…"


def compile_themes(themes: dict) -> dict[str, re.Pattern]:
    """Turns each theme's keyword list into one search pattern."""
    patterns = {}
    for name, cfg in themes.items():
        parts = []
        for kw in cfg.get("keywords", []):
            kw = normalize(str(kw).strip())
            if not kw:
                continue
            wildcard = kw.endswith("*")
            kw = re.escape(kw.rstrip("*")).replace(r"\ ", r"\s+")
            parts.append(rf"\b{kw}\w*" if wildcard else rf"\b{kw}\b")
        if parts:
            patterns[name] = re.compile("|".join(parts))
    return patterns


def length_bucket(minutes: int | None) -> str:
    if minutes is None:
        return "Unknown"
    if minutes < 3:
        return "Short (< 3 min)"
    if minutes <= 7:
        return "Medium (3–7 min)"
    return "Long (> 7 min)"


LENGTH_BUCKETS = ["Short (< 3 min)", "Medium (3–7 min)", "Long (> 7 min)", "Unknown"]


# ----------------------------------------------------------------- feeds
def _fetch_feed(source: dict) -> list[dict]:
    try:
        resp = requests.get(source["url"], headers={"User-Agent": USER_AGENT}, timeout=15)
        resp.raise_for_status()
    except requests.RequestException:
        return []
    feed = feedparser.parse(resp.content)
    is_google = "news.google.com" in source["url"]
    items = []
    for e in feed.entries:
        link = e.get("link")
        title = clean_html(e.get("title", ""))
        if not link or not title:
            continue

        when = e.get("published_parsed") or e.get("updated_parsed")
        published = datetime(*when[:6], tzinfo=timezone.utc) if when else None

        source_name = source["name"]
        if is_google:
            # Google titles look like "Headline - Newspaper"
            outlet = (e.get("source") or {}).get("title")
            if outlet and title.endswith(f" - {outlet}"):
                title = title[: -len(outlet) - 3]
            source_name = f"{outlet} (via Google News)" if outlet else source["name"]
            summary, full_text = "", ""
        else:
            summary = clean_html(e.get("summary", ""))
            full_text = clean_html(" ".join(c.get("value", "") for c in e.get("content", [])))

        image = None
        for key in ("media_content", "media_thumbnail"):
            for m in e.get(key, []) or []:
                if m.get("url"):
                    image = m["url"]
                    break
            if image:
                break
        if not image:
            for enc in e.get("enclosures", []):
                if enc.get("type", "").startswith("image") and enc.get("href"):
                    image = enc["href"]
                    break

        items.append({
            "id": hashlib.md5(link.encode()).hexdigest()[:12],
            "title": title,
            "link": link,
            "source": source_name,
            "feed": source["name"],
            "language": source.get("language", "en"),
            "published": published,
            "excerpt": shorten(summary or full_text),
            "image": image,
            "is_google": is_google,
            "_feed_words": len(full_text.split()) if full_text else 0,
        })
    return items


def _measure_words(article: dict) -> int | None:
    """Counts the words of the full article. None = could not measure."""
    if article["is_google"]:
        return None  # Google News links are redirects that can't be read
    if article["_feed_words"] >= 250:  # the feed already contains the full text
        return article["_feed_words"]
    url = article["link"]
    if url in _length_cache:
        return _length_cache[url]
    words = None
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=10)
        if resp.ok:
            text = trafilatura.extract(resp.text) or ""
            words = len(text.split()) or None
    except Exception:
        words = None
    _length_cache[url] = words
    return words


# ----------------------------------------------------------------- main entry
def collect_articles(settings: dict, max_days: int = 14, progress=None) -> list[dict]:
    """Returns all recent articles, newest first, with themes and length."""
    sources = settings.get("sources", [])
    patterns = compile_themes(settings.get("themes", {}))

    with ThreadPoolExecutor(max_workers=10) as pool:
        batches = list(pool.map(_fetch_feed, sources))

    cutoff = datetime.now(timezone.utc) - timedelta(days=max_days)
    seen_titles = set()
    articles = []
    # Direct sources first, so duplicates found via Google News are the ones dropped
    for item in sorted((a for b in batches for a in b), key=lambda a: a["is_google"]):
        if item["published"] and item["published"] < cutoff:
            continue
        key = re.sub(r"\W+", "", normalize(item["title"]))
        if key in seen_titles:
            continue
        seen_titles.add(key)
        text = normalize(f"{item['title']} {item['excerpt']}")
        item["themes"] = [name for name, pat in patterns.items() if pat.search(text)]
        articles.append(item)

    done = 0
    def measure(a):
        nonlocal done
        a["words"] = _measure_words(a)
        done += 1
        if progress:
            progress(done, len(articles))

    with ThreadPoolExecutor(max_workers=16) as pool:
        list(pool.map(measure, articles))

    for a in articles:
        a["minutes"] = max(1, round(a["words"] / WORDS_PER_MINUTE)) if a["words"] else None
        a["length"] = length_bucket(a["minutes"])
        a.pop("_feed_words", None)

    far_past = datetime(1970, 1, 1, tzinfo=timezone.utc)
    articles.sort(key=lambda a: a["published"] or far_past, reverse=True)
    return articles
