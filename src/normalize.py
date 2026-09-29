"""Every source (Reddit, Substack, Hacker News, Bluesky, publication feeds,
and anything added later) returns data in its own shape. Everything
downstream -- dedupe, scoring, drafting, storage, the dashboard -- should
only ever see one common shape. These functions are the only place that
needs to know how to read a given source's raw object."""

import datetime as dt
import re


def _strip_html(html: str) -> str:
    """Substack/RSS bodies come through as HTML. Strip tags down to plain
    text so the scorer/drafter prompts aren't full of markup."""
    text = re.sub(r"<[^>]+>", " ", html or "")
    return re.sub(r"\s+", " ", text).strip()


def normalize_reddit_post(post, subreddit_name: str) -> dict:
    return {
        "source_type": "reddit",
        "source_name": subreddit_name,
        "external_id": post.id,
        "title": post.title,
        "body": (post.selftext or "")[:5000],
        "url": f"https://reddit.com{post.permalink}",
        "author": str(post.author) if post.author else "[deleted]",
        "created_utc": post.created_utc,
    }


def normalize_hn_hit(hit: dict) -> dict:
    object_id = hit["objectID"]
    return {
        "source_type": "hackernews",
        "source_name": "Hacker News",
        "external_id": object_id,
        "title": hit.get("title") or "(untitled)",
        "body": (hit.get("story_text") or "")[:5000],
        "url": hit.get("url") or f"https://news.ycombinator.com/item?id={object_id}",
        "author": hit.get("author") or "unknown",
        "created_utc": hit.get("created_at_i") or dt.datetime.now(dt.timezone.utc).timestamp(),
    }


def normalize_substack_entry(entry, publication_name: str) -> dict:
    published = getattr(entry, "published_parsed", None)
    if published:
        created_utc = dt.datetime(*published[:6], tzinfo=dt.timezone.utc).timestamp()
    else:
        # Some feeds omit a parseable date; fall back to "now" rather than
        # dropping the post, since lookback filtering already happened
        # upstream using whatever date info was available.
        created_utc = dt.datetime.now(dt.timezone.utc).timestamp()

    raw_body = getattr(entry, "summary", "") or getattr(entry, "description", "") or ""

    return {
        "source_type": "substack",
        "source_name": publication_name,
        "external_id": entry.link,  # Substack posts have no numeric id; the URL is unique
        "title": entry.title,
        "body": _strip_html(raw_body)[:5000],
        "url": entry.link,
        "author": getattr(entry, "author", publication_name),
        "created_utc": created_utc,
    }


def normalize_publication_entry(entry, publication_name: str) -> dict:
    """Same RSS shape as Substack, but tagged as 'publication' so scan.py
    and the scorer treat it as a signal to log, not a place to reply."""
    published = getattr(entry, "published_parsed", None)
    if published:
        created_utc = dt.datetime(*published[:6], tzinfo=dt.timezone.utc).timestamp()
    else:
        created_utc = dt.datetime.now(dt.timezone.utc).timestamp()

    raw_body = getattr(entry, "summary", "") or getattr(entry, "description", "") or ""

    return {
        "source_type": "publication",
        "source_name": publication_name,
        "external_id": entry.link,
        "title": entry.title,
        "body": _strip_html(raw_body)[:5000],
        "url": entry.link,
        "author": getattr(entry, "author", publication_name),
        "created_utc": created_utc,
    }


def normalize_bluesky_post(post: dict) -> dict:
    record = post.get("record") or {}
    text = record.get("text", "") or ""

    created_str = record.get("createdAt")
    try:
        created_utc = (
            dt.datetime.fromisoformat(created_str.replace("Z", "+00:00")).timestamp()
            if created_str
            else dt.datetime.now(dt.timezone.utc).timestamp()
        )
    except ValueError:
        created_utc = dt.datetime.now(dt.timezone.utc).timestamp()

    author = post.get("author") or {}
    handle = author.get("handle", "unknown")
    rkey = post["uri"].split("/")[-1]

    return {
        "source_type": "bluesky",
        "source_name": "Bluesky",
        "external_id": post["uri"],
        "title": (text[:120] + "\u2026") if len(text) > 120 else (text or "(no text)"),
        "body": text[:5000],
        "url": f"https://bsky.app/profile/{handle}/post/{rkey}",
        "author": handle,
        "created_utc": created_utc,
    }
