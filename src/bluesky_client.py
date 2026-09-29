"""Bluesky's public AT Protocol API (public.api.bsky.app) is free, official,
and needs no login for search -- the same index bsky.app's own search box
uses. This module fetches raw posts; normalize.py turns them into the
common lead shape."""

import datetime as dt

import requests

SEARCH_URL = "https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts"


def fetch_new_posts(keywords: list, lookback_hours: int, max_results_per_query: int = 25) -> list:
    """Search for each keyword and return new post hits, deduped across
    keywords within this run."""
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=lookback_hours)
    found = {}

    for keyword in keywords:
        params = {"q": keyword, "limit": max_results_per_query, "sort": "latest"}
        try:
            resp = requests.get(SEARCH_URL, params=params, timeout=15)
            resp.raise_for_status()
            posts = resp.json().get("posts", [])
        except requests.RequestException as e:
            print(f"[bluesky] search failed for '{keyword}': {e}")
            continue

        for post in posts:
            created_str = (post.get("record") or {}).get("createdAt")
            try:
                created_dt = (
                    dt.datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                    if created_str
                    else None
                )
            except ValueError:
                created_dt = None

            if created_dt and created_dt < cutoff:
                continue

            found[post["uri"]] = post

    return list(found.values())
