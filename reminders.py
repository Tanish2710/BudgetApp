"""
reminders.py - Payment reminder engine

- Builds one consolidated statement per person who owes money (per circle breakdown,
  consistent with recorded settlements and items marked paid)
- Sends multipart HTML + plain-text email over SMTP (STARTTLS or SSL), or simulates it
- Automatic reminders: a daily schedule, an overdue threshold, a per-person cooldown
  and a minimum amount, all stored in the app database and shared by the Streamlit app
  and the CLI, so running both never double-sends
- Every attempt is written to the reminder_log table

CLI:
    python reminders.py --summary          # who owes what and who is due a reminder
    python reminders.py --run-now          # send due reminders now (dry-run unless live mode is on)
    python reminders.py --auto             # cron entry point: only runs if today's scheduled run is due
"""
import html
import os
import smtplib
import threading
import time
from datetime import datetime, date, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, make_msgid, formatdate

import database as db
import logic

APP_NAME = "Smart Budgeter"

DEFAULT_SETTINGS = {
    "currency": "₹",
    # Automatic reminders
    "auto_enabled": False,
    "live_mode": False,          # False = dry-run: emails are rendered and logged, never sent
    "overdue_days": 3,           # only remind once the oldest open item is this old
    "cadence_days": 3,           # minimum days between reminders to the same person
    "min_amount": 1.0,           # ignore balances below this
    "send_hour": 9,              # local hour for the daily run
    "last_auto_run_date": None,  # ISO date of the last claimed automatic run
    # SMTP (environment variables are used for anything left blank)
    "smtp_host": "",
    "smtp_port": 0,
    "smtp_user": "",
    "smtp_pass": "",
    "from_email": "",
    "sender_name": APP_NAME,
}

SMTP_KEYS = ["smtp_host", "smtp_port", "smtp_user", "smtp_pass", "from_email", "sender_name"]


# ---------------------------------------------------------------------------
# Settings & credentials
# ---------------------------------------------------------------------------
def get_settings():
    db.init_db()
    return db.get_settings(DEFAULT_SETTINGS)


def save_settings(values):
    unknown = set(values) - set(DEFAULT_SETTINGS)
    if unknown:
        raise KeyError(f"Unknown reminder settings: {sorted(unknown)}")
    db.set_settings(values)


def get_smtp_credentials(settings=None):
    """Resolve SMTP settings: saved settings first, then environment variables."""
    s = settings if settings is not None else get_settings()
    host = s.get("smtp_host") or os.getenv("SMTP_HOST", "smtp.gmail.com")
    port = int(s.get("smtp_port") or os.getenv("SMTP_PORT", "587"))
    user = s.get("smtp_user") or os.getenv("SMTP_USER", "")
    passwd = s.get("smtp_pass") or os.getenv("SMTP_PASS", "")
    from_email = s.get("from_email") or os.getenv("FROM_EMAIL", "") or user
    sender_name = s.get("sender_name") or APP_NAME
    return {"host": host, "port": port, "user": user, "pass": passwd,
            "from_email": from_email, "sender_name": sender_name}


def smtp_is_configured(settings=None):
    c = get_smtp_credentials(settings)
    return bool(c["user"] and c["pass"] and c["from_email"])


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------
def fmt_money(a, curr="₹"):
    try:
        v = float(a)
    except (ValueError, TypeError):
        v = 0.0
    sign = "-" if v < 0 else ""
    return f"{sign}{curr}{abs(v):,.2f}"


def _fmt_date(iso):
    try:
        return date.fromisoformat(str(iso)[:10]).strftime("%d %b %Y")
    except ValueError:
        return str(iso)


def _days_phrase(n):
    if n <= 0:
        return "today"
    return "1 day" if n == 1 else f"{n} days"


# ---------------------------------------------------------------------------
# Email content
# ---------------------------------------------------------------------------
def build_subject(statement, curr="₹"):
    circles = statement["circles"]
    where = circles[0]["group_name"] if len(circles) == 1 else f"{len(circles)} circles"
    return f"Payment reminder: {fmt_money(statement['total_owed'], curr)} outstanding ({where})"


def build_statement_plain(statement, curr="₹", sender_name=APP_NAME):
    lines = [
        f"Hi {statement['name']},",
        "",
        f"This is a reminder that you have an outstanding balance of "
        f"{fmt_money(statement['total_owed'], curr)} on {APP_NAME}.",
        f"The oldest open item dates from {_fmt_date(statement['oldest_due'])} "
        f"({_days_phrase(statement['days_outstanding'])} ago).",
        "",
    ]
    for c in statement["circles"]:
        lines.append(f"{c['group_name']}")
        lines.append("-" * len(c["group_name"]))
        for it in c["items"]:
            lines.append(f"  {_fmt_date(it['date'])}  {it['description']} (paid by {it['payer_name']})"
                         f"  {fmt_money(it['amount_owed'], curr)}")
        if c["credits"] > 0.004:
            lines.append(f"  Payments and credits  -{fmt_money(c['credits'], curr)}")
        lines.append(f"  Balance due  {fmt_money(c['owed'], curr)}")
        if c["transfers"]:
            lines.append("  To settle:")
            for t in c["transfers"]:
                lines.append(f"    Pay {t['to_name']} {fmt_money(t['amount'], curr)}")
        lines.append("")
    lines += [
        "Once you've paid, ask the person you paid to record it in the app and this reminder will stop.",
        "",
        "Thanks,",
        sender_name,
    ]
    return "\n".join(lines)


def build_statement_html(statement, curr="₹", sender_name=APP_NAME):
    """Email-safe HTML (table layout, inline styles, all user content escaped)."""
    e = html.escape
    ink, muted, line, accent = "#0b0b0b", "#6b6a66", "#e6e5e0", "#2a78d6"
    font = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"

    circle_blocks = []
    for c in statement["circles"]:
        rows = []
        for it in c["items"]:
            rows.append(f"""
              <tr>
                <td style="padding:10px 0;border-bottom:1px solid {line};font-size:14px;color:{ink};">
                  {e(str(it['description']))}
                  <div style="font-size:12px;color:{muted};margin-top:2px;">{e(_fmt_date(it['date']))} &middot; paid by {e(str(it['payer_name']))}</div>
                </td>
                <td align="right" style="padding:10px 0;border-bottom:1px solid {line};font-size:14px;color:{ink};white-space:nowrap;">{e(fmt_money(it['amount_owed'], curr))}</td>
              </tr>""")
        if c["credits"] > 0.004:
            rows.append(f"""
              <tr>
                <td style="padding:10px 0;border-bottom:1px solid {line};font-size:14px;color:{muted};">Payments and credits</td>
                <td align="right" style="padding:10px 0;border-bottom:1px solid {line};font-size:14px;color:{muted};white-space:nowrap;">&minus;{e(fmt_money(c['credits'], curr))}</td>
              </tr>""")
        rows.append(f"""
              <tr>
                <td style="padding:12px 0 4px 0;font-size:14px;font-weight:600;color:{ink};">Balance due</td>
                <td align="right" style="padding:12px 0 4px 0;font-size:14px;font-weight:600;color:{ink};white-space:nowrap;">{e(fmt_money(c['owed'], curr))}</td>
              </tr>""")
        transfers = "".join(
            f"<li style='margin:2px 0;'>Pay <strong>{e(t['to_name'])}</strong> {e(fmt_money(t['amount'], curr))}</li>"
            for t in c["transfers"]
        )
        settle_html = (f"""
            <div style="margin-top:12px;padding:12px 14px;background:#f5f8fd;border-radius:6px;font-size:13px;color:{ink};">
              <div style="font-weight:600;margin-bottom:4px;">How to settle</div>
              <ul style="margin:0;padding-left:18px;">{transfers}</ul>
            </div>""" if transfers else "")
        circle_blocks.append(f"""
          <tr><td style="padding:20px 32px 4px 32px;">
            <div style="font-size:12px;font-weight:600;letter-spacing:.04em;text-transform:uppercase;color:{muted};">{e(c['group_name'])}</div>
            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;margin-top:6px;">
              {''.join(rows)}
            </table>
            {settle_html}
          </td></tr>""")

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Payment reminder</title></head>
<body style="margin:0;padding:0;background:#f4f4f1;font-family:{font};">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f4f4f1;padding:24px 12px;">
    <tr><td align="center">
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:560px;background:#ffffff;border:1px solid {line};border-radius:10px;">
        <tr><td style="padding:24px 32px 0 32px;">
          <div style="font-size:14px;font-weight:700;color:{ink};">
            <span style="display:inline-block;width:10px;height:10px;background:{accent};border-radius:2px;margin-right:8px;vertical-align:middle;"></span>{e(APP_NAME)}
          </div>
        </td></tr>
        <tr><td style="padding:20px 32px 0 32px;">
          <div style="font-size:15px;color:{ink};">Hi {e(statement['name'])},</div>
          <div style="font-size:14px;line-height:1.55;color:{muted};margin-top:8px;">
            This is a friendly reminder about your outstanding balance. The oldest open item is from
            {e(_fmt_date(statement['oldest_due']))} ({e(_days_phrase(statement['days_outstanding']))} ago).
          </div>
        </td></tr>
        <tr><td style="padding:20px 32px 0 32px;">
          <div style="border:1px solid {line};border-radius:8px;padding:18px 20px;">
            <div style="font-size:12px;color:{muted};">Total outstanding</div>
            <div style="font-size:28px;font-weight:700;color:{ink};margin-top:2px;letter-spacing:-0.01em;">{e(fmt_money(statement['total_owed'], curr))}</div>
          </div>
        </td></tr>
        {''.join(circle_blocks)}
        <tr><td style="padding:20px 32px 28px 32px;font-size:13px;line-height:1.55;color:{muted};">
          Once you've paid, ask the person you paid to record it in {e(APP_NAME)} and these reminders will stop.
          <br><br>Thanks,<br>{e(sender_name)}
        </td></tr>
      </table>
      <div style="font-size:11px;color:#9a9993;margin-top:14px;">Sent by {e(APP_NAME)} on behalf of your circle.</div>
    </td></tr>
  </table>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Delivery
# ---------------------------------------------------------------------------
def _smtp_connect(creds, timeout=15):
    if int(creds["port"]) == 465:
        server = smtplib.SMTP_SSL(creds["host"], creds["port"], timeout=timeout)
        server.ehlo()
    else:
        server = smtplib.SMTP(creds["host"], creds["port"], timeout=timeout)
        server.ehlo()
        if server.has_extn("starttls"):
            server.starttls()
            server.ehlo()
    server.login(creds["user"], creds["pass"])
    return server


def send_email(to_email, subject, plain_body, html_body=None, is_dry_run=True, settings=None):
    """Send (or simulate) a multipart email. Returns (success, message)."""
    if is_dry_run:
        return True, f"Simulated email to {to_email} (dry-run, nothing sent)"

    creds = get_smtp_credentials(settings)
    if not creds["user"] or not creds["pass"]:
        return False, "SMTP username or app password is missing. Add them under Reminders > Email delivery."

    msg = MIMEMultipart("alternative")
    msg["From"] = formataddr((creds["sender_name"], creds["from_email"]))
    msg["To"] = to_email
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=(creds["from_email"].split("@")[-1] or None))
    msg.attach(MIMEText(plain_body, "plain", "utf-8"))
    if html_body:
        msg.attach(MIMEText(html_body, "html", "utf-8"))
    try:
        with _smtp_connect(creds) as server:
            server.send_message(msg)
        return True, f"Sent to {to_email}"
    except Exception as e:  # smtplib raises a wide range of exceptions
        return False, f"Could not send to {to_email}: {e}"


def test_smtp_connection(settings=None, test_to_email=None):
    """Authenticate against the SMTP server and optionally send a short test email."""
    creds = get_smtp_credentials(settings)
    if not creds["user"] or not creds["pass"]:
        return False, "SMTP username and app password are required."
    try:
        with _smtp_connect(creds, timeout=12) as server:
            if test_to_email:
                msg = MIMEText(f"Your {APP_NAME} email settings are working.", "plain", "utf-8")
                msg["From"] = formataddr((creds["sender_name"], creds["from_email"]))
                msg["To"] = test_to_email
                msg["Subject"] = f"{APP_NAME}: test email"
                server.send_message(msg)
                return True, f"Connected to {creds['host']}:{creds['port']} and sent a test email to {test_to_email}."
        return True, f"Signed in to {creds['host']}:{creds['port']} as {creds['user']}."
    except Exception as e:
        return False, f"Connection failed: {e}"


# ---------------------------------------------------------------------------
# Queue & dispatch
# ---------------------------------------------------------------------------
def _parse_ts(ts):
    try:
        return datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return None


def get_reminder_queue(group_id=None, settings=None, now=None):
    """
    Every person who owes money, annotated with whether they're due a reminder:
      status in {"due", "cooldown", "not_overdue", "below_min", "no_email"}
    plus last_reminded (datetime or None) and next_eligible (date or None).
    """
    s = settings or get_settings()
    now = now or datetime.now()
    statements = logic.build_debtor_statements(group_id, today=now.date())
    last_sent = db.get_last_reminder_times(("sent",))
    cadence = max(0, int(s["cadence_days"]))

    for st in statements:
        last = _parse_ts(last_sent.get(st["user_id"]))
        st["last_reminded"] = last
        next_ok = (last + timedelta(days=cadence)).date() if last else None
        st["next_eligible"] = next_ok
        if not st["email"]:
            st["status"] = "no_email"
        elif st["total_owed"] < float(s["min_amount"]):
            st["status"] = "below_min"
        elif st["days_outstanding"] < int(s["overdue_days"]):
            st["status"] = "not_overdue"
        elif next_ok and now.date() < next_ok:
            st["status"] = "cooldown"
        else:
            st["status"] = "due"
    return statements


def send_statement_reminder(statement, is_dry_run=True, settings=None, trigger="manual"):
    """Render, send (or simulate) and log a reminder for one statement."""
    s = settings or get_settings()
    curr = s.get("currency") or "₹"
    creds = get_smtp_credentials(s)
    subject = build_subject(statement, curr)
    group_id = statement["circles"][0]["group_id"] if len(statement["circles"]) == 1 else None

    if not statement.get("email"):
        ok, msg, status = False, f"{statement['name']} has no email address.", "skipped"
    else:
        plain = build_statement_plain(statement, curr, creds["sender_name"])
        html_body = build_statement_html(statement, curr, creds["sender_name"])
        ok, msg = send_email(statement["email"], subject, plain, html_body, is_dry_run=is_dry_run, settings=s)
        status = ("simulated" if is_dry_run else "sent") if ok else "failed"

    db.log_reminder(statement["user_id"], group_id, statement["total_owed"], statement.get("email") or "",
                    subject, status, trigger, msg)
    return {"success": ok, "status": status, "name": statement["name"], "to": statement.get("email") or "",
            "amount": statement["total_owed"], "subject": subject, "msg": msg}


def run_reminders(group_id=None, trigger="manual", is_dry_run=None, settings=None, now=None):
    """Send reminders to everyone whose status is "due". Returns a summary dict."""
    s = settings or get_settings()
    if is_dry_run is None:
        is_dry_run = not s["live_mode"]
    queue = get_reminder_queue(group_id, s, now)
    due = [st for st in queue if st["status"] == "due"]
    results = [send_statement_reminder(st, is_dry_run=is_dry_run, settings=s, trigger=trigger) for st in due]
    ok = sum(1 for r in results if r["success"])
    verb = "simulated" if is_dry_run else "sent"
    if not due:
        message = "Nobody is due a reminder right now."
    else:
        message = f"{ok} of {len(due)} reminder(s) {verb}."
    return {"queue": queue, "results": results, "message": message, "dry_run": is_dry_run}


# ---------------------------------------------------------------------------
# Automatic schedule
# ---------------------------------------------------------------------------
def next_auto_run(settings=None, now=None):
    """The next datetime the daily automatic run will fire, or None if disabled."""
    s = settings or get_settings()
    if not s["auto_enabled"]:
        return None
    now = now or datetime.now()
    today_slot = now.replace(hour=int(s["send_hour"]), minute=0, second=0, microsecond=0)
    if s.get("last_auto_run_date") == now.date().isoformat():
        return today_slot + timedelta(days=1)
    # Past the send hour but not yet run today: due now (picked up on the next check).
    return today_slot if now < today_slot else now


def run_due_auto_reminders(now=None):
    """
    Run today's automatic reminders if enabled and past the send hour. Safe to call often
    and from several processes: the run is claimed atomically, so it happens once per day.
    Returns the run summary, or None when nothing was due.
    """
    s = get_settings()
    if not s["auto_enabled"]:
        return None
    now = now or datetime.now()
    if now.hour < int(s["send_hour"]):
        return None
    today = now.date().isoformat()
    previous = s.get("last_auto_run_date")
    if previous == today:
        return None
    if not db.compare_and_set_setting("last_auto_run_date", previous, today):
        return None  # another process claimed it
    s["last_auto_run_date"] = today
    return run_reminders(trigger="auto", settings=s, now=now)


_scheduler_lock = threading.Lock()
_scheduler_thread = None


def start_background_scheduler(interval_seconds=300):
    """Start (once per process) a daemon thread that checks the schedule every few minutes."""
    global _scheduler_thread
    with _scheduler_lock:
        if _scheduler_thread and _scheduler_thread.is_alive():
            return _scheduler_thread

        def loop():
            while True:
                try:
                    res = run_due_auto_reminders()
                    if res:
                        print(f"[reminders] automatic run: {res['message']}", flush=True)
                except Exception as e:  # keep the scheduler alive no matter what
                    print(f"[reminders] automatic run failed: {e}", flush=True)
                time.sleep(interval_seconds)

        _scheduler_thread = threading.Thread(target=loop, name="reminder-scheduler", daemon=True)
        _scheduler_thread.start()
        return _scheduler_thread


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def print_summary(group_id=None):
    s = get_settings()
    curr = s.get("currency") or "₹"
    queue = get_reminder_queue(group_id, s)
    if not queue:
        print("Nobody owes anything. All circles are settled.")
        return
    labels = {"due": "DUE", "cooldown": "COOLDOWN", "not_overdue": "NOT OVERDUE",
              "below_min": "BELOW MIN", "no_email": "NO EMAIL"}
    print(f"\nOutstanding balances ({len(queue)}):")
    for st in queue:
        print(f"  [{labels[st['status']]:>11}] {st['name']:<20} {fmt_money(st['total_owed'], curr):>14}"
              f"  oldest {st['oldest_due']} ({st['days_outstanding']}d)  {st['email'] or '-'}")
    nxt = next_auto_run(s)
    print(f"\nAutomatic reminders: {'on' if s['auto_enabled'] else 'off'}"
          f"{' - next run ' + nxt.strftime('%Y-%m-%d %H:%M') if nxt else ''}"
          f" | mode: {'live' if s['live_mode'] else 'dry-run'}\n")


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description=f"{APP_NAME} payment reminders")
    p.add_argument("--group", type=int, default=None, help="Limit to one circle (group id)")
    p.add_argument("--summary", action="store_true", help="Show balances and reminder status, send nothing")
    p.add_argument("--run-now", action="store_true", help="Send reminders to everyone currently due")
    p.add_argument("--auto", action="store_true", help="Run today's scheduled reminders if due (for cron)")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--live", action="store_true", help="Force live sending for this run")
    mode.add_argument("--dry-run", action="store_true", help="Force dry-run for this run")
    args = p.parse_args()

    db.init_db()
    if args.auto:
        res = run_due_auto_reminders()
        print(res["message"] if res else "No automatic run due (disabled, before send hour, or already ran today).")
    elif args.run_now:
        forced = True if args.dry_run else (False if args.live else None)
        res = run_reminders(args.group, trigger="cli", is_dry_run=forced)
        for r in res["results"]:
            print(f"  [{r['status']}] {r['name']} <{r['to']}> {r['msg']}")
        print(res["message"])
    else:
        print_summary(args.group)
