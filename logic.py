"""
logic.py - Financial & Debt-Splitting Business Logic
- Multi-party balance computation & greedy debt simplification
- Budget health, category-level pacing & burn rate analysis
- Cash flow, savings rate & month-over-month telemetry
- Sankey diagram graph builder for debt flows
"""
from collections import defaultdict
from datetime import datetime, date
import calendar
from database import get_db_connection

def compute_balances(group_id=None):
    """
    Returns dict {user_id: net_balance} where positive = owed money (+), negative = owes money (-).
    Sum of net balances across a group always nets out to zero.
    """
    conn = get_db_connection()
    balances = defaultdict(float)

    if group_id is not None:
        # Load unpaid splits for this group
        rows = conn.execute("""
            SELECT s.user_id as debtor, s.amount_owed, s.is_paid, se.payer_id
            FROM splits s JOIN shared_expenses se ON s.shared_id = se.shared_id
            WHERE se.group_id = ?
        """, (group_id,)).fetchall()
        for r in rows:
            if r["debtor"] == r["payer_id"]:
                continue
            if r["is_paid"] == 0:
                balances[r["debtor"]] -= r["amount_owed"]
                balances[r["payer_id"]] += r["amount_owed"]

        # Settlements for this group
        rows2 = conn.execute("""
            SELECT from_user, to_user, amount FROM settlements WHERE group_id = ?
        """, (group_id,)).fetchall()
        for r in rows2:
            balances[r["from_user"]] += r["amount"]
            balances[r["to_user"]] -= r["amount"]

        # Ensure all group members are present with 0 if no balance
        members = conn.execute("SELECT user_id FROM group_members WHERE group_id = ?", (group_id,)).fetchall()
        for m in members:
            if m["user_id"] not in balances:
                balances[m["user_id"]] = 0.0
    else:
        rows = conn.execute("""
            SELECT s.user_id as debtor, s.amount_owed, s.is_paid, se.payer_id
            FROM splits s JOIN shared_expenses se ON s.shared_id = se.shared_id
        """).fetchall()
        for r in rows:
            if r["debtor"] == r["payer_id"]:
                continue
            if r["is_paid"] == 0:
                balances[r["debtor"]] -= r["amount_owed"]
                balances[r["payer_id"]] += r["amount_owed"]

        rows2 = conn.execute("SELECT from_user, to_user, amount FROM settlements").fetchall()
        for r in rows2:
            balances[r["from_user"]] += r["amount"]
            balances[r["to_user"]] -= r["amount"]

    conn.close()
    return {uid: round(bal, 2) for uid, bal in balances.items()}

def compute_balances_detailed(group_id=None):
    """Returns list of {user_id, name, balance, status} sorted descending."""
    balances = compute_balances(group_id)
    if not balances:
        return []
    conn = get_db_connection()
    result = []
    for uid, bal in balances.items():
        row = conn.execute("SELECT name, email FROM users WHERE user_id = ?", (uid,)).fetchone()
        name = row["name"] if row else f"User {uid}"
        email = row["email"] if row else ""
        status = "gets back" if bal > 0.01 else ("owes" if bal < -0.01 else "settled")
        result.append({
            "user_id": uid,
            "name": name,
            "email": email,
            "balance": round(bal, 2),
            "status": status
        })
    conn.close()
    result.sort(key=lambda x: x["balance"], reverse=True)
    return result

def simplify_debts(balances):
    """
    Greedy minimum cash-flow debt simplification algorithm.
    Reduces N pairwise debts into the minimal number of direct transactions.
    Returns list of (debtor_id, creditor_id, amount).
    """
    creditors = [[uid, bal] for uid, bal in balances.items() if bal > 0.01]
    debtors = [[uid, -bal] for uid, bal in balances.items() if bal < -0.01]

    creditors.sort(key=lambda x: x[1], reverse=True)
    debtors.sort(key=lambda x: x[1], reverse=True)

    transactions = []
    i = j = 0
    while i < len(debtors) and j < len(creditors):
        d_uid, d_amt = debtors[i]
        c_uid, c_amt = creditors[j]
        settle = round(min(d_amt, c_amt), 2)
        if settle > 0.01:
            transactions.append((d_uid, c_uid, settle))
        d_amt = round(d_amt - settle, 2)
        c_amt = round(c_amt - settle, 2)
        if d_amt < 0.01:
            i += 1
        else:
            debtors[i] = [d_uid, d_amt]
        if c_amt < 0.01:
            j += 1
        else:
            creditors[j] = [c_uid, c_amt]
    return transactions

def get_who_owes_whom(group_id=None):
    """Returns list of dicts {from_user, from_name, to_user, to_name, amount}."""
    balances = compute_balances(group_id)
    txns = simplify_debts(balances)
    if not txns:
        return []
    conn = get_db_connection()
    result = []
    for from_id, to_id, amt in txns:
        f_row = conn.execute("SELECT name, email FROM users WHERE user_id = ?", (from_id,)).fetchone()
        t_row = conn.execute("SELECT name, email FROM users WHERE user_id = ?", (to_id,)).fetchone()
        result.append({
            "from_user": from_id,
            "from_name": f_row["name"] if f_row else f"User {from_id}",
            "from_email": f_row["email"] if f_row else "",
            "to_user": to_id,
            "to_name": t_row["name"] if t_row else f"User {to_id}",
            "to_email": t_row["email"] if t_row else "",
            "amount": amt
        })
    conn.close()
    return result

def get_unpaid_splits(group_id=None):
    """All unpaid splits with debtor and payer details (excludes self-share)."""
    conn = get_db_connection()
    if group_id:
        rows = conn.execute("""
            SELECT s.*, se.description, se.date, se.payer_id, se.amount as total,
                   se.category, g.group_name,
                   u.name as debtor_name, p.name as payer_name, u.email as debtor_email, p.email as payer_email,
                   u.phone as debtor_phone, p.phone as payer_phone
            FROM splits s
            JOIN shared_expenses se ON s.shared_id = se.shared_id
            JOIN groups g ON se.group_id = g.group_id
            JOIN users u ON s.user_id = u.user_id
            JOIN users p ON se.payer_id = p.user_id
            WHERE se.group_id = ? AND s.is_paid = 0 AND s.user_id != se.payer_id
            ORDER BY se.date DESC, s.split_id DESC
        """, (group_id,)).fetchall()
    else:
        rows = conn.execute("""
            SELECT s.*, se.description, se.date, se.payer_id, se.amount as total,
                   se.category, g.group_name,
                   u.name as debtor_name, p.name as payer_name, u.email as debtor_email, p.email as payer_email,
                   u.phone as debtor_phone, p.phone as payer_phone
            FROM splits s
            JOIN shared_expenses se ON s.shared_id = se.shared_id
            JOIN groups g ON se.group_id = g.group_id
            JOIN users u ON s.user_id = u.user_id
            JOIN users p ON se.payer_id = p.user_id
            WHERE s.is_paid = 0 AND s.user_id != se.payer_id
            ORDER BY se.date DESC, s.split_id DESC
        """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_budget_status(user_id, month=None):
    """Calculates overall monthly budget utilization and burn status."""
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    if not user:
        conn.close()
        return None
    budget = user["monthly_budget"] or 0.0

    if not month:
        month = datetime.now().strftime("%Y-%m")

    row = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) as spent FROM expenses WHERE user_id = ? AND substr(date, 1, 7) = ?",
        (user_id, month)
    ).fetchone()
    spent = float(row["spent"]) if row else 0.0
    conn.close()

    remaining = round(budget - spent, 2)
    pct = round((spent / budget * 100), 1) if budget > 0 else 0.0

    # Pacing: calculate days passed in month
    now = datetime.now()
    cur_month_str = now.strftime("%Y-%m")
    if month == cur_month_str:
        days_in_month = calendar.monthrange(now.year, now.month)[1]
        days_passed = max(1, now.day)
        days_remaining = max(1, days_in_month - days_passed)
        time_elapsed_pct = round((days_passed / days_in_month) * 100, 1)
        safe_daily_spend = round(max(0.0, remaining / days_remaining), 2)
        projected_spend = round((spent / days_passed) * days_in_month, 2)
    else:
        parts = month.split("-")
        y, m = int(parts[0]), int(parts[1])
        days_in_month = calendar.monthrange(y, m)[1]
        days_passed = days_in_month
        days_remaining = 0
        time_elapsed_pct = 100.0
        safe_daily_spend = 0.0
        projected_spend = spent

    return {
        "budget": budget,
        "spent": spent,
        "remaining": remaining,
        "pct_used": pct,
        "days_in_month": days_in_month,
        "days_passed": days_passed,
        "days_remaining": days_remaining,
        "time_elapsed_pct": time_elapsed_pct,
        "safe_daily_spend": safe_daily_spend,
        "projected_spend": projected_spend,
        "is_over_budget": remaining < 0,
        "is_pacing_fast": (pct > (time_elapsed_pct + 15)) if budget > 0 else False
    }

def get_category_budget_status(user_id, month=None):
    """Compares allocated category budgets with actual spending for the specified month."""
    if not month:
        month = datetime.now().strftime("%Y-%m")

    conn = get_db_connection()
    # Budgets
    b_rows = conn.execute("SELECT category, monthly_limit FROM category_budgets WHERE user_id = ?", (user_id,)).fetchall()
    budgets = {r["category"]: float(r["monthly_limit"]) for r in b_rows}

    # Actuals
    s_rows = conn.execute(
        "SELECT category, SUM(amount) as total FROM expenses WHERE user_id = ? AND substr(date, 1, 7) = ? GROUP BY category",
        (user_id, month)
    ).fetchall()
    spends = {r["category"]: float(r["total"]) for r in s_rows}
    conn.close()

    all_cats = set(budgets.keys()) | set(spends.keys())
    results = []
    for cat in sorted(all_cats):
        limit = budgets.get(cat, 0.0)
        spent = round(spends.get(cat, 0.0), 2)
        rem = round(limit - spent, 2) if limit > 0 else None
        pct = round((spent / limit * 100), 1) if limit > 0 else None
        results.append({
            "category": cat,
            "budget": limit,
            "spent": spent,
            "remaining": rem,
            "pct_used": pct,
            "has_budget": limit > 0
        })
    results.sort(key=lambda x: x["spent"], reverse=True)
    return results

def get_cash_flow_summary(user_id, month=None):
    """Calculates Net Cash Flow = Total Income - Total Expense, and Savings Rate."""
    if not month:
        month = datetime.now().strftime("%Y-%m")

    conn = get_db_connection()
    # Income
    inc_row = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) as total FROM incomes WHERE user_id = ? AND substr(date, 1, 7) = ?",
        (user_id, month)
    ).fetchone()
    total_income = float(inc_row["total"]) if inc_row else 0.0

    # Expense
    exp_row = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) as total FROM expenses WHERE user_id = ? AND substr(date, 1, 7) = ?",
        (user_id, month)
    ).fetchone()
    total_expense = float(exp_row["total"]) if exp_row else 0.0
    conn.close()

    net_cashflow = round(total_income - total_expense, 2)
    savings_rate = round((net_cashflow / total_income * 100), 1) if total_income > 0 else 0.0

    return {
        "month": month,
        "total_income": total_income,
        "total_expense": total_expense,
        "net_cashflow": net_cashflow,
        "savings_rate": savings_rate
    }

def get_month_over_month_metrics(user_id):
    """Compares current month vs previous month spending and income."""
    now = datetime.now()
    cur_m = now.strftime("%Y-%m")
    # Previous month
    if now.month == 1:
        prev_m = f"{now.year - 1}-12"
    else:
        prev_m = f"{now.year}-{now.month - 1:02d}"

    conn = get_db_connection()
    cur_exp = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE user_id = ? AND substr(date, 1, 7) = ?", (user_id, cur_m)).fetchone()[0]
    prev_exp = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE user_id = ? AND substr(date, 1, 7) = ?", (user_id, prev_m)).fetchone()[0]

    cur_inc = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM incomes WHERE user_id = ? AND substr(date, 1, 7) = ?", (user_id, cur_m)).fetchone()[0]
    prev_inc = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM incomes WHERE user_id = ? AND substr(date, 1, 7) = ?", (user_id, prev_m)).fetchone()[0]
    conn.close()

    cur_exp, prev_exp = float(cur_exp), float(prev_exp)
    cur_inc, prev_inc = float(cur_inc), float(prev_inc)

    exp_change_pct = round(((cur_exp - prev_exp) / prev_exp * 100), 1) if prev_exp > 0 else 0.0
    inc_change_pct = round(((cur_inc - prev_inc) / prev_inc * 100), 1) if prev_inc > 0 else 0.0

    return {
        "current_month": cur_m,
        "prev_month": prev_m,
        "current_expense": cur_exp,
        "prev_expense": prev_exp,
        "expense_diff": round(cur_exp - prev_exp, 2),
        "expense_change_pct": exp_change_pct,
        "current_income": cur_inc,
        "prev_income": prev_inc,
        "income_diff": round(cur_inc - prev_inc, 2),
        "income_change_pct": inc_change_pct
    }

def get_sankey_debt_data(group_id=None, curr="₹", *args, **kwargs):
    """Formats node and link dictionaries for Plotly Sankey diagram of simplified debts."""
    if "curr" in kwargs:
        curr = kwargs["curr"]
    elif len(args) > 0:
        curr = args[0]
    txns = get_who_owes_whom(group_id)
    if not txns:
        return None

    nodes = []
    node_idx = {}
    for t in txns:
        for name in [t["from_name"], t["to_name"]]:
            if name not in node_idx:
                node_idx[name] = len(nodes)
                nodes.append(name)

    sources = [node_idx[t["from_name"]] for t in txns]
    targets = [node_idx[t["to_name"]] for t in txns]
    values = [t["amount"] for t in txns]
    labels = [f"{t['from_name']} owes {t['to_name']} {curr}{t['amount']:.2f}" for t in txns]

    return {
        "nodes": nodes,
        "sources": sources,
        "targets": targets,
        "values": values,
        "labels": labels
    }

def validate_user_data(name, email, phone, exclude_user_id=None):
    """
    Validates name, email format & uniqueness, and 10-digit mobile number format & uniqueness.
    Returns (is_valid: bool, error_msg: str or None, clean_email: str or None, clean_phone: str or None).
    """
    import re
    import database as db

    name_str = str(name).strip() if name else ""
    if not name_str:
        return False, "Full Name is required.", None, None

    # Validate Email
    email_str = str(email).strip() if email else ""
    if not email_str:
        return False, "Email address is required.", None, None

    email_regex = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    if not re.match(email_regex, email_str):
        return False, f"'{email_str}' is not a valid email address format (e.g. name@example.com).", None, None

    clean_email = email_str.lower()

    # Check Email Uniqueness in Database
    existing_user_email = db.get_user_by_email(clean_email)
    if existing_user_email and (exclude_user_id is None or existing_user_email["user_id"] != exclude_user_id):
        return False, f"Email '{clean_email}' is already registered to user '{existing_user_email['name']}'. Please use a unique email address.", None, None

    # Validate 10-Digit Mobile Number
    phone_str = str(phone).strip() if phone else ""
    if not phone_str:
        return False, "10-digit mobile number is required.", None, None

    clean_phone = "".join(filter(str.isdigit, phone_str))
    if len(clean_phone) != 10 or not phone_str.isdigit():
        return False, f"Mobile number must be exactly 10 digits (0-9) without spaces or country code (entered: '{phone_str}').", None, None

    # Check Phone Uniqueness in Database
    existing_user_phone = db.get_user_by_phone(clean_phone)
    if existing_user_phone and (exclude_user_id is None or existing_user_phone["user_id"] != exclude_user_id):
        return False, f"Mobile number '{clean_phone}' is already registered to user '{existing_user_phone['name']}'. Please use a unique mobile number.", None, None

    return True, None, clean_email, clean_phone

