import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import load_config, load_settings  # noqa: E402
from src.db import get_conn, insert_lead, lead_exists  # noqa: E402
from src.digest_email import send_digest  # noqa: E402
from src.hn_client import fetch_new_stories as fetch_hn_stories  # noqa: E402
from src.normalize import (  # noqa: E402
    normalize_hn_hit,
    normalize_reddit_post,
    normalize_substack_entry,
)
from src.reddit_client import get_reddit, search_subreddit  # noqa: E402
from src.scorer import Scorer  # noqa: E402
from src.substack_client import fetch_new_entries as fetch_substack_entries  # noqa: E402


def source_label(candidate: dict) -> str:
    if candidate["source_type"] == "reddit":
        return f"r/{candidate['source_name']} (Reddit)"
    if candidate["source_type"] == "hackernews":
        return "Hacker News"
    return f"{candidate['source_name']} (Substack)"


def gather_candidates(settings, config) -> list:
    """Pull raw items from every configured source and normalize them all
    into one common shape. Adding a new source later means adding one more
    block here, plus a normalize_<source>() function -- nothing downstream
    of this function needs to change."""
    candidates = []
    lookback_hours = config.get("lookback_hours", 30)

    subreddits = config.get("subreddits") or []
    if subreddits:
        reddit = get_reddit(settings)
        for subreddit_name in subreddits:
            posts = search_subreddit(
                reddit,
                subreddit_name,
                config["keywords"],
                limit=config.get("posts_per_subreddit", 25),
                lookback_hours=lookback_hours,
            )
            candidates.extend(normalize_reddit_post(p, subreddit_name) for p in posts)

    substack_feeds = config.get("substack_feeds") or []
    for feed in substack_feeds:
        entries = fetch_substack_entries(feed["url"], lookback_hours=lookback_hours)
        candidates.extend(normalize_substack_entry(e, feed["name"]) for e in entries)

    hn_keywords = config.get("hackernews_keywords") or []
    if hn_keywords:
        hits = fetch_hn_stories(
            hn_keywords,
            lookback_hours=lookback_hours,
            max_results_per_query=config.get("posts_per_subreddit", 25),
        )
        candidates.extend(normalize_hn_hit(h) for h in hits)

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

    for candidate in gather_candidates(settings, config):
        if lead_exists(conn, candidate["external_id"]):
            continue

        try:
            result = scorer.score_post(product_desc, candidate["title"], candidate["body"])
        except Exception as e:  # noqa: BLE001
            print(f"[scan] scoring failed for {candidate['external_id']}: {e}")
            continue

        score = result.get("score", 0)
        reasoning = result.get("reason", "")
        draft_reply = None
        self_promo_allowed = None

        if score >= threshold:
            try:
                draft = scorer.draft_reply(
                    product_desc,
                    brand_voice,
                    candidate["title"],
                    candidate["body"],
                    source_label(candidate),
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
        }
        insert_lead(conn, lead)

        if score >= threshold:
            new_leads_today.append(lead)

    if new_leads_today:
        send_digest(settings.smtp_user, settings.smtp_pass, settings.digest_to, new_leads_today)

    conn.close()
    print(f"[scan] complete. {len(new_leads_today)} lead(s) above threshold.")


if __name__ == "__main__":
    main()
