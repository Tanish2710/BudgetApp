"""
reminders.py - Dedicated Email Reminder & Automation Engine for Outstanding Debts
- Generates professional HTML & Plain-text settlement statement emails
- Provides single-split instant reminder dispatch & batch automation
- Supports live SMTP delivery (Gmail, Outlook, custom SMTP) and safe Dry-Run preview
- Standalone CLI execution via cron or one-click execution from Streamlit UI
"""
import smtplib
import os
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import database as db
import logic

# Global fallback defaults from environment variables
DEFAULT_SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
DEFAULT_SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
DEFAULT_SMTP_USER = os.getenv("SMTP_USER", "")
DEFAULT_SMTP_PASS = os.getenv("SMTP_PASS", "")
DEFAULT_FROM_EMAIL = os.getenv("FROM_EMAIL", DEFAULT_SMTP_USER or "reminders@smartbudgeter.local")
DRY_RUN = os.getenv("DRY_RUN", "1") == "1"
OVERDUE_DAYS = int(os.getenv("OVERDUE_DAYS", "3"))

def fmt_money(a, curr="₹"):
    try:
        return f"{curr}{float(a):,.2f}"
    except (ValueError, TypeError):
        return f"{curr}0.00"

def get_smtp_credentials(smtp_config=None):
    """Resolves SMTP settings prioritizing custom config over environment variables."""
    cfg = smtp_config or {}
    host = cfg.get("host") or DEFAULT_SMTP_HOST
    port = int(cfg.get("port") or DEFAULT_SMTP_PORT)
    user = cfg.get("user") or DEFAULT_SMTP_USER
    passwd = cfg.get("pass") or DEFAULT_SMTP_PASS
    from_email = cfg.get("from_email") or DEFAULT_FROM_EMAIL or user or "reminders@smartbudgeter.local"
    return host, port, user, passwd, from_email

def build_email_plain(debtor_name, payer_name, description, amount_owed, date, total, group_name="", curr="₹"):
    group_str = f" ({group_name})" if group_name else ""
    return (
        f"Hi {debtor_name},\n\n"
        f"This is a friendly reminder regarding your pending share for a shared expense{group_str}:\n\n"
        f"  • Expense: {description}\n"
        f"  • Date: {date}\n"
        f"  • Bill Total: {fmt_money(total, curr)} (Paid by {payer_name})\n"
        f"  • Your Share Owed: {fmt_money(amount_owed, curr)}\n\n"
        f"Whenever convenient, please settle up with {payer_name} via your preferred payment method "
        f"(UPI, Cash, Bank Transfer, or Venmo). Once settled, this balance will be updated in the Smart Budgeter app.\n\n"
        f"Warm regards,\n"
        f"Smart Budgeter & Debt-Splitter Automated Reminders\n"
    )

def build_email_html(debtor_name, payer_name, description, amount_owed, date, total, group_name="", curr="₹"):
    group_badge = f'<span style="background:#EEF2FF; color:#4F46E5; font-size:12px; font-weight:600; padding:4px 10px; border-radius:12px; margin-left:8px;">{group_name}</span>' if group_name else ""
    formatted_amount = fmt_money(amount_owed, curr)
    formatted_total = fmt_money(total, curr)

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>Payment Reminder</title>
      <style>
        body {{
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
          background-color: #F8FAFC;
          color: #1E293B;
          margin: 0;
          padding: 24px 12px;
        }}
        .email-container {{
          max-width: 560px;
          margin: 0 auto;
          background: #FFFFFF;
          border-radius: 14px;
          border: 1px solid #E2E8F0;
          overflow: hidden;
          box-shadow: 0 4px 16px rgba(0, 0, 0, 0.04);
        }}
        .email-header {{
          background: #1E293B;
          border-bottom: 2px solid #2563EB;
          padding: 24px 28px;
          color: #FFFFFF;
        }}
        .email-header h1 {{
          margin: 0;
          font-size: 19px;
          font-weight: 700;
          letter-spacing: -0.01em;
          color: #FFFFFF;
        }}
        .email-header p {{
          margin: 4px 0 0 0;
          font-size: 12px;
          color: #94A3B8;
        }}
        .email-body {{
          padding: 26px 28px;
        }}
        .salutation {{
          font-size: 15px;
          font-weight: 600;
          color: #0F172A;
          margin-bottom: 10px;
        }}
        .amount-box {{
          background: #F8FAFC;
          border: 1px solid #E2E8F0;
          border-radius: 8px;
          padding: 18px;
          text-align: center;
          margin: 18px 0;
        }}
        .amount-label {{
          font-size: 11px;
          text-transform: uppercase;
          letter-spacing: 0.06em;
          color: #64748B;
          font-weight: 700;
          margin-bottom: 4px;
        }}
        .amount-value {{
          font-size: 30px;
          font-weight: 800;
          color: #0F172A;
          font-family: 'JetBrains Mono', Consolas, monospace;
          letter-spacing: -0.02em;
        }}
        .details-table {{
          width: 100%;
          border-collapse: collapse;
          margin: 16px 0;
          font-size: 13px;
        }}
        .details-table td {{
          padding: 9px 0;
          border-bottom: 1px solid #F1F5F9;
        }}
        .details-table td.label {{
          color: #64748B;
          font-weight: 500;
          width: 35%;
        }}
        .details-table td.value {{
          color: #0F172A;
          font-weight: 600;
          text-align: right;
        }}
        .instruction-box {{
          background: #F8FAFC;
          border: 1px solid #CBD5E1;
          border-radius: 6px;
          padding: 12px 14px;
          font-size: 13px;
          color: #334155;
          margin-top: 16px;
          line-height: 1.45;
        }}
        .email-footer {{
          padding: 20px 28px;
          background: #F8FAFC;
          border-top: 1px solid #E2E8F0;
          text-align: center;
          font-size: 12px;
          color: #94A3B8;
        }}
      </style>
    </head>
    <body>
      <div class="email-container">
        <div class="email-header">
          <h1>Expense Settlement Statement{group_badge}</h1>
          <p>Smart Budgeter &bull; Accounts Receivable</p>
        </div>
        <div class="email-body">
          <div class="salutation">Hi {debtor_name},</div>
          <p style="font-size: 14px; line-height: 1.5; color: #475569; margin: 0 0 16px 0;">
            This is a friendly statement regarding an outstanding shared expense split.
          </p>
          
          <div class="amount-box">
            <div class="amount-label">Your Share Outstanding</div>
            <div class="amount-value">{formatted_amount}</div>
          </div>

          <table class="details-table">
            <tr>
              <td class="label">Expense Item</td>
              <td class="value">{description}</td>
            </tr>
            <tr>
              <td class="label">Date Incurred</td>
              <td class="value">{date}</td>
            </tr>
            <tr>
              <td class="label">Paid Originally By</td>
              <td class="value">{payer_name}</td>
            </tr>
            <tr>
              <td class="label">Total Bill Amount</td>
              <td class="value">{formatted_total}</td>
            </tr>
          </table>

          <div class="instruction-box">
            <strong>Settlement instructions:</strong> Please settle up with <strong>{payer_name}</strong> via your preferred payment app (UPI, GPay, Cash, Bank Transfer, or Venmo). Once paid, the balance can be recorded in your circle ledger.
          </div>
        </div>
        <div class="email-footer">
          Sent automatically via Smart Budgeter &bull; Debt-Splitter Pro<br>
          Keep circle expenses clear, balanced, and fair.
        </div>
      </div>
    </body>
    </html>
    """
    return html

def send_email(to_email, subject, plain_body, html_body=None, is_dry_run=True, smtp_config=None):
    """
    Dispatches a multipart plain/HTML email or safely simulates delivery in Dry-Run mode.
    Returns: (success: bool, status_message: str, details: dict)
    """
    host, port, user, passwd, from_email = get_smtp_credentials(smtp_config)
    
    details = {
        "to": to_email,
        "from": from_email,
        "subject": subject,
        "is_dry_run": is_dry_run,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "plain_body": plain_body,
        "html_body": html_body or ""
    }

    if is_dry_run:
        print(f"[DRY-RUN EMAIL] To: {to_email} | Subject: {subject}\n{plain_body}\n---")
        return True, "Simulation Successful (Dry-Run mode: no actual email dispatched)", details

    if not user or not passwd:
        return False, "SMTP credentials (Username / App Password) are missing. Please configure them in Settings or use Dry-Run mode.", details

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = from_email
        msg["To"] = to_email
        msg["Subject"] = subject

        # Attach plain text fallback first
        msg.attach(MIMEText(plain_body, "plain", "utf-8"))

        # Attach rich HTML if provided
        if html_body:
            msg.attach(MIMEText(html_body, "html", "utf-8"))

        # Connect and send
        with smtplib.SMTP(host, port, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(user, passwd)
            server.send_message(msg)

        print(f"[SENT EMAIL] To: {to_email} | Subject: {subject}")
        return True, f"Email delivered successfully to {to_email}", details
    except Exception as e:
        err_msg = f"Failed to send email to {to_email}: {str(e)}"
        print(f"[EMAIL ERROR] {err_msg}")
        return False, err_msg, details

def test_smtp_connection(smtp_config=None, test_to_email=None):
    """Tests the SMTP connection and credentials, optionally sending a test ping."""
    host, port, user, passwd, from_email = get_smtp_credentials(smtp_config)
    if not user or not passwd:
        return False, "Missing SMTP Username or App Password."

    try:
        with smtplib.SMTP(host, port, timeout=12) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(user, passwd)
            
            if test_to_email:
                test_msg = MIMEText("This is a test notification confirming your Smart Budgeter email setup works perfectly!", "plain")
                test_msg["From"] = from_email
                test_msg["To"] = test_to_email
                test_msg["Subject"] = "Smart Budgeter - SMTP Connection Verified"
                server.send_message(test_msg)
                return True, f"Connected to {host}:{port} and dispatched test email to {test_to_email}!"
            return True, f"Successfully authenticated with SMTP host {host}:{port} as {user}."
    except Exception as e:
        return False, f"SMTP Connection Failed: {str(e)}"

def send_single_split_reminder(split, is_dry_run=True, smtp_config=None, curr="₹"):
    """
    Sends an email reminder for an individual split item.
    """
    debtor_name = split.get("debtor_name", "Friend")
    payer_name = split.get("payer_name", "a group member")
    description = split.get("description", "Shared Expense")
    amount = split.get("amount_owed", 0.0)
    date = split.get("date", "")
    total = split.get("total", amount)
    group_name = split.get("group_name", "")
    debtor_email = split.get("debtor_email")

    if not debtor_email:
        return {
            "success": False,
            "to": "Missing Email",
            "debtor": debtor_name,
            "msg": f"Debtor '{debtor_name}' does not have an email address on file. Please update their profile.",
            "subject": "",
            "details": {}
        }

    subject = f"Friendly Reminder: {fmt_money(amount, curr)} for '{description}'"
    plain_body = build_email_plain(debtor_name, payer_name, description, amount, date, total, group_name, curr)
    html_body = build_email_html(debtor_name, payer_name, description, amount, date, total, group_name, curr)

    ok, msg, details = send_email(debtor_email, subject, plain_body, html_body, is_dry_run=is_dry_run, smtp_config=smtp_config)

    return {
        "success": ok,
        "to": debtor_email,
        "debtor": debtor_name,
        "amount": amount,
        "desc": description,
        "msg": msg,
        "subject": subject,
        "details": details
    }

def send_gentle_reminders(group_id=None, overdue_days=OVERDUE_DAYS, is_dry_run=None, smtp_config=None, curr="₹"):
    """
    Finds all overdue splits beyond the day threshold and dispatches email reminders.
    """
    if is_dry_run is None:
        is_dry_run = DRY_RUN

    cutoff = (datetime.now() - timedelta(days=overdue_days)).strftime("%Y-%m-%d")
    unpaid = logic.get_unpaid_splits(group_id)
    overdue = [s for s in unpaid if s["date"] <= cutoff]

    if not overdue:
        return {
            "overdue": [],
            "sent": [],
            "total_amount": 0.0,
            "message": f"No overdue splits older than {overdue_days} day(s) (cutoff: {cutoff}). Everything is up to date!"
        }

    sent = []
    total_amount = sum(float(s["amount_owed"]) for s in overdue)

    for s in overdue:
        res = send_single_split_reminder(s, is_dry_run=is_dry_run, smtp_config=smtp_config, curr=curr)
        sent.append(res)

    success_count = sum(1 for r in sent if r["success"])
    mode_text = "simulated (dry-run)" if is_dry_run else "dispatched"
    summary_message = f"Processed {len(overdue)} overdue split(s). {success_count}/{len(overdue)} reminders {mode_text}."

    return {
        "overdue": overdue,
        "sent": sent,
        "total_amount": total_amount,
        "message": summary_message
    }

def print_overdue_summary(group_id=None):
    """CLI summary printer."""
    unpaid = logic.get_unpaid_splits(group_id)
    if not unpaid:
        print("No unpaid splits found.")
        return
    print(f"\nUnpaid Splits Tracker ({len(unpaid)} items):")
    cutoff = (datetime.now() - timedelta(days=OVERDUE_DAYS)).strftime("%Y-%m-%d")
    for s in unpaid:
        is_over = s["date"] <= cutoff
        status = "⚠️ OVERDUE" if is_over else "⏳ PENDING"
        email_str = f"[{s.get('debtor_email') or 'NO EMAIL'}]"
        print(f"  [{status}] {s['debtor_name']} {email_str} owes {fmt_money(s['amount_owed'])} to {s['payer_name']} for '{s['description']}' ({s['date']})")
    print()

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Smart Budgeter - Automated Email Reminder Engine")
    p.add_argument("--group", type=int, default=None, help="Group ID filter")
    p.add_argument("--overdue-days", type=int, default=OVERDUE_DAYS, help="Overdue threshold in days")
    p.add_argument("--live", action="store_true", help="Send live emails (disables dry-run mode)")
    p.add_argument("--summary", action="store_true", help="Print summary without dispatching")
    args = p.parse_args()

    db.init_db()
    if args.summary:
        print_overdue_summary(args.group)
    else:
        res = send_gentle_reminders(args.group, args.overdue_days, is_dry_run=not args.live)
        print(res["message"])
