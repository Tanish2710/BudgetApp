"""
database.py - Smart Budgeter "Debt-Splitter" Persistence Layer
SQLite with normalized schema, foreign keys, full CRUD, and migrations.
"""
import sqlite3
import os
import json
from datetime import datetime, date, timedelta
import random

DB_PATH = os.environ.get(
    "BUDGET_DB_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "finance.db"),
)

EXPENSE_CATEGORIES = [
    "Food & Dining", "Groceries", "Housing & Rent", "Utilities", "Transportation",
    "Entertainment", "Health & Medical", "Shopping", "Travel", "Education", "Other",
]
SHARED_CATEGORIES = ["General"] + EXPENSE_CATEGORIES
INCOME_SOURCES = ["Salary", "Freelance & Consulting", "Investments & Dividends", "Reimbursements", "Gifts", "Other"]
PAYMENT_METHODS = ["UPI", "Debit Card", "Credit Card", "Bank Transfer", "Cash", "Other"]
SETTLEMENT_METHODS = ["UPI", "Bank Transfer", "Cash", "Card", "Other"]

ALL_TABLES = [
    "reminder_log", "splits", "shared_expenses", "settlements", "group_members", "groups",
    "category_budgets", "incomes", "expenses", "users",
]

def get_db_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    user_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT NOT NULL,
    email          TEXT UNIQUE,
    phone          TEXT UNIQUE,
    monthly_budget REAL DEFAULT 0,
    created_at     TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS expenses (
    exp_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id        INTEGER NOT NULL,
    amount         REAL NOT NULL CHECK(amount > 0),
    category       TEXT NOT NULL,
    description    TEXT,
    date           TEXT NOT NULL,
    payment_method TEXT DEFAULT 'Card',
    notes          TEXT,
    FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS incomes (
    income_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    amount      REAL NOT NULL CHECK(amount > 0),
    source      TEXT NOT NULL,
    description TEXT,
    date        TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS category_budgets (
    budget_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL,
    category      TEXT NOT NULL,
    monthly_limit REAL NOT NULL CHECK(monthly_limit >= 0),
    FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    UNIQUE(user_id, category)
);

CREATE TABLE IF NOT EXISTS groups (
    group_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    group_name TEXT NOT NULL UNIQUE,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS group_members (
    group_id INTEGER NOT NULL,
    user_id  INTEGER NOT NULL,
    joined_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (group_id, user_id),
    FOREIGN KEY(group_id) REFERENCES groups(group_id) ON DELETE CASCADE,
    FOREIGN KEY(user_id)  REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS shared_expenses (
    shared_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id    INTEGER NOT NULL,
    payer_id    INTEGER NOT NULL,
    amount      REAL NOT NULL CHECK(amount > 0),
    description TEXT NOT NULL,
    category    TEXT DEFAULT 'General',
    date        TEXT NOT NULL,
    FOREIGN KEY(group_id) REFERENCES groups(group_id) ON DELETE CASCADE,
    FOREIGN KEY(payer_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS splits (
    split_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    shared_id   INTEGER NOT NULL,
    user_id     INTEGER NOT NULL,
    amount_owed REAL NOT NULL CHECK(amount_owed >= 0),
    is_paid     INTEGER DEFAULT 0 CHECK(is_paid IN (0,1)),
    FOREIGN KEY(shared_id) REFERENCES shared_expenses(shared_id) ON DELETE CASCADE,
    FOREIGN KEY(user_id)   REFERENCES users(user_id) ON DELETE CASCADE,
    UNIQUE(shared_id, user_id)
);

CREATE TABLE IF NOT EXISTS settlements (
    settlement_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    from_user      INTEGER NOT NULL,
    to_user        INTEGER NOT NULL,
    amount         REAL NOT NULL CHECK(amount > 0),
    group_id       INTEGER,
    date           TEXT DEFAULT (datetime('now', 'localtime')),
    note           TEXT,
    payment_method TEXT DEFAULT 'Cash',
    FOREIGN KEY(from_user) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY(to_user)   REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY(group_id)  REFERENCES groups(group_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS app_settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS reminder_log (
    log_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER,
    group_id   INTEGER,
    amount     REAL DEFAULT 0,
    recipient  TEXT,
    subject    TEXT,
    status     TEXT NOT NULL,
    trigger    TEXT DEFAULT 'manual',
    message    TEXT,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_reminder_log_user ON reminder_log(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_expenses_user_date ON expenses(user_id, date);
CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(category);
CREATE INDEX IF NOT EXISTS idx_incomes_user_date ON incomes(user_id, date);
CREATE INDEX IF NOT EXISTS idx_shared_group ON shared_expenses(group_id);
CREATE INDEX IF NOT EXISTS idx_shared_payer ON shared_expenses(payer_id);
CREATE INDEX IF NOT EXISTS idx_splits_user ON splits(user_id);
CREATE INDEX IF NOT EXISTS idx_splits_shared ON splits(shared_id);
CREATE INDEX IF NOT EXISTS idx_splits_paid ON splits(is_paid);
CREATE INDEX IF NOT EXISTS idx_settlements_group ON settlements(group_id);
CREATE INDEX IF NOT EXISTS idx_group_members_user ON group_members(user_id);
CREATE INDEX IF NOT EXISTS idx_group_members_group ON group_members(group_id);
"""

def run_migrations(conn):
    migrations = [
        "ALTER TABLE users ADD COLUMN phone TEXT",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email)",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_phone ON users(phone)",
        "ALTER TABLE expenses ADD COLUMN payment_method TEXT DEFAULT 'Card'",
        "ALTER TABLE expenses ADD COLUMN notes TEXT",
        "ALTER TABLE shared_expenses ADD COLUMN category TEXT DEFAULT 'General'",
        "ALTER TABLE settlements ADD COLUMN payment_method TEXT DEFAULT 'Cash'",
        # Data fix: a payer's own share of a bill is settled by definition.
        "UPDATE splits SET is_paid = 1 WHERE is_paid = 0 AND user_id = (SELECT payer_id FROM shared_expenses se WHERE se.shared_id = splits.shared_id)",
    ]
    for sql in migrations:
        try:
            conn.execute(sql)
        except sqlite3.OperationalError:
            pass
    conn.commit()

def init_db():
    conn = get_db_connection()
    conn.executescript(SCHEMA_SQL)
    run_migrations(conn)
    conn.close()
    return True

# --- Users CRUD ---
def create_user(name, email=None, phone=None, monthly_budget=0.0):
    # Support backward compatibility if monthly_budget is passed as 3rd positional argument
    if isinstance(phone, (int, float)) and monthly_budget == 0.0:
        monthly_budget = float(phone)
        phone = None

    name = str(name).strip() if name else ""
    clean_email = str(email).strip().lower() if email and str(email).strip() else None
    clean_phone = "".join(filter(str.isdigit, str(phone).strip())) if phone and str(phone).strip() else None

    conn = get_db_connection()
    cur = conn.cursor()

    # Pre-check email uniqueness
    if clean_email:
        existing_e = cur.execute("SELECT user_id, name FROM users WHERE LOWER(TRIM(email)) = LOWER(?)", (clean_email,)).fetchone()
        if existing_e:
            conn.close()
            raise ValueError(f"Email '{clean_email}' is already registered to user '{existing_e['name']}'.")

    # Pre-check phone uniqueness
    if clean_phone:
        existing_p = cur.execute("SELECT user_id, name FROM users WHERE phone = ?", (clean_phone,)).fetchone()
        if existing_p:
            conn.close()
            raise ValueError(f"Mobile number '{clean_phone}' is already registered to user '{existing_p['name']}'.")

    try:
        cur.execute(
            "INSERT INTO users (name, email, phone, monthly_budget) VALUES (?, ?, ?, ?)",
            (name, clean_email, clean_phone, float(monthly_budget))
        )
        conn.commit()
        uid = cur.lastrowid
    except sqlite3.IntegrityError as e:
        conn.close()
        err_msg = str(e).lower()
        if "email" in err_msg:
            raise ValueError(f"Email '{clean_email}' is already registered.")
        elif "phone" in err_msg:
            raise ValueError(f"Mobile number '{clean_phone}' is already registered.")
        raise ValueError(f"Database constraint violation: {e}")

    conn.close()
    return uid

def get_user(user_id):
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_all_users():
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM users ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_user_by_email(email):
    if not email:
        return None
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM users WHERE LOWER(TRIM(email)) = LOWER(TRIM(?))", (str(email).strip(),)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_user_by_phone(phone):
    if not phone:
        return None
    clean_phone = "".join(filter(str.isdigit, str(phone).strip()))
    if not clean_phone:
        return None
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM users WHERE phone = ?", (clean_phone,)).fetchone()
    conn.close()
    return dict(row) if row else None

def update_user(user_id, name=None, email=None, phone=None, monthly_budget=None):
    conn = get_db_connection()
    cur = conn.cursor()

    clean_email = str(email).strip().lower() if email and str(email).strip() else (None if email == "" else None)
    clean_phone = "".join(filter(str.isdigit, str(phone).strip())) if phone and str(phone).strip() else (None if phone == "" else None)

    if email is not None and clean_email:
        existing_e = cur.execute("SELECT user_id, name FROM users WHERE LOWER(TRIM(email)) = LOWER(?) AND user_id != ?", (clean_email, user_id)).fetchone()
        if existing_e:
            conn.close()
            raise ValueError(f"Email '{clean_email}' is already registered to user '{existing_e['name']}'.")

    if phone is not None and clean_phone:
        existing_p = cur.execute("SELECT user_id, name FROM users WHERE phone = ? AND user_id != ?", (clean_phone, user_id)).fetchone()
        if existing_p:
            conn.close()
            raise ValueError(f"Mobile number '{clean_phone}' is already registered to user '{existing_p['name']}'.")

    fields, vals = [], []
    if name is not None:
        fields.append("name = ?"); vals.append(str(name).strip())
    if email is not None:
        fields.append("email = ?"); vals.append(clean_email)
    if phone is not None:
        fields.append("phone = ?"); vals.append(clean_phone)
    if monthly_budget is not None:
        fields.append("monthly_budget = ?"); vals.append(float(monthly_budget))

    if not fields:
        conn.close()
        return False

    vals.append(user_id)
    try:
        cur.execute(f"UPDATE users SET {', '.join(fields)} WHERE user_id = ?", vals)
        conn.commit()
    except sqlite3.IntegrityError as e:
        conn.close()
        err_msg = str(e).lower()
        if "email" in err_msg:
            raise ValueError(f"Email '{clean_email}' is already registered.")
        elif "phone" in err_msg:
            raise ValueError(f"Mobile number '{clean_phone}' is already registered.")
        raise ValueError(f"Database constraint violation: {e}")

    conn.close()
    return True

def delete_user(user_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    conn.commit(); conn.close()

# --- Expenses CRUD ---
def add_expense(user_id, amount, category, date=None, description="", payment_method="Card", notes=""):
    if date is None: date = datetime.now().strftime("%Y-%m-%d")
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO expenses (user_id, amount, category, description, date, payment_method, notes) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user_id, amount, category, description, date, payment_method, notes)
    )
    conn.commit()
    eid = cur.lastrowid
    conn.close()
    return eid

def get_user_expenses(user_id, limit=None):
    conn = get_db_connection()
    q = "SELECT * FROM expenses WHERE user_id = ? ORDER BY date DESC, exp_id DESC"
    if limit: q += f" LIMIT {int(limit)}"
    rows = conn.execute(q, (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_all_expenses(limit=None):
    conn = get_db_connection()
    q = "SELECT e.*, u.name as user_name FROM expenses e JOIN users u ON e.user_id = u.user_id ORDER BY e.date DESC, e.exp_id DESC"
    if limit: q += f" LIMIT {int(limit)}"
    rows = conn.execute(q).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_expenses_filtered(user_id=None, category=None, start_date=None, end_date=None, search=None, limit=None):
    conn = get_db_connection()
    query = "SELECT e.*, u.name as user_name FROM expenses e JOIN users u ON e.user_id = u.user_id WHERE 1=1"
    params = []
    if user_id:
        query += " AND e.user_id = ?"
        params.append(user_id)
    if category and category != "All":
        query += " AND e.category = ?"
        params.append(category)
    if start_date:
        query += " AND e.date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND e.date <= ?"
        params.append(end_date)
    if search:
        query += " AND (e.description LIKE ? OR e.category LIKE ? OR e.notes LIKE ?)"
        term = f"%{search}%"
        params.extend([term, term, term])
    query += " ORDER BY e.date DESC, e.exp_id DESC"
    if limit:
        query += f" LIMIT {int(limit)}"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_expense(exp_id, amount=None, category=None, description=None, date=None, payment_method=None, notes=None):
    conn = get_db_connection()
    fields, vals = [], []
    if amount is not None: fields.append("amount = ?"); vals.append(amount)
    if category is not None: fields.append("category = ?"); vals.append(category)
    if description is not None: fields.append("description = ?"); vals.append(description)
    if date is not None: fields.append("date = ?"); vals.append(date)
    if payment_method is not None: fields.append("payment_method = ?"); vals.append(payment_method)
    if notes is not None: fields.append("notes = ?"); vals.append(notes)
    if not fields: conn.close(); return False
    vals.append(exp_id)
    conn.execute(f"UPDATE expenses SET {', '.join(fields)} WHERE exp_id = ?", vals)
    conn.commit(); conn.close(); return True

def delete_expense(exp_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM expenses WHERE exp_id = ?", (exp_id,))
    conn.commit(); conn.close()

def get_spending_by_category(user_id, month=None):
    conn = get_db_connection()
    if month:
        rows = conn.execute(
            "SELECT category, SUM(amount) as total FROM expenses WHERE user_id = ? AND substr(date,1,7) = ? GROUP BY category ORDER BY total DESC",
            (user_id, month)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT category, SUM(amount) as total FROM expenses WHERE user_id = ? GROUP BY category ORDER BY total DESC",
            (user_id,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_monthly_spending(user_id=None):
    conn = get_db_connection()
    if user_id:
        rows = conn.execute("SELECT substr(date,1,7) as month, SUM(amount) as total FROM expenses WHERE user_id = ? GROUP BY month ORDER BY month", (user_id,)).fetchall()
    else:
        rows = conn.execute("SELECT substr(date,1,7) as month, SUM(amount) as total FROM expenses GROUP BY month ORDER BY month").fetchall()
    conn.close()
    return [dict(r) for r in rows]

# --- Incomes CRUD ---
def add_income(user_id, amount, source, date=None, description=""):
    if date is None: date = datetime.now().strftime("%Y-%m-%d")
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO incomes (user_id, amount, source, description, date) VALUES (?, ?, ?, ?, ?)",
        (user_id, amount, source, description, date)
    )
    conn.commit()
    iid = cur.lastrowid
    conn.close()
    return iid

def get_user_incomes(user_id=None, limit=None):
    conn = get_db_connection()
    if user_id:
        q = "SELECT i.*, u.name as user_name FROM incomes i JOIN users u ON i.user_id = u.user_id WHERE i.user_id = ? ORDER BY i.date DESC, i.income_id DESC"
        params = (user_id,)
    else:
        q = "SELECT i.*, u.name as user_name FROM incomes i JOIN users u ON i.user_id = u.user_id ORDER BY i.date DESC, i.income_id DESC"
        params = ()
    if limit: q += f" LIMIT {int(limit)}"
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_income(income_id, amount=None, source=None, description=None, date=None):
    conn = get_db_connection()
    fields, vals = [], []
    if amount is not None: fields.append("amount = ?"); vals.append(amount)
    if source is not None: fields.append("source = ?"); vals.append(source)
    if description is not None: fields.append("description = ?"); vals.append(description)
    if date is not None: fields.append("date = ?"); vals.append(date)
    if not fields: conn.close(); return False
    vals.append(income_id)
    conn.execute(f"UPDATE incomes SET {', '.join(fields)} WHERE income_id = ?", vals)
    conn.commit(); conn.close(); return True

def delete_income(income_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM incomes WHERE income_id = ?", (income_id,))
    conn.commit(); conn.close()

def get_monthly_income(user_id=None):
    conn = get_db_connection()
    if user_id:
        rows = conn.execute("SELECT substr(date,1,7) as month, SUM(amount) as total FROM incomes WHERE user_id = ? GROUP BY month ORDER BY month", (user_id,)).fetchall()
    else:
        rows = conn.execute("SELECT substr(date,1,7) as month, SUM(amount) as total FROM incomes GROUP BY month ORDER BY month").fetchall()
    conn.close()
    return [dict(r) for r in rows]

# --- Category Budgets CRUD ---
def set_category_budget(user_id, category, monthly_limit):
    conn = get_db_connection()
    conn.execute("""
        INSERT INTO category_budgets (user_id, category, monthly_limit)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id, category) DO UPDATE SET monthly_limit = excluded.monthly_limit
    """, (user_id, category, float(monthly_limit)))
    conn.commit()
    conn.close()
    return True

def get_category_budgets(user_id):
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM category_budgets WHERE user_id = ? ORDER BY category", (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def delete_category_budget(user_id, category):
    conn = get_db_connection()
    conn.execute("DELETE FROM category_budgets WHERE user_id = ? AND category = ?", (user_id, category))
    conn.commit()
    conn.close()

def get_distinct_categories(user_id=None):
    """Return sorted distinct categories without loading all expense rows (perf)."""
    conn = get_db_connection()
    if user_id:
        rows = conn.execute("SELECT DISTINCT category FROM expenses WHERE user_id = ? AND category IS NOT NULL AND TRIM(category) != '' ORDER BY category", (user_id,)).fetchall()
    else:
        rows = conn.execute("SELECT DISTINCT category FROM expenses WHERE category IS NOT NULL AND TRIM(category) != '' ORDER BY category").fetchall()
    conn.close()
    return [r["category"] for r in rows if r["category"]]

# --- Groups CRUD ---
def create_group(group_name):
    group_name = str(group_name or "").strip()
    if not group_name:
        raise ValueError("Circle name is required.")
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO groups (group_name) VALUES (?)", (group_name,))
        conn.commit()
        gid = cur.lastrowid
    except sqlite3.IntegrityError:
        raise ValueError(f"A circle named '{group_name}' already exists.")
    finally:
        conn.close()
    return gid

def rename_group(group_id, group_name):
    group_name = str(group_name or "").strip()
    if not group_name:
        raise ValueError("Circle name is required.")
    conn = get_db_connection()
    try:
        conn.execute("UPDATE groups SET group_name = ? WHERE group_id = ?", (group_name, group_id))
        conn.commit()
    except sqlite3.IntegrityError:
        raise ValueError(f"A circle named '{group_name}' already exists.")
    finally:
        conn.close()

def get_all_groups():
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM groups ORDER BY group_name").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_group(group_id):
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM groups WHERE group_id = ?", (group_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def delete_group(group_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM groups WHERE group_id = ?", (group_id,))
    conn.commit(); conn.close()

def add_member_to_group(group_id, user_id):
    conn = get_db_connection()
    try:
        conn.execute("INSERT INTO group_members (group_id, user_id) VALUES (?, ?)", (group_id, user_id))
        conn.commit()
        ok = True
    except sqlite3.IntegrityError:
        ok = False
    conn.close()
    return ok

def remove_member_from_group(group_id, user_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM group_members WHERE group_id = ? AND user_id = ?", (group_id, user_id))
    conn.commit(); conn.close()

def get_group_members(group_id):
    conn = get_db_connection()
    rows = conn.execute("SELECT u.* FROM users u JOIN group_members gm ON gm.user_id = u.user_id WHERE gm.group_id = ? ORDER BY u.name", (group_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_user_groups(user_id):
    conn = get_db_connection()
    rows = conn.execute("SELECT g.* FROM groups g JOIN group_members gm ON gm.group_id = g.group_id WHERE gm.user_id = ?", (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# --- Shared Expenses & Splits ---
def allocate_amounts(total, weights):
    """
    Split `total` proportionally to `weights` (list of non-negative numbers), working in
    whole cents so the parts always add back up to the exact total (largest-remainder method).
    """
    total_cents = int(round(float(total) * 100))
    weights = [max(0.0, float(w)) for w in weights]
    w_sum = sum(weights)
    if not weights or w_sum <= 0:
        raise ValueError("Allocation weights must contain at least one positive value")
    raw = [total_cents * w / w_sum for w in weights]
    cents = [int(r) for r in raw]
    leftover = total_cents - sum(cents)
    order = sorted(range(len(raw)), key=lambda i: (raw[i] - cents[i]), reverse=True)
    for i in order[:leftover]:
        cents[i] += 1
    return [c / 100 for c in cents]

def add_shared_expense(group_id, payer_id, amount, description, date=None, split_among=None, custom_splits=None, category="General"):
    if date is None: date = datetime.now().strftime("%Y-%m-%d")
    amount = round(float(amount), 2)

    if custom_splits:
        split_items = [(uid, round(float(owed), 2)) for uid, owed in custom_splits.items()]
        if abs(sum(o for _, o in split_items) - amount) > 0.01:
            raise ValueError("Split amounts must add up to the bill total")
    else:
        conn = get_db_connection()
        if split_among is None:
            members = conn.execute("SELECT user_id FROM group_members WHERE group_id = ?", (group_id,)).fetchall()
            split_among = [r["user_id"] for r in members]
        conn.close()
        if not split_among:
            raise ValueError("No members to split among")
        split_items = list(zip(split_among, allocate_amounts(amount, [1] * len(split_among))))

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO shared_expenses (group_id, payer_id, amount, description, date, category) VALUES (?, ?, ?, ?, ?, ?)",
            (group_id, payer_id, amount, description, date, category)
        )
        shared_id = cur.lastrowid
        for uid, owed in split_items:
            # The payer's own share is settled by definition.
            is_paid = 1 if uid == payer_id else 0
            cur.execute(
                "INSERT INTO splits (shared_id, user_id, amount_owed, is_paid) VALUES (?, ?, ?, ?)",
                (shared_id, uid, owed, is_paid)
            )
        conn.commit()
    finally:
        conn.close()
    return shared_id

def delete_shared_expense(shared_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM shared_expenses WHERE shared_id = ?", (shared_id,))
    conn.commit()
    conn.close()

def get_group_shared_expenses(group_id):
    conn = get_db_connection()
    rows = conn.execute("SELECT se.*, u.name as payer_name FROM shared_expenses se JOIN users u ON se.payer_id = u.user_id WHERE se.group_id = ? ORDER BY se.date DESC, se.shared_id DESC", (group_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_splits_for_expense(shared_id):
    conn = get_db_connection()
    rows = conn.execute("SELECT s.*, u.name as user_name FROM splits s JOIN users u ON s.user_id = u.user_id WHERE s.shared_id = ? ORDER BY u.name", (shared_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_all_splits_for_group(group_id):
    conn = get_db_connection()
    rows = conn.execute("""
        SELECT s.*, se.payer_id, se.amount as total_amount, se.description,
               u.name as debtor_name, p.name as payer_name, se.date
        FROM splits s
        JOIN shared_expenses se ON s.shared_id = se.shared_id
        JOIN users u ON s.user_id = u.user_id
        JOIN users p ON se.payer_id = p.user_id
        WHERE se.group_id = ? ORDER BY se.date DESC, s.split_id DESC
    """, (group_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def mark_split_paid(split_id, paid=True):
    conn = get_db_connection()
    conn.execute("UPDATE splits SET is_paid = ? WHERE split_id = ?", (1 if paid else 0, split_id))
    conn.commit()
    conn.close()

def mark_user_paid_for_expense(shared_id, user_id, paid=True):
    conn = get_db_connection()
    conn.execute("UPDATE splits SET is_paid = ? WHERE shared_id = ? AND user_id = ?", (1 if paid else 0, shared_id, user_id))
    conn.commit()
    conn.close()

# --- Settlements CRUD ---
def add_settlement(from_user, to_user, amount, group_id=None, note="", payment_method="Cash", date=None):
    if from_user == to_user:
        raise ValueError("Payer and receiver must be different people")
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO settlements (from_user, to_user, amount, group_id, note, payment_method, date) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (from_user, to_user, round(float(amount), 2), group_id, note, payment_method, date)
    )
    conn.commit()
    sid = cur.lastrowid
    conn.close()
    return sid

def delete_settlement(settlement_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM settlements WHERE settlement_id = ?", (settlement_id,))
    conn.commit()
    conn.close()

def get_settlements(group_id=None):
    conn = get_db_connection()
    if group_id:
        rows = conn.execute("""
            SELECT st.*, f.name as from_name, t.name as to_name, g.group_name
            FROM settlements st
            JOIN users f ON st.from_user = f.user_id
            JOIN users t ON st.to_user = t.user_id
            LEFT JOIN groups g ON st.group_id = g.group_id
            WHERE st.group_id = ? ORDER BY st.date DESC, st.settlement_id DESC
        """, (group_id,)).fetchall()
    else:
        rows = conn.execute("""
            SELECT st.*, f.name as from_name, t.name as to_name, g.group_name
            FROM settlements st
            JOIN users f ON st.from_user = f.user_id
            JOIN users t ON st.to_user = t.user_id
            LEFT JOIN groups g ON st.group_id = g.group_id
            ORDER BY st.date DESC, st.settlement_id DESC
        """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# --- App Settings (key/value, JSON encoded) ---
def get_setting(key, default=None):
    conn = get_db_connection()
    row = conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    if row is None or row["value"] is None:
        return default
    try:
        return json.loads(row["value"])
    except (TypeError, ValueError):
        return default

def get_settings(defaults):
    """Return a dict of settings, filling any missing key from `defaults`."""
    conn = get_db_connection()
    rows = conn.execute("SELECT key, value FROM app_settings").fetchall()
    conn.close()
    stored = {}
    for r in rows:
        try:
            stored[r["key"]] = json.loads(r["value"])
        except (TypeError, ValueError):
            pass
    return {k: stored.get(k, v) for k, v in defaults.items()}

def set_setting(key, value):
    set_settings({key: value})

def set_settings(values):
    conn = get_db_connection()
    conn.executemany(
        "INSERT INTO app_settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        [(k, json.dumps(v)) for k, v in values.items()],
    )
    conn.commit()
    conn.close()

def compare_and_set_setting(key, expected, new_value):
    """
    Atomically set `key` to `new_value` only if it currently equals `expected`.
    Used so the in-app scheduler and a cron job never both claim the same daily run.
    """
    conn = get_db_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
        current = json.loads(row["value"]) if row and row["value"] is not None else None
        if current != expected:
            conn.rollback()
            return False
        conn.execute(
            "INSERT INTO app_settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, json.dumps(new_value)),
        )
        conn.commit()
        return True
    finally:
        conn.close()

# --- Reminder Log ---
def log_reminder(user_id, group_id, amount, recipient, subject, status, trigger="manual", message=""):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO reminder_log (user_id, group_id, amount, recipient, subject, status, trigger, message, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (user_id, group_id, amount, recipient, subject, status, trigger, message,
         datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    )
    conn.commit()
    lid = cur.lastrowid
    conn.close()
    return lid

def get_reminder_log(limit=100, user_id=None):
    conn = get_db_connection()
    q = ("SELECT rl.*, u.name AS user_name FROM reminder_log rl "
         "LEFT JOIN users u ON rl.user_id = u.user_id")
    params = []
    if user_id:
        q += " WHERE rl.user_id = ?"
        params.append(user_id)
    q += " ORDER BY rl.created_at DESC, rl.log_id DESC LIMIT ?"
    params.append(int(limit))
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_last_reminder_times(statuses=("sent",)):
    """Return {user_id: last created_at} for reminders with the given statuses."""
    conn = get_db_connection()
    placeholders = ",".join("?" * len(statuses))
    rows = conn.execute(
        f"SELECT user_id, MAX(created_at) AS last_at FROM reminder_log WHERE status IN ({placeholders}) GROUP BY user_id",
        list(statuses),
    ).fetchall()
    conn.close()
    return {r["user_id"]: r["last_at"] for r in rows}

# --- Reporting queries ---
def get_daily_spending(user_id, month):
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT date, SUM(amount) AS total FROM expenses WHERE user_id = ? AND substr(date,1,7) = ? GROUP BY date ORDER BY date",
        (user_id, month),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_monthly_category_spending(user_id):
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT substr(date,1,7) AS month, category, SUM(amount) AS total FROM expenses "
        "WHERE user_id = ? GROUP BY month, category ORDER BY month",
        (user_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_incomes_filtered(user_id=None, start_date=None, end_date=None, search=None, limit=None):
    conn = get_db_connection()
    query = "SELECT i.*, u.name as user_name FROM incomes i JOIN users u ON i.user_id = u.user_id WHERE 1=1"
    params = []
    if user_id:
        query += " AND i.user_id = ?"; params.append(user_id)
    if start_date:
        query += " AND i.date >= ?"; params.append(start_date)
    if end_date:
        query += " AND i.date <= ?"; params.append(end_date)
    if search:
        query += " AND (i.description LIKE ? OR i.source LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
    query += " ORDER BY i.date DESC, i.income_id DESC"
    if limit:
        query += f" LIMIT {int(limit)}"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def reset_database():
    """Drop every table and recreate an empty schema. App settings are kept."""
    conn = get_db_connection()
    conn.execute("PRAGMA foreign_keys = OFF;")
    for t in ALL_TABLES:
        conn.execute(f"DROP TABLE IF EXISTS {t}")
    conn.commit()
    conn.close()
    init_db()

# --- Demo Data Generator ---
def _month_start(d, months_back):
    """First day of the month `months_back` months before d (negative = months ahead)."""
    idx = d.year * 12 + (d.month - 1) - months_back
    return date(idx // 12, idx % 12 + 1, 1)

month_start = _month_start


def seed_comprehensive_demo_data(reset=False):
    """Populate a realistic six-month dataset for demos and testing. Amounts are in INR."""
    if reset:
        reset_database()
    else:
        init_db()

    conn = get_db_connection()
    user_count = conn.execute("SELECT count(*) FROM users").fetchone()[0]
    conn.close()
    if user_count > 0 and not reset:
        return False  # Already seeded

    rng = random.Random(42)
    today = date.today()

    u_alice = create_user("Alice Johnson", "alice@example.com", "9876543210", 60000.0)
    u_bob = create_user("Bob Martinez", "bob@example.com", "9876543211", 45000.0)
    u_charlie = create_user("Charlie Chen", "charlie@example.com", "9876543212", 40000.0)
    u_diana = create_user("Diana Prince", "diana@example.com", "9876543213", 50000.0)

    for cat, limit in [
        ("Housing & Rent", 22000), ("Groceries", 8000), ("Food & Dining", 6000),
        ("Utilities", 4000), ("Transportation", 3500), ("Entertainment", 3000), ("Shopping", 5000),
    ]:
        set_category_budget(u_alice, cat, float(limit))

    # Recurring monthly pattern for Alice, plus a lighter pattern for others
    profiles = {
        u_alice: {"salary": 95000, "rent": 21000},
        u_bob: {"salary": 72000, "rent": 18000},
        u_charlie: {"salary": 64000, "rent": 16000},
        u_diana: {"salary": 88000, "rent": 20000},
    }
    variable = [
        ("Groceries", "BigBasket order", (900, 2600), 3, "UPI"),
        ("Food & Dining", "Dinner out", (450, 1800), 4, "Credit Card"),
        ("Food & Dining", "Swiggy order", (250, 700), 4, "UPI"),
        ("Transportation", "Uber ride", (180, 650), 5, "UPI"),
        ("Transportation", "Metro card recharge", (500, 500), 1, "Debit Card"),
        ("Entertainment", "Movie tickets", (400, 1100), 1, "Credit Card"),
        ("Shopping", "Amazon order", (600, 3800), 2, "Credit Card"),
        ("Health & Medical", "Pharmacy", (200, 900), 1, "UPI"),
    ]

    for uid, prof in profiles.items():
        intensity = 1.0 if uid == u_alice else 0.45
        for back in range(5, -1, -1):
            start = _month_start(today, back)
            month_len = ((_month_start(today, back - 1) if back > 0 else _month_start(today, -1)) - timedelta(days=1)).day
            last_day = today.day if back == 0 else month_len
            elapsed = last_day / month_len  # the current month only has part of its spending so far

            def day(n):
                return start.replace(day=min(n, last_day)).isoformat()

            add_income(uid, float(prof["salary"]), "Salary", day(1), "Monthly salary")
            if uid == u_alice and back % 2 == 0:
                add_income(uid, float(rng.choice([8000, 12000, 15000])), "Freelance & Consulting", day(18), "Design consulting project")
            add_expense(uid, float(prof["rent"]), "Housing & Rent", day(2), "Apartment rent", "Bank Transfer")
            add_expense(uid, float(rng.randint(1400, 2600)), "Utilities", day(10), "Electricity bill", "UPI")
            add_expense(uid, 999.0, "Utilities", day(12), "Fiber internet", "Credit Card")
            add_expense(uid, 649.0, "Entertainment", day(5), "Streaming subscriptions", "Credit Card")

            for cat, desc, (lo, hi), per_month, method in variable:
                count = max(0, round(per_month * intensity * elapsed + rng.uniform(-0.6, 0.6)))
                for _ in range(count):
                    d = rng.randint(1, last_day)
                    add_expense(uid, float(rng.randint(lo, hi)), cat, day(d), desc, method)

    # Circles
    g_apt = create_group("Apartment 4B")
    g_trip = create_group("Goa Weekend Trip")
    for uid in [u_alice, u_bob, u_charlie]:
        add_member_to_group(g_apt, uid)
    for uid in [u_alice, u_bob, u_charlie, u_diana]:
        add_member_to_group(g_trip, uid)

    def ago(n):
        return (today - timedelta(days=n)).isoformat()

    add_shared_expense(g_apt, u_alice, 5400.0, "Monthly groceries restock", ago(1),
                       split_among=[u_alice, u_bob, u_charlie], category="Groceries")
    s_elec = add_shared_expense(g_apt, u_bob, 2880.0, "Electricity & gas bill", ago(8),
                                split_among=[u_alice, u_bob, u_charlie], category="Utilities")
    add_shared_expense(g_apt, u_alice, 1199.0, "Wi-Fi plan (quarterly)", ago(20),
                       split_among=[u_alice, u_bob, u_charlie], category="Utilities")
    add_shared_expense(g_trip, u_diana, 18000.0, "Villa booking", ago(12),
                       split_among=[u_alice, u_bob, u_charlie, u_diana], category="Travel")
    add_shared_expense(g_trip, u_bob, 4800.0, "Seafood dinner", ago(11),
                       custom_splits=dict(zip([u_alice, u_bob, u_charlie, u_diana],
                                              allocate_amounts(4800.0, [1, 2, 1, 2]))),
                       category="Food & Dining")

    # Alice paid her electricity share directly; Charlie settled his via UPI.
    for s in get_splits_for_expense(s_elec):
        if s["user_id"] == u_alice:
            mark_split_paid(s["split_id"], True)
    add_settlement(u_charlie, u_bob, 960.0, g_apt, "Electricity share", "UPI")

    return True

if __name__ == "__main__":
    init_db()
    conn = get_db_connection()
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    print("Tables in DB:", [r["name"] for r in rows])
    conn.close()
