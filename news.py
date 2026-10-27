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
            # Some feeds (e.g. Human Rights Watch) start with a photo caption
            summary = re.sub(r"^Click to expand Image.*?©\s*\d{4}\s[^(]*", "", summary)
            summary = summary.replace("Click to expand Image", "").strip()
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
            "also_in": [],
            "_only_on_theme": bool(source.get("only_on_theme")),
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


# ----------------------------------------------------------------- duplicates
STOPWORDS = set(
    "the and for with from that this are was were has have had its into about after over than "
    "will not but says said say new more amid how why what who can could their they them "
    "los las una unos unas del con por para que sus son fue han como mas sobre tras entre ante "
    "desde hasta sin este esta estos estas ese esa pero muy dice segun cada contra".split()
)
NUMBER = re.compile(r"^(\d+|i|ii|iii|iv|v|vi|vii|viii|ix|x)$")


def _numbers(title: str) -> set[str]:
    """Numbers like 'Part II' or '2025', so a series' parts aren't treated as duplicates."""
    return {w for w in re.findall(r"\w+", normalize(title)) if NUMBER.match(w)}


def _words(text: str) -> set[str]:
    """Meaningful words, shortened so that 'refugees' and 'refugee' count as the same."""
    return {w[:6] for w in re.findall(r"\w+", normalize(text)) if len(w) >= 3 and w not in STOPWORDS}


def _canonical_url(url: str) -> str:
    url = re.sub(r"[?#].*$", "", url.lower()).rstrip("/")
    return re.sub(r"^https?://(www\.|amp\.)?", "", url)


def _find_duplicate(item: dict, kept: list[dict]) -> dict | None:
    """Returns the already-kept article telling the same story, if any:
    same link, nearly the same headline, or (mostly) the same text, published within 3 days."""
    item["_url"] = _canonical_url(item["link"])
    item["_title_words"] = tw = _words(item["title"])
    item["_text_words"] = xw = _words(item["excerpt"])
    item["_numbers"] = nums = _numbers(item["title"])
    for other in kept:
        if other["_url"] == item["_url"]:
            return other
        if other["language"] != item["language"]:
            continue
        if item["published"] and other["published"] and \
                abs(item["published"] - other["published"]) > timedelta(days=3):
            continue
        if nums and other["_numbers"] and nums != other["_numbers"]:
            continue
        otw, oxw = other["_title_words"], other["_text_words"]
        shared = len(tw & otw)
        if tw and otw and shared >= 4 and shared / min(len(tw), len(otw)) >= 0.7:
            return other
        if shared >= 2 and len(xw) >= 12 and len(oxw) >= 12 and len(xw & oxw) / len(xw | oxw) >= 0.5:
            return other
    return None


# ----------------------------------------------------------------- main entry
def collect_articles(settings: dict, max_days: int = 14, progress=None) -> list[dict]:
    """Returns all recent articles, newest first, with themes and length."""
    sources = settings.get("sources", [])
    patterns = compile_themes(settings.get("themes", {}))

    with ThreadPoolExecutor(max_workers=20) as pool:
        batches = list(pool.map(_fetch_feed, sources))

    cutoff = datetime.now(timezone.utc) - timedelta(days=max_days)
    articles = []
    # Direct sources first, so duplicates found via Google News are the ones dropped
    for item in sorted((a for b in batches for a in b), key=lambda a: a["is_google"]):
        if item["published"] and item["published"] < cutoff:
            continue
        text = normalize(f"{item['title']} {item['excerpt']}")
        item["themes"] = [name for name, pat in patterns.items() if pat.search(text)]
        if item.pop("_only_on_theme") and not item["themes"]:
            continue
        duplicate_of = _find_duplicate(item, articles)
        if duplicate_of:
            if item["source"] != duplicate_of["source"] and item["source"] not in duplicate_of["also_in"]:
                duplicate_of["also_in"].append(item["source"])
            continue
        articles.append(item)
    for a in articles:
        for key in ("_url", "_title_words", "_text_words", "_numbers"):
            a.pop(key, None)

    done = 0
    def measure(a):
        nonlocal done
        a["words"] = _measure_words(a)
        done += 1
        if progress:
            progress(done, len(articles))

    with ThreadPoolExecutor(max_workers=32) as pool:
        list(pool.map(measure, articles))

    for a in articles:
        a["minutes"] = max(1, round(a["words"] / WORDS_PER_MINUTE)) if a["words"] else None
        a["length"] = length_bucket(a["minutes"])
        a.pop("_feed_words", None)

    far_past = datetime(1970, 1, 1, tzinfo=timezone.utc)
    articles.sort(key=lambda a: a["published"] or far_past, reverse=True)
    return articles
