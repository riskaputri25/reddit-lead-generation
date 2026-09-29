"""Fetches RSS feeds for both Substack publications and public-sector
publication feeds. Substack (and some other publishers) sit behind
Cloudflare, which blocks requests that look automated based on IP address
and headers. GitHub Actions IPs are well-known data-center ranges, and
feedparser's default User-Agent is a common trigger, so we fetch with
requests using a normal browser User-Agent first and hand the raw bytes to
feedparser, rather than letting feedparser make the request itself."""

import datetime as dt

import feedparser
import requests

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}


def fetch_new_entries(feed_url: str, lookback_hours: int) -> list:
    try:
        resp = requests.get(feed_url, headers=BROWSER_HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        # Prints the actual HTTP status when there is one (403, 404, etc.)
        # so a wrong URL and a blocked request are easy to tell apart in
        # the Action log, instead of both showing as "could not parse".
        print(f"[feed] request failed, skipping: {feed_url} ({e})")
        return []

    parsed = feedparser.parse(resp.content)

    if parsed.bozo and not parsed.entries:
        print(f"[feed] could not parse feed, skipping: {feed_url}")
        return []

    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=lookback_hours)
    fresh = []

    for entry in parsed.entries:
        published = getattr(entry, "published_parsed", None)
        if published:
            published_dt = dt.datetime(*published[:6], tzinfo=dt.timezone.utc)
            if published_dt < cutoff:
                continue
        fresh.append(entry)

    return fresh
