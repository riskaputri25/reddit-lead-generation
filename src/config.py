import os
from dataclasses import dataclass

import yaml
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    reddit_client_id: str
    reddit_client_secret: str
    reddit_user_agent: str
    anthropic_api_key: str
    deepseek_api_key: str
    database_url: str
    smtp_user: str
    smtp_pass: str
    digest_to: str


def load_settings() -> Settings:
    # ANTHROPIC_API_KEY and DEEPSEEK_API_KEY are deliberately not required here:
    # only the one matching config.yaml's llm_provider needs to be set, and
    # Scorer raises a clear error itself if the chosen provider's key is missing.
    # Reddit credentials are optional too: without them (e.g. while Reddit API
    # approval is pending) leave `subreddits: []` in config.yaml and the scan
    # runs on Substack / Hacker News only.
    required = ["DATABASE_URL"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(missing)}"
        )

    return Settings(
        reddit_client_id=os.environ.get("REDDIT_CLIENT_ID", ""),
        reddit_client_secret=os.environ.get("REDDIT_CLIENT_SECRET", ""),
        reddit_user_agent=os.environ.get("REDDIT_USER_AGENT", "lead-finder"),
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        deepseek_api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
        database_url=os.environ["DATABASE_URL"],
        smtp_user=os.environ.get("SMTP_USER", ""),
        smtp_pass=os.environ.get("SMTP_PASS", ""),
        digest_to=os.environ.get("DIGEST_TO_EMAIL", ""),
    )


def load_config(path: str = "config.yaml") -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)
