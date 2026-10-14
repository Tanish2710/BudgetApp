"""
database.py - Smart Budgeter "Debt-Splitter" Persistence Layer
SQLite with normalized schema, foreign keys, full CRUD, and migrations.
"""
import sqlite3
import os
from datetime import datetime, date, timedelta
import random

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "finance.db")

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
    date           TEXT DEFAULT (datetime('now')),
    note           TEXT,
    payment_method TEXT DEFAULT 'Cash',
    FOREIGN KEY(from_user) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY(to_user)   REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY(group_id)  REFERENCES groups(group_id) ON DELETE SET NULL
);

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
        "ALTER TABLE settlements ADD COLUMN payment_method TEXT DEFAULT 'Cash'"
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
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO groups (group_name) VALUES (?)", (group_name,))
    conn.commit()
    gid = cur.lastrowid
    conn.close()
    return gid

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
def add_shared_expense(group_id, payer_id, amount, description, date=None, split_among=None, custom_splits=None, category="General"):
    if date is None: date = datetime.now().strftime("%Y-%m-%d")
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO shared_expenses (group_id, payer_id, amount, description, date, category) VALUES (?, ?, ?, ?, ?, ?)",
        (group_id, payer_id, amount, description, date, category)
    )
    shared_id = cur.lastrowid
    if custom_splits:
        for uid, owed in custom_splits.items():
            cur.execute("INSERT INTO splits (shared_id, user_id, amount_owed) VALUES (?, ?, ?)", (shared_id, uid, owed))
    else:
        if split_among is None:
            members = conn.execute("SELECT user_id FROM group_members WHERE group_id = ?", (group_id,)).fetchall()
            split_among = [r["user_id"] for r in members]
        if not split_among: raise ValueError("No members to split among")
        per_person = round(amount / len(split_among), 2)
        remainder = round(amount - per_person * len(split_among), 2)
        for i, uid in enumerate(split_among):
            owed = per_person + (remainder if i == 0 else 0)
            cur.execute("INSERT INTO splits (shared_id, user_id, amount_owed) VALUES (?, ?, ?)", (shared_id, uid, owed))
    conn.commit()
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
def add_settlement(from_user, to_user, amount, group_id=None, note="", payment_method="Cash"):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO settlements (from_user, to_user, amount, group_id, note, payment_method) VALUES (?, ?, ?, ?, ?, ?)",
        (from_user, to_user, amount, group_id, note, payment_method)
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

# --- Demo Data Generator ---
def seed_comprehensive_demo_data(reset=False):
    """Populates realistic, vibrant financial dataset for instant demo and testing."""
    conn = get_db_connection()
    if reset:
        tables = ["splits", "shared_expenses", "settlements", "group_members", "groups", "category_budgets", "incomes", "expenses", "users"]
        for t in tables:
            conn.execute(f"DROP TABLE IF EXISTS {t}")
        conn.commit()
    conn.close()
    init_db()

    conn = get_db_connection()
    user_count = conn.execute("SELECT count(*) FROM users").fetchone()[0]
    conn.close()

    if user_count > 0 and not reset:
        return False  # Already seeded

    # Create Core Users
    u_alice = create_user("Alice Johnson", "alice@example.com", "9876543210", 2200.0)
    u_bob = create_user("Bob Martinez", "bob@example.com", "9876543211", 1800.0)
    u_charlie = create_user("Charlie Chen", "charlie@example.com", "9876543212", 1500.0)
    u_diana = create_user("Diana Prince", "diana@example.com", "9876543213", 2000.0)

    # Category Budgets for Alice
    set_category_budget(u_alice, "Food & Dining", 500.0)
    set_category_budget(u_alice, "Housing & Rent", 900.0)
    set_category_budget(u_alice, "Groceries", 300.0)
    set_category_budget(u_alice, "Utilities", 150.0)
    set_category_budget(u_alice, "Entertainment", 150.0)
    set_category_budget(u_alice, "Transportation", 200.0)

    # Incomes for Alice
    today = date.today()
    first_of_month = today.replace(day=1)
    add_income(u_alice, 3200.0, "Salary", first_of_month.isoformat(), "Tech Corp Bi-weekly Pay")
    add_income(u_alice, 450.0, "Freelance", (today - timedelta(days=4)).isoformat(), "UI/UX Consult Project")
    add_income(u_bob, 2800.0, "Salary", first_of_month.isoformat(), "Monthly Paycheck")
    add_income(u_charlie, 2400.0, "Salary", first_of_month.isoformat(), "Full-time Engineering")

    # Personal Expenses for Alice & others
    personal_samples = [
        (u_alice, 850.0, "Housing & Rent", first_of_month.isoformat(), "Monthly Apartment Rent Share", "Bank Transfer"),
        (u_alice, 115.40, "Groceries", (today - timedelta(days=2)).isoformat(), "Trader Joe's organic restock", "Credit Card"),
        (u_alice, 38.50, "Food & Dining", (today - timedelta(days=3)).isoformat(), "Sushi dinner with friends", "Card"),
        (u_alice, 14.99, "Entertainment", (today - timedelta(days=6)).isoformat(), "Netflix & Spotify subscription", "Card"),
        (u_alice, 45.00, "Transportation", (today - timedelta(days=7)).isoformat(), "Weekly transit card reload", "Card"),
        (u_alice, 82.20, "Utilities", (today - timedelta(days=9)).isoformat(), "High-speed Fiber Internet", "Bank Transfer"),
        (u_alice, 26.50, "Food & Dining", (today - timedelta(days=11)).isoformat(), "Chipotle burrito bowls", "UPI / Cash"),
        (u_alice, 64.00, "Shopping", (today - timedelta(days=12)).isoformat(), "Ergonomic keyboard wrist rest", "Credit Card"),
        (u_bob, 750.0, "Housing & Rent", first_of_month.isoformat(), "Rent Share", "Bank Transfer"),
        (u_bob, 89.0, "Groceries", (today - timedelta(days=5)).isoformat(), "Whole Foods run", "Card"),
        (u_charlie, 42.0, "Food & Dining", (today - timedelta(days=4)).isoformat(), "Italian Bistro lunch", "Card"),
    ]
    for uid, amt, cat, dt, desc, pmethod in personal_samples:
        add_expense(uid, amt, cat, dt, desc, pmethod)

    # Groups
    g_apt = create_group("Apartment 4B Circle")
    g_trip = create_group("Weekend Lakehouse Trip")

    for uid in [u_alice, u_bob, u_charlie]:
        add_member_to_group(g_apt, uid)
    for uid in [u_alice, u_bob, u_charlie, u_diana]:
        add_member_to_group(g_trip, uid)

    # Shared Expenses
    s1 = add_shared_expense(
        g_apt, u_alice, 180.0, "Costco Bulk Household Supplies",
        (today - timedelta(days=1)).isoformat(),
        split_among=[u_alice, u_bob, u_charlie], category="Groceries"
    )
    s2 = add_shared_expense(
        g_apt, u_bob, 96.0, "Electricity & Gas Bill",
        (today - timedelta(days=8)).isoformat(),
        split_among=[u_alice, u_bob, u_charlie], category="Utilities"
    )
    s3 = add_shared_expense(
        g_trip, u_diana, 440.0, "Lakehouse Airbnb Reservation",
        (today - timedelta(days=5)).isoformat(),
        split_among=[u_alice, u_bob, u_charlie, u_diana], category="Travel"
    )

    # Mark s2 for Alice paid (so Bob's electricity bill has partial payments)
    splits_s2 = get_splits_for_expense(s2)
    for s in splits_s2:
        if s["user_id"] == u_alice:
            mark_split_paid(s["split_id"], True)

    # Record a settlement: Charlie settled $32 with Bob
    add_settlement(u_charlie, u_bob, 32.0, g_apt, "Settled electricity bill via Venmo", "Venmo")

    return True

if __name__ == "__main__":
    init_db()
    conn = get_db_connection()
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    print("Tables in DB:", [r["name"] for r in rows])
    conn.close()
