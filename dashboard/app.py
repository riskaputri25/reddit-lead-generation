import os
import sys
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, Response, redirect, render_template, request, url_for

# app.py runs from inside dashboard/, but .env sits one level up in the
# repo root, so point at it explicitly rather than relying on the current
# working directory.
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.db import (  # noqa: E402
    fetch_leads,
    get_conn,
    get_daily_counts,
    get_status_counts,
    get_summary_stats,
    get_top_themes,
    update_lead,
)

app = Flask(__name__)

DASHBOARD_USER = os.environ.get("DASHBOARD_USER", "admin")
DASHBOARD_PASS = os.environ.get("DASHBOARD_PASS", "changeme")
DATABASE_URL = os.environ["DATABASE_URL"]


def check_auth(username, password):
    return username == DASHBOARD_USER and password == DASHBOARD_PASS


def authenticate():
    return Response(
        "Login required", 401, {"WWW-Authenticate": 'Basic realm="Login Required"'}
    )


def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)

    return decorated


@app.route("/")
@requires_auth
def index():
    view = request.args.get("view", "leads")
    status_filter = request.args.get("status", "new")
    conn = get_conn(DATABASE_URL)

    if view == "signals":
        leads = fetch_leads(conn, status=None, mode="signal")
    else:
        status = None if status_filter == "all" else status_filter
        leads = fetch_leads(conn, status=status, mode="reply")

    conn.close()
    return render_template("index.html", leads=leads, status_filter=status_filter, view=view)


@app.route("/analytics")
@requires_auth
def analytics():
    conn = get_conn(DATABASE_URL)
    summary = get_summary_stats(conn)
    status_counts = get_status_counts(conn)
    themes = get_top_themes(conn)
    daily_rows = get_daily_counts(conn, days=30)
    conn.close()

    # Reshape into Chart.js's {labels, datasets} shape here, in Python,
    # so the template stays simple and has no logic of its own.
    days = sorted({row["day"].isoformat() for row in daily_rows})
    sources = sorted({row["source_type"] for row in daily_rows})
    by_key = {(row["day"].isoformat(), row["source_type"]): row["n"] for row in daily_rows}
    datasets = [
        {"label": source, "data": [by_key.get((day, source), 0) for day in days]}
        for source in sources
    ]

    return render_template(
        "analytics.html",
        summary=summary,
        status_counts=status_counts,
        themes=themes,
        chart_labels=days,
        chart_datasets=datasets,
    )


@app.route("/leads/<int:lead_id>/update", methods=["POST"])
@requires_auth
def update(lead_id):
    new_status = request.form.get("status")
    new_draft = request.form.get("draft_reply")

    conn = get_conn(DATABASE_URL)
    fields = {}
    if new_status:
        fields["status"] = new_status
    if new_draft is not None:
        fields["draft_reply"] = new_draft
    update_lead(conn, lead_id, **fields)
    conn.close()

    return redirect(
        url_for(
            "index",
            status=request.args.get("status", "new"),
            view=request.args.get("view", "leads"),
        )
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
