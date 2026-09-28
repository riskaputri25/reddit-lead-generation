create table if not exists leads (
  id                 serial primary key,
  source_type        text not null default 'reddit', -- 'reddit' | 'substack'
  source_name        text not null,                  -- subreddit name, or Substack publication name
  external_id        text unique not null,            -- reddit post id, or the post URL for Substack
  title              text not null,
  body               text,
  url                text not null,
  author             text,
  created_utc        timestamptz not null,
  score              int not null,
  reasoning          text,
  self_promo_allowed boolean,
  draft_reply        text,
  status             text not null default 'new', -- 'new' | 'replied' | 'skipped'
  scanned_at         timestamptz not null default now()
);

create index if not exists idx_leads_score on leads (score desc);
create index if not exists idx_leads_status on leads (status);
create index if not exists idx_leads_source_type on leads (source_type);
