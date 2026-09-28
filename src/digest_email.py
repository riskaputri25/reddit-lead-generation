import smtplib
from email.mime.text import MIMEText


def send_digest(smtp_user: str, smtp_pass: str, to_email: str, leads: list[dict]) -> None:
    if not (smtp_user and smtp_pass and to_email):
        print("[digest] email not configured, skipping.")
        return
    if not leads:
        return

    lines = [f"{len(leads)} new lead(s) found today:\n"]
    for lead in leads:
        label = f"r/{lead['source_name']}" if lead["source_type"] == "reddit" else lead["source_name"]
        lines.append(f"- [{lead['score']}] {label}: {lead['title']}")
        lines.append(f"  {lead['url']}")
    lines.append("\nOpen the dashboard to review, edit, and reply.")
    body = "\n".join(lines)

    msg = MIMEText(body)
    msg["Subject"] = f"Reddit Lead Finder: {len(leads)} new lead(s)"
    msg["From"] = smtp_user
    msg["To"] = to_email

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, [to_email], msg.as_string())
