import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.bluesky_client import fetch_new_posts as fetch_bluesky_posts  # noqa: E402
from src.config import load_config, load_settings  # noqa: E402
from src.db import get_conn, insert_lead, lead_exists  # noqa: E402
from src.digest_email import send_digest  # noqa: E402
from src.hn_client import fetch_new_stories as fetch_hn_stories  # noqa: E402
from src.normalize import (  # noqa: E402
    normalize_bluesky_post,
    normalize_hn_hit,
    normalize_publication_entry,
    normalize_reddit_post,
    normalize_substack_entry,
)
from src.reddit_client import get_reddit, search_subreddit  # noqa: E402
from src.scorer import Scorer  # noqa: E402
from src.substack_client import fetch_new_entries as fetch_feed_entries  # noqa: E402


def source_label(candidate: dict) -> str:
    if candidate["source_type"] == "reddit":
        return f"r/{candidate['source_name']} (Reddit)"
    if candidate["source_type"] == "hackernews":
        return "Hacker News"
    if candidate["source_type"] == "bluesky":
        return "Bluesky"
    if candidate["source_type"] == "publication":
        return f"{candidate['source_name']} (publication, signal only)"
    return f"{candidate['source_name']} (Substack)"


def gather_candidates(settings, config) -> list:
    """Pull raw items from every configured source and normalize them all
    into one common shape. Adding a new source later means adding one more
    block here, plus a normalize_<source>() function -- nothing downstream
    of this function needs to change."""
    candidates = []
    lookback_hours = config.get("lookback_hours", 30)
    posts_per_query = config.get("posts_per_subreddit", 25)

    subreddits = config.get("subreddits") or []
    if subreddits:
        reddit = get_reddit(settings)
        for subreddit_name in subreddits:
            posts = search_subreddit(
                reddit,
                subreddit_name,
                config["keywords"],
                limit=posts_per_query,
                lookback_hours=lookback_hours,
            )
            candidates.extend(normalize_reddit_post(p, subreddit_name) for p in posts)

    substack_feeds = config.get("substack_feeds") or []
    for feed in substack_feeds:
        entries = fetch_feed_entries(feed["url"], lookback_hours=lookback_hours)
        candidates.extend(normalize_substack_entry(e, feed["name"]) for e in entries)

    hn_keywords = config.get("hackernews_keywords") or []
    if hn_keywords:
        hits = fetch_hn_stories(
            hn_keywords,
            lookback_hours=lookback_hours,
            max_results_per_query=posts_per_query,
            exclude_terms=config.get("hackernews_exclude"),
        )
        candidates.extend(normalize_hn_hit(h) for h in hits)

    bluesky_keywords = config.get("bluesky_keywords") or []
    if bluesky_keywords:
        posts = fetch_bluesky_posts(
            bluesky_keywords,
            lookback_hours=lookback_hours,
            max_results_per_query=posts_per_query,
        )
        candidates.extend(normalize_bluesky_post(p) for p in posts)

    publication_feeds = config.get("publication_feeds") or []
    for feed in publication_feeds:
        entries = fetch_feed_entries(feed["url"], lookback_hours=lookback_hours)
        candidates.extend(normalize_publication_entry(e, feed["name"]) for e in entries)

    return candidates


def main() -> None:
    settings = load_settings()
    config = load_config()

    provider = config.get("llm_provider", "claude")
    scorer = Scorer(
        provider,
        anthropic_api_key=settings.anthropic_api_key,
        deepseek_api_key=settings.deepseek_api_key,
    )
    conn = get_conn(settings.database_url)

    threshold = config.get("score_threshold", 70)
    product_desc = config["product"]["description"]
    brand_voice = config["product"]["brand_voice"]

    new_leads_today = []

    candidates = gather_candidates(settings, config)
    fetched = {}
    for c in candidates:
        fetched[c["source_type"]] = fetched.get(c["source_type"], 0) + 1
    print(f"[scan] fetched from sources: {fetched or 'nothing'}")

    already_seen = 0
    scored = []

    for candidate in candidates:
        if lead_exists(conn, candidate["external_id"]):
            already_seen += 1
            continue

        is_signal = candidate["source_type"] == "publication"

        try:
            result = scorer.score_post(
                product_desc, candidate["title"], candidate["body"], candidate["source_type"]
            )
        except Exception as e:  # noqa: BLE001
            print(f"[scan] scoring failed for {candidate['external_id']}: {e}")
            continue

        score = result.get("score", 0)
        scored.append(score)
        reasoning = result.get("reason", "")
        theme = result.get("theme") if is_signal else None
        second_use = result.get("second_use") if is_signal else None
        draft_reply = None
        self_promo_allowed = None

        # Signal-mode items (publication feeds) never get a drafted reply --
        # they're logged for you to read, not a place to comment.
        if score >= threshold and not is_signal:
            try:
                draft = scorer.draft_reply(
                    product_desc,
                    brand_voice,
                    candidate["title"],
                    candidate["body"],
                    source_label(candidate),
                    candidate["source_type"],
                )
                draft_reply = draft.get("draft_reply")
                self_promo_allowed = draft.get("self_promo_allowed")
            except Exception as e:  # noqa: BLE001
                print(f"[scan] drafting failed for {candidate['external_id']}: {e}")

        lead = {
            **candidate,
            "score": score,
            "reasoning": reasoning,
            "self_promo_allowed": self_promo_allowed,
            "draft_reply": draft_reply,
            "mode": "signal" if is_signal else "reply",
            "theme": theme,
            "second_use": second_use,
        }
        insert_lead(conn, lead)

        if score >= threshold:
            new_leads_today.append(lead)

    if new_leads_today:
        send_digest(settings.smtp_user, settings.smtp_pass, settings.digest_to, new_leads_today)

    conn.close()
    top = sorted(scored, reverse=True)[:5]
    print(f"[scan] new posts scored: {len(scored)}, already seen: {already_seen}, top scores: {top}")
    print(f"[scan] complete. {len(new_leads_today)} lead(s) above threshold.")


if __name__ == "__main__":
    main()
