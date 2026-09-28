import datetime as dt

import praw


def get_reddit(settings) -> praw.Reddit:
    if not (settings.reddit_client_id and settings.reddit_client_secret):
        raise RuntimeError(
            "config.yaml lists subreddits but REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET "
            "aren't set. Set them, or leave `subreddits: []` to skip Reddit."
        )
    return praw.Reddit(
        client_id=settings.reddit_client_id,
        client_secret=settings.reddit_client_secret,
        user_agent=settings.reddit_user_agent,
    )


def search_subreddit(reddit, subreddit_name, keywords, limit, lookback_hours):
    """Search one subreddit for each keyword, dedupe within this run, and
    drop anything older than lookback_hours."""
    subreddit = reddit.subreddit(subreddit_name)
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=lookback_hours)
    found = {}

    for keyword in keywords:
        try:
            for post in subreddit.search(keyword, sort="new", time_filter="week", limit=limit):
                created = dt.datetime.fromtimestamp(post.created_utc, dt.timezone.utc)
                if created < cutoff:
                    continue
                found[post.id] = post
        except Exception as e:  # noqa: BLE001 - keep scanning other keywords/subs
            print(f"[reddit] search failed for r/{subreddit_name} / '{keyword}': {e}")

    return list(found.values())
