"""
reminders.py - Automation & Nudge Engine for Outstanding Debts
- Generates gentle multi-channel reminders (Email, Discord webhook, WhatsApp/SMS pre-filled links)
- Standalone CLI execution via cron or one-click execution from Streamlit UI
"""
import smtplib
import os
import json
import urllib.parse
import urllib.request
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import database as db
import logic

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", SMTP_USER or "noreply@debtsplitter.local")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
DRY_RUN = os.getenv("DRY_RUN", "1") == "1"
OVERDUE_DAYS = int(os.getenv("OVERDUE_DAYS", "3"))

def fmt_money(a, curr="₹"):
    return f"{curr}{float(a):,.2f}"

def build_email_body(debtor_name, payer_name, description, amount_owed, date, total, group_name="", curr="₹"):
    group_str = f" in {group_name}" if group_name else ""
    return (
        f"Hi {debtor_name},\n\n"
        f"Friendly reminder — you have an open split{group_str}:\n\n"
        f"  • Expense: {description}\n"
        f"  • Bill Total: {fmt_money(total, curr)} (Paid by {payer_name} on {date})\n"
        f"  • Your Share: {fmt_money(amount_owed, curr)}\n\n"
        f"Whenever convenient, please settle up or let {payer_name} know. "
        f"You can also mark this split as settled directly in the Smart Budgeter app.\n\n"
        f"Best regards,\nSmart Budgeter & Debt-Splitter Bot\n"
    )

def build_whatsapp_text(debtor_name, payer_name, description, amount_owed, date, curr="₹"):
    return (
        f"Hey {debtor_name}! 👋 Gentle reminder about the split for *{description}* "
        f"({date}). Your share is *{fmt_money(amount_owed, curr)}* owed to *{payer_name}*. "
        f"Let me know once you settle up! 💸"
    )

def generate_whatsapp_link(debtor_name, payer_name, description, amount_owed, date, phone="", curr="₹"):
    text = build_whatsapp_text(debtor_name, payer_name, description, amount_owed, date, curr)
    encoded = urllib.parse.quote(text)
    if phone:
        clean_phone = "".join(filter(str.isdigit, str(phone)))
        return f"https://api.whatsapp.com/send?phone={clean_phone}&text={encoded}"
    return f"https://api.whatsapp.com/send?text={encoded}"

def send_email(to_email, subject, body, is_dry_run=True):
    if is_dry_run:
        print(f"[DRY-RUN EMAIL] To: {to_email} | Subject: {subject}\n{body}\n---")
        return True, "Dry-run simulated successfully"
    if not SMTP_USER or not SMTP_PASS:
        return False, "SMTP credentials (SMTP_USER/SMTP_PASS) not configured in environment"
    msg = MIMEMultipart()
    msg["From"] = FROM_EMAIL
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        print(f"[SENT] Email to {to_email}")
        return True, "Email delivered successfully"
    except Exception as e:
        print(f"[ERROR] Email to {to_email} failed: {e}")
        return False, str(e)

def send_discord(content, webhook_url=None, is_dry_run=True):
    url = webhook_url or DISCORD_WEBHOOK_URL
    if not url:
        if is_dry_run:
            print(f"[DRY-RUN DISCORD] {content}")
            return True, "Simulated Discord webhook (no URL provided)"
        return False, "DISCORD_WEBHOOK_URL not configured"
    if is_dry_run:
        print(f"[DRY-RUN DISCORD] {content}")
        return True, "Dry-run simulated Discord notification"
    data = json.dumps({"content": content}).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as resp:
            return True, f"Discord webhook triggered (Status {resp.status})"
    except Exception as e:
        print(f"[ERROR] Discord failed: {e}")
        return False, str(e)

def send_gentle_reminders(group_id=None, overdue_days=OVERDUE_DAYS, channels=("email", "discord"), is_dry_run=None, curr="₹"):
    if is_dry_run is None:
        is_dry_run = DRY_RUN

    cutoff = (datetime.now() - timedelta(days=overdue_days)).strftime("%Y-%m-%d")
    unpaid = logic.get_unpaid_splits(group_id)
    overdue = [s for s in unpaid if s["date"] <= cutoff]

    if not overdue:
        return {"overdue": [], "sent": [], "message": f"No overdue splits older than {overdue_days} days (cutoff: {cutoff})."}

    sent = []
    discord_lines = []
    for s in overdue:
        debtor = s["debtor_name"]
        payer = s["payer_name"]
        amt = s["amount_owed"]
        desc = s["description"]
        date = s["date"]
        total = s["total"]
        email = s.get("debtor_email")
        grp = s.get("group_name", "")

        body = build_email_body(debtor, payer, desc, amt, date, total, grp, curr=curr)
        subject = f"Gentle Reminder: {fmt_money(amt, curr)} for '{desc}'"

        if "email" in channels:
            if email:
                ok, msg = send_email(email, subject, body, is_dry_run=is_dry_run)
                sent.append({
                    "channel": "email", "to": email, "debtor": debtor,
                    "amount": amt, "desc": desc, "success": ok, "msg": msg
                })
            else:
                sent.append({
                    "channel": "email", "to": "No email on file", "debtor": debtor,
                    "amount": amt, "desc": desc, "success": False, "msg": "User has no email"
                })

        discord_lines.append(f"• **{debtor}** owes **{fmt_money(amt, curr)}** to **{payer}** for *{desc}* ({date})")

    if "discord" in channels and discord_lines:
        content = (
            f"📢 **Smart Budgeter Reminders** (Overdue > {overdue_days} days):\n" +
            "\n".join(discord_lines[:12])
        )
        if len(discord_lines) > 12:
            content += f"\n...and {len(discord_lines) - 12} more pending items."
        ok, msg = send_discord(content, is_dry_run=is_dry_run)
        sent.append({"channel": "discord", "success": ok, "msg": msg})

    return {
        "overdue": overdue,
        "sent": sent,
        "message": f"Processed {len(overdue)} overdue split(s)."
    }

def print_overdue_summary(group_id=None):
    unpaid = logic.get_unpaid_splits(group_id)
    if not unpaid:
        print("No unpaid splits found.")
        return
    print(f"\nUnpaid Splits Tracker ({len(unpaid)} items):")
    cutoff = (datetime.now() - timedelta(days=OVERDUE_DAYS)).strftime("%Y-%m-%d")
    for s in unpaid:
        is_over = s["date"] <= cutoff
        status = "⚠️ OVERDUE" if is_over else "⏳ PENDING"
        print(f"  [{status}] {s['debtor_name']} owes {fmt_money(s['amount_owed'])} to {s['payer_name']} for '{s['description']}' ({s['date']})")
    print()

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Smart Budgeter - Reminder Automation")
    p.add_argument("--group", type=int, default=None, help="Group ID filter")
    p.add_argument("--overdue-days", type=int, default=OVERDUE_DAYS)
    p.add_argument("--live", action="store_true", help="Send live messages (disables dry-run)")
    p.add_argument("--summary", action="store_true", help="Print summary without dispatching")
    args = p.parse_args()

    db.init_db()
    if args.summary:
        print_overdue_summary(args.group)
    else:
        res = send_gentle_reminders(args.group, args.overdue_days, is_dry_run=not args.live)
        print(res["message"])
