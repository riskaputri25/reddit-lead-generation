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
