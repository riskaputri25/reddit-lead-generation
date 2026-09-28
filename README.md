# Reddit Lead Finder

Scans chosen subreddits once a day, scores each new post with Claude, drafts a
reply for anything promising, emails you a digest, and gives you a small
dashboard to review, edit, and mark leads as replied. You always post the
reply yourself — nothing here posts on your behalf.

## How it fits together

```
GitHub Actions (daily cron)
  -> src/scan.py
       -> Reddit API (PRAW)         : find new posts
       -> Claude Haiku 4.5          : score every post (cheap, high volume)
       -> Claude Sonnet 5           : draft a reply for posts above threshold
       -> Supabase Postgres         : store everything
       -> Gmail SMTP                : email you today's leads

dashboard/app.py (Flask, deployed on Render)
       -> Supabase Postgres         : read/edit leads, mark replied
```

Nothing runs on your machine. The scan runs on GitHub's servers once a day;
the dashboard runs on Render whenever you open it.

## Cost (as of this build)

| Piece | Cost |
|---|---|
| Reddit API | $0 (free tier, well under the rate limit) |
| Claude API | ~$10-15/month, pay-as-you-go, billed by Anthropic |
| Supabase Postgres | $0 (free tier) |
| GitHub Actions | $0 (one run/day is trivial against the free minutes) |
| Render web service | $0 (free tier; sleeps after 15 min idle, wakes in ~30-50s) |
| Email | $0 (your own Gmail account) |

The only real recurring cost is Claude API usage, and it's metered in cents,
not dollars, at this volume.

## One-time setup

### 1. Reddit API app (OPTIONAL -- skip if you don't have access)
Reddit closed self-service API signup in late 2025 and now requires manual
approval. If you can't get credentials, leave `subreddits: []` in
`config.yaml` and skip the Reddit secrets in step 6 -- the scan runs on
Substack and Hacker News without them.

1. Go to https://www.reddit.com/prefs/apps
2. Click "create another app..." at the bottom
3. Type: **script**. Name/redirect URI can be anything (e.g. `http://localhost:8080`)
4. After creating it, note down:
   - the string under the app name (that's your `client_id`)
   - the "secret" field (that's your `client_secret`)

### 2. Model provider: Claude, DeepSeek, or both
`config.yaml` has an `llm_provider` field set to `claude` or `deepseek` — this
is the only thing that decides which one runs, so you can switch any time
without touching code. Set up the key(s) for whichever you plan to use (both
is fine too, so you can flip the setting later and already be ready):

- **Claude**: go to https://console.claude.com (separate from your claude.ai
  login — billed pay-as-you-go), create an API key. ~$10-15/month at normal
  volume, higher-quality drafts.
- **DeepSeek**: go to https://platform.deepseek.com, create an API key.
  Roughly 10x cheaper per token than Claude. Its JSON output is generally
  reliable but worth spot-checking on a handful of real posts before you
  trust it fully unattended — if `[scorer] could not parse model output`
  shows up often in the Action logs, that's your signal to switch back.

### 3. Supabase (database)
1. Create a free project at https://supabase.com
2. Open the SQL editor and run everything in `schema.sql` (in this folder).
   If you already created the `leads` table from an earlier version of this
   project and it has no real data in it yet, run `drop table leads;` first
   -- the schema changed to support more than one source (Reddit + Substack).
3. Go to Project Settings -> Database -> Connection string ("URI" format,
   use the "Transaction pooler" connection string) — this is your `DATABASE_URL`

### 4. Gmail app password (for the daily digest email)
1. Turn on 2-factor auth on the Gmail account you want to send from, if not already on
2. Go to https://myaccount.google.com/apppasswords and create an app password
3. That 16-character password is your `SMTP_PASS`; the Gmail address is `SMTP_USER`

### 5. Configure the scan
Edit `config.yaml` in this repo with:
- your product description (this is what Claude/DeepSeek scores posts against)
- your brand voice (this is how replies get drafted)
- the subreddits and keywords to watch (leave `subreddits: []` empty if Reddit
  access isn't sorted out yet -- Substack will still run fine on its own)
- the Substack publications to watch under `substack_feeds`, each as a
  `name` and its official feed URL (`https://<publication>.substack.com/feed`,
  or `https://<customdomain>/feed` for publications on their own domain).
  There's no keyword search across Substack, so list the specific
  newsletters worth watching rather than topics.
- `hackernews_keywords`: search terms for Hacker News (free official API, no
  key needed) -- catches Ask HN / Show HN posts like "looking for a tool for X"
- your score threshold (0-100; only posts above this get a drafted reply)

### 6. Push this to GitHub, then add these repo secrets
Repo -> Settings -> Secrets and variables -> Actions -> New repository secret:

- `REDDIT_CLIENT_ID` (optional, only if you have Reddit access)
- `REDDIT_CLIENT_SECRET` (optional)
- `REDDIT_USER_AGENT` (optional)
- `ANTHROPIC_API_KEY` (leave blank if you're only using DeepSeek)
- `DEEPSEEK_API_KEY` (leave blank if you're only using Claude)
- `DATABASE_URL`
- `SMTP_USER`
- `SMTP_PASS`
- `DIGEST_TO_EMAIL` (where you want the daily digest sent)

The workflow in `.github/workflows/daily_scan.yml` runs once a day
automatically. You can also trigger it manually from the Actions tab to test it.

### 7. Deploy the dashboard (Render, free tier)
1. New -> Web Service -> connect this repo
2. Root directory: `dashboard`
3. Build command: `pip install -r ../requirements.txt`
4. Start command: `gunicorn app:app`
5. Add environment variables: `DATABASE_URL`, `DASHBOARD_USER`, `DASHBOARD_PASS`
   (pick your own login for the dashboard — this is what protects it, since
   the free tier gives you a public URL)
6. Deploy. First load each day may take ~30-50 seconds to wake up.

## Day to day

- Once a day, the scan runs, scores new posts, drafts replies for the good
  ones, and emails you a digest.
- Open the dashboard link, sorted by score. Read a draft, edit it if you want,
  hit copy, open the Reddit thread, paste your reply, then mark it "replied"
  in the dashboard so it doesn't show up again.
