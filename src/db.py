from __future__ import annotations

import psycopg2
import psycopg2.extras


def get_conn(database_url: str):
    return psycopg2.connect(database_url)


def lead_exists(conn, external_id: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("select 1 from leads where external_id = %s", (external_id,))
        return cur.fetchone() is not None


def insert_lead(conn, lead: dict) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into leads
              (source_type, source_name, external_id, title, body, url, author,
               created_utc, score, reasoning, self_promo_allowed, draft_reply,
               mode, theme, second_use, status)
            values
              (%(source_type)s, %(source_name)s, %(external_id)s, %(title)s, %(body)s,
               %(url)s, %(author)s, to_timestamp(%(created_utc)s), %(score)s,
               %(reasoning)s, %(self_promo_allowed)s, %(draft_reply)s,
               %(mode)s, %(theme)s, %(second_use)s, 'new')
            on conflict (external_id) do nothing
            """,
            lead,
        )
    conn.commit()


def fetch_leads(conn, status: str | None = None, mode: str | None = None):
    query = "select * from leads"
    clauses = []
    params: list = []
    if status:
        clauses.append("status = %s")
        params.append(status)
    if mode:
        clauses.append("mode = %s")
        params.append(mode)
    if clauses:
        query += " where " + " and ".join(clauses)
    query += " order by score desc, scanned_at desc"
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(query, params)
        return cur.fetchall()


def update_lead(conn, lead_id: int, **fields) -> None:
    if not fields:
        return
    set_clause = ", ".join(f"{k} = %s" for k in fields)
    values = list(fields.values()) + [lead_id]
    with conn.cursor() as cur:
        cur.execute(f"update leads set {set_clause} where id = %s", values)
    conn.commit()


def get_summary_stats(conn) -> dict:
    with conn.cursor() as cur:
        cur.execute("select count(*) from leads")
        total = cur.fetchone()[0]
        cur.execute("select count(*) from leads where scanned_at >= now() - interval '7 days'")
        this_week = cur.fetchone()[0]
        cur.execute("select count(*) from leads where status = 'replied'")
        replied = cur.fetchone()[0]
        cur.execute("select count(*) from leads where mode = 'signal'")
        signals = cur.fetchone()[0]
    return {"total": total, "this_week": this_week, "replied": replied, "signals": signals}


def get_daily_counts(conn, days: int = 30) -> list:
    """One row per day per source, for the last N days. Chart-shaping
    happens in Python (app.py), not here -- this just returns raw counts."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            select date_trunc('day', scanned_at)::date as day,
                   source_type,
                   count(*) as n
            from leads
            where scanned_at >= now() - (%s || ' days')::interval
            group by 1, 2
            order by 1
            """,
            (days,),
        )
        return cur.fetchall()


def get_status_counts(conn) -> dict:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("select status, count(*) as n from leads where mode = 'reply' group by status")
        return {row["status"]: row["n"] for row in cur.fetchall()}


def get_top_themes(conn, limit: int = 8) -> list:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            select theme, second_use, count(*) as n
            from leads
            where mode = 'signal' and theme is not null
            group by theme, second_use
            order by n desc, theme
            limit %s
            """,
            (limit,),
        )
        return cur.fetchall()
