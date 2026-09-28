"""Hacker News's official Algolia-powered search API (hn.algolia.com) is
free, public, and needs no key -- the same index that powers HN's own
search box. This module fetches raw hits; normalize.py turns them into the
common lead shape."""

import datetime as dt

import requests

SEARCH_URL = "https://hn.algolia.com/api/v1/search_by_date"


def fetch_new_stories(keywords: list, lookback_hours: int, max_results_per_query: int = 25) -> list:
    """Search for each keyword and return new story/Show HN/Ask HN hits,
    deduped across keywords within this run. Comments are skipped --
    top-level posts are what's worth replying to."""
    cutoff_unix = int(
        (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=lookback_hours)).timestamp()
    )
    found = {}

    for keyword in keywords:
        params = {
            "query": keyword,
            "tags": "story",
            "numericFilters": f"created_at_i>{cutoff_unix}",
            "hitsPerPage": max_results_per_query,
        }
        try:
            resp = requests.get(SEARCH_URL, params=params, timeout=15)
            resp.raise_for_status()
            hits = resp.json().get("hits", [])
        except requests.RequestException as e:
            print(f"[hackernews] search failed for '{keyword}': {e}")
            continue

        for hit in hits:
            found[hit["objectID"]] = hit

    return list(found.values())
