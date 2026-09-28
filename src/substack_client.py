"""Every Substack publication exposes a free, official, public RSS feed at
<publication>/feed -- no API key, no auth, no scraping. This module just
fetches and date-filters those feeds; src/normalize.py turns entries into
the common lead shape."""

import datetime as dt

import feedparser


def fetch_new_entries(feed_url: str, lookback_hours: int) -> list:
    parsed = feedparser.parse(feed_url)

    if parsed.bozo and not parsed.entries:
        # bozo=True with no entries usually means the URL isn't a real feed
        # (typo, or the publication moved). Fail loud but keep scanning
        # other feeds rather than crashing the whole run.
        print(f"[substack] could not parse feed, skipping: {feed_url}")
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
