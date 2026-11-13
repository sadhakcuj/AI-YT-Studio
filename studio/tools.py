"""Free data sources. Every function fails soft: on any network error it returns [] so a run never dies on research."""
from __future__ import annotations

import os

import httpx

UA = {"User-Agent": "ai-studio/0.1 (personal research tool)"}
TIMEOUT = 15


def _get(url: str, **kw):
    try:
        r = httpx.get(url, headers=UA, timeout=TIMEOUT, follow_redirects=True, **kw)
        r.raise_for_status()
        return r
    except Exception:
        return None


def hn_top(n: int = 20) -> list[dict]:
    """Hacker News front page via the free Algolia API."""
    r = _get("https://hn.algolia.com/api/v1/search", params={"tags": "front_page", "hitsPerPage": n})
    if not r:
        return []
    return [
        {"source": "hackernews", "title": h.get("title", ""), "score": h.get("points", 0), "url": h.get("url") or ""}
        for h in r.json().get("hits", [])
    ]


def reddit_top(subreddits: list[str], per_sub: int = 6) -> list[dict]:
    out: list[dict] = []
    for sub in subreddits:
        r = _get(f"https://www.reddit.com/r/{sub}/top.json", params={"t": "week", "limit": per_sub})
        if not r:
            continue
        for c in r.json().get("data", {}).get("children", []):
            d = c.get("data", {})
            out.append({"source": f"r/{sub}", "title": d.get("title", ""), "score": d.get("score", 0), "url": ""})
    return out


def youtube_trending(region: str = "US", n: int = 15) -> list[dict]:
    key = os.getenv("YOUTUBE_API_KEY")
    if not key:
        return []
    r = _get(
        "https://www.googleapis.com/youtube/v3/videos",
        params={"part": "snippet,statistics", "chart": "mostPopular", "regionCode": region, "maxResults": n, "key": key},
    )
    if not r:
        return []
    return [
        {
            "source": "youtube-trending",
            "title": i["snippet"]["title"],
            "score": int(i.get("statistics", {}).get("viewCount", 0)),
            "url": f"https://youtu.be/{i['id']}",
        }
        for i in r.json().get("items", [])
    ]


def youtube_search(query: str, n: int = 8) -> list[dict]:
    key = os.getenv("YOUTUBE_API_KEY")
    if not key:
        return []
    r = _get(
        "https://www.googleapis.com/youtube/v3/search",
        params={"part": "snippet", "q": query, "type": "video", "maxResults": n, "key": key},
    )
    if not r:
        return []
    return [
        {"source": "youtube", "title": i["snippet"]["title"], "url": f"https://youtu.be/{i['id'].get('videoId', '')}"}
        for i in r.json().get("items", [])
    ]


def wikipedia_search(query: str, n: int = 5) -> list[dict]:
    r = _get(
        "https://en.wikipedia.org/w/api.php",
        params={"action": "query", "list": "search", "srsearch": query, "srlimit": n, "format": "json"},
    )
    if not r:
        return []
    return [{"source": "wikipedia", "title": h["title"], "title_key": h["title"].replace(" ", "_")} for h in r.json().get("query", {}).get("search", [])]


def wikipedia_extract(title: str, max_chars: int = 3500) -> dict | None:
    r = _get(
        "https://en.wikipedia.org/w/api.php",
        params={"action": "query", "prop": "extracts", "explaintext": 1, "titles": title, "format": "json", "redirects": 1},
    )
    if not r:
        return None
    for page in r.json().get("query", {}).get("pages", {}).values():
        text = (page.get("extract") or "").strip()
        if text:
            return {
                "title": page.get("title", title),
                "url": "https://en.wikipedia.org/wiki/" + page.get("title", title).replace(" ", "_"),
                "text": text[:max_chars],
            }
    return None
