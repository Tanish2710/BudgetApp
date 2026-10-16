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
    "sessions", "reminder_log", "splits", "shared_expenses", "settlements", "group_members", "groups",
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
    created_at     TEXT DEFAULT (datetime('now')),
    -- Accounts have a password_hash and a role ('admin' or 'user'). People without a
    -- password are contacts: they exist to split bills with and belong to owner_id.
    password_hash  TEXT,
    role           TEXT,
    is_active      INTEGER DEFAULT 1,
    owner_id       INTEGER,
    last_login     TEXT
);

-- Sign-ups and email changes waiting for the emailed code. Nothing becomes an account
-- (or changes its login email) until the code is entered.
CREATE TABLE IF NOT EXISTS pending_verifications (
    email         TEXT PRIMARY KEY,
    user_id       INTEGER,            -- set for an email change, NULL for a new sign-up
    name          TEXT,
    password_hash TEXT,
    code_hash     TEXT NOT NULL,
    expires_at    TEXT NOT NULL,
    attempts      INTEGER DEFAULT 0,
    sent_at       TEXT NOT NULL,
    created_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL,
    expires_at TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
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
    group_name TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    owner_id   INTEGER
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
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
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
        # Accounts and roles
        "ALTER TABLE users ADD COLUMN password_hash TEXT",
        "ALTER TABLE users ADD COLUMN role TEXT",
        "ALTER TABLE users ADD COLUMN is_active INTEGER DEFAULT 1",
        "ALTER TABLE users ADD COLUMN owner_id INTEGER",
        "ALTER TABLE users ADD COLUMN last_login TEXT",
        "ALTER TABLE groups ADD COLUMN owner_id INTEGER",
    ]
    for sql in migrations:
        try:
            conn.execute(sql)
        except sqlite3.OperationalError:
            pass
    conn.commit()
    _drop_global_circle_name_unique(conn)
    for sql in [
        "CREATE INDEX IF NOT EXISTS idx_users_owner ON users(owner_id)",
        "CREATE INDEX IF NOT EXISTS idx_groups_owner ON groups(owner_id)",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_groups_owner_name ON groups(owner_id, group_name)",
    ]:
        conn.execute(sql)
    conn.commit()


def _drop_global_circle_name_unique(conn):
    """Circle names used to be unique across the whole app. With separate accounts two people
    may both have an "Apartment" circle, so names are now unique per owner. SQLite can't drop a
    column constraint, so the table is rebuilt (foreign keys off, so nothing cascades)."""
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'groups'").fetchone()
    if not row or "UNIQUE" not in row["sql"].upper():
        return
    conn.commit()
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.execute("BEGIN")
        conn.execute("""CREATE TABLE groups_new (
            group_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            group_name TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            owner_id   INTEGER)""")
        conn.execute("INSERT INTO groups_new (group_id, group_name, created_at, owner_id) "
                     "SELECT group_id, group_name, created_at, owner_id FROM groups")
        conn.execute("DROP TABLE groups")
        conn.execute("ALTER TABLE groups_new RENAME TO groups")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.execute("PRAGMA foreign_keys = ON")

def init_db():
    conn = get_db_connection()
    conn.executescript(SCHEMA_SQL)
    run_migrations(conn)
    conn.close()
    return True

# --- Users CRUD ---
def create_user(name, email=None, phone=None, monthly_budget=0.0, owner_id=None):
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
            raise ValueError(f"Email '{clean_email}' is already in use.")

    # Pre-check phone uniqueness
    if clean_phone:
        existing_p = cur.execute("SELECT user_id, name FROM users WHERE phone = ?", (clean_phone,)).fetchone()
        if existing_p:
            conn.close()
            raise ValueError(f"Mobile number '{clean_phone}' is already in use.")

    try:
        cur.execute(
            "INSERT INTO users (name, email, phone, monthly_budget, owner_id) VALUES (?, ?, ?, ?, ?)",
            (name, clean_email, clean_phone, float(monthly_budget), owner_id)
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
            raise ValueError(f"Email '{clean_email}' is already in use.")

    if phone is not None and clean_phone:
        existing_p = cur.execute("SELECT user_id, name FROM users WHERE phone = ? AND user_id != ?", (clean_phone, user_id)).fetchone()
        if existing_p:
            conn.close()
            raise ValueError(f"Mobile number '{clean_phone}' is already in use.")

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

# --- Accounts, roles and what each account can see ---
# An account is a users row with a password. role is "admin" or "user". Contacts (rows with no
# password) belong to the account in owner_id; circles belong to the account that made them.

def count_accounts():
    conn = get_db_connection()
    n = conn.execute("SELECT COUNT(*) FROM users WHERE password_hash IS NOT NULL").fetchone()[0]
    conn.close()
    return n


def get_accounts():
    conn = get_db_connection()
    rows = conn.execute("""
        SELECT u.*,
               (SELECT COUNT(*) FROM expenses e WHERE e.user_id = u.user_id) AS expense_count,
               (SELECT COUNT(*) FROM users c WHERE c.owner_id = u.user_id AND c.password_hash IS NULL) AS contact_count
        FROM users u WHERE u.password_hash IS NOT NULL ORDER BY u.created_at, u.user_id
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_account_by_email(email):
    """The account (not a contact) registered with this email, or None."""
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM users WHERE LOWER(TRIM(email)) = LOWER(TRIM(?)) AND password_hash IS NOT NULL",
                       (str(email or "").strip(),)).fetchone()
    conn.close()
    return dict(row) if row else None


def create_account(name, email, password_hash):
    """
    Create a login. The first account ever becomes the admin and takes ownership of every
    person and circle already in the database; later accounts are regular users.
    A contact someone added earlier with the same email is turned into the account, so the
    person keeps the bills and balances already recorded for them.
    Returns (user_id, role).
    """
    clean_email = str(email).strip().lower()
    conn = get_db_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")  # two simultaneous first sign-ups can't both become admin
        if conn.execute("SELECT 1 FROM users WHERE LOWER(TRIM(email)) = ? AND password_hash IS NOT NULL",
                        (clean_email,)).fetchone():
            raise ValueError("An account with this email already exists. Log in instead.")
        first = conn.execute("SELECT COUNT(*) FROM users WHERE password_hash IS NOT NULL").fetchone()[0] == 0
        role = "admin" if first else "user"
        contact = conn.execute("SELECT user_id FROM users WHERE LOWER(TRIM(email)) = ?", (clean_email,)).fetchone()
        if contact:
            uid = contact["user_id"]
            conn.execute("UPDATE users SET password_hash = ?, role = ?, is_active = 1, owner_id = NULL WHERE user_id = ?",
                         (password_hash, role, uid))
        else:
            cur = conn.execute("INSERT INTO users (name, email, password_hash, role, is_active) VALUES (?, ?, ?, ?, 1)",
                               (str(name).strip(), clean_email, password_hash, role))
            uid = cur.lastrowid
        if first:
            conn.execute("UPDATE users SET owner_id = ? WHERE password_hash IS NULL AND owner_id IS NULL", (uid,))
            conn.execute("UPDATE groups SET owner_id = ? WHERE owner_id IS NULL", (uid,))
        conn.commit()
        return uid, role
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def save_pending_verification(email, code_hash, expires_at, name=None, password_hash=None, user_id=None):
    """Create or replace the pending sign-up / email change for this address."""
    conn = get_db_connection()
    conn.execute("DELETE FROM pending_verifications WHERE created_at < datetime('now', '-2 days')")
    conn.execute("""
        INSERT INTO pending_verifications (email, user_id, name, password_hash, code_hash, expires_at, attempts, sent_at)
        VALUES (?, ?, ?, ?, ?, ?, 0, ?)
        ON CONFLICT(email) DO UPDATE SET user_id = excluded.user_id, name = excluded.name,
            password_hash = excluded.password_hash, code_hash = excluded.code_hash,
            expires_at = excluded.expires_at, attempts = 0, sent_at = excluded.sent_at,
            created_at = datetime('now')
    """, (str(email).strip().lower(), user_id, name, password_hash, code_hash, expires_at, _now()))
    conn.commit(); conn.close()


def refresh_pending_code(email, code_hash, expires_at):
    conn = get_db_connection()
    conn.execute("UPDATE pending_verifications SET code_hash = ?, expires_at = ?, attempts = 0, sent_at = ? WHERE email = ?",
                 (code_hash, expires_at, _now(), str(email).strip().lower()))
    conn.commit(); conn.close()


def get_pending_verification(email):
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM pending_verifications WHERE email = ?", (str(email or "").strip().lower(),)).fetchone()
    conn.close()
    return dict(row) if row else None


def count_pending_attempt(email):
    conn = get_db_connection()
    conn.execute("UPDATE pending_verifications SET attempts = attempts + 1 WHERE email = ?", (str(email).strip().lower(),))
    conn.commit(); conn.close()


def delete_pending_verification(email):
    conn = get_db_connection()
    conn.execute("DELETE FROM pending_verifications WHERE email = ?", (str(email).strip().lower(),))
    conn.commit(); conn.close()


def set_password_hash(user_id, password_hash):
    conn = get_db_connection()
    conn.execute("UPDATE users SET password_hash = ? WHERE user_id = ?", (password_hash, user_id))
    conn.commit(); conn.close()


def set_account_role(user_id, role):
    if role not in ("admin", "user"):
        raise ValueError("Unknown role")
    conn = get_db_connection()
    conn.execute("UPDATE users SET role = ? WHERE user_id = ? AND password_hash IS NOT NULL", (role, user_id))
    conn.commit(); conn.close()


def set_account_active(user_id, active):
    conn = get_db_connection()
    conn.execute("UPDATE users SET is_active = ? WHERE user_id = ?", (1 if active else 0, user_id))
    if not active:
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    conn.commit(); conn.close()


def touch_last_login(user_id):
    conn = get_db_connection()
    conn.execute("UPDATE users SET last_login = ? WHERE user_id = ?",
                 (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id))
    conn.commit(); conn.close()


def delete_account(user_id, new_owner_id):
    """Delete an account and its own data; its contacts and circles move to new_owner_id."""
    conn = get_db_connection()
    conn.execute("UPDATE users SET owner_id = ? WHERE owner_id = ?", (new_owner_id, user_id))
    conn.execute("UPDATE groups SET owner_id = ? WHERE owner_id = ?", (new_owner_id, user_id))
    conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    conn.commit(); conn.close()


def create_session(token_hash, user_id, days=30):
    conn = get_db_connection()
    conn.execute("DELETE FROM sessions WHERE expires_at < ?", (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),))
    conn.execute("INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
                 (token_hash, user_id, (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit(); conn.close()


def get_session_user(token_hash):
    """The active account behind an unexpired session token, or None."""
    conn = get_db_connection()
    row = conn.execute("""
        SELECT u.* FROM sessions s JOIN users u ON u.user_id = s.user_id
        WHERE s.token_hash = ? AND s.expires_at > ? AND u.password_hash IS NOT NULL AND u.is_active = 1
    """, (token_hash, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_session(token_hash):
    conn = get_db_connection()
    conn.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))
    conn.commit(); conn.close()


def get_visible_groups(account):
    """Admins see every circle; everyone else sees circles they made or belong to."""
    if account["role"] == "admin":
        return get_all_groups()
    conn = get_db_connection()
    rows = conn.execute("""
        SELECT * FROM groups WHERE owner_id = ?
           OR group_id IN (SELECT group_id FROM group_members WHERE user_id = ?)
        ORDER BY group_name
    """, (account["user_id"], account["user_id"])).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_managed_profiles(account):
    """People whose personal budget this account may open: admins, everyone; others,
    themselves plus the contacts they added."""
    conn = get_db_connection()
    if account["role"] == "admin":
        rows = conn.execute("SELECT * FROM users ORDER BY name").fetchall()
    else:
        rows = conn.execute("""
            SELECT * FROM users WHERE user_id = ? OR (owner_id = ? AND password_hash IS NULL)
            ORDER BY CASE WHEN user_id = ? THEN 0 ELSE 1 END, name
        """, (account["user_id"],) * 3).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_visible_people(account, group_ids):
    """Everyone this account can see by name: its own profiles plus members of its circles."""
    if account["role"] == "admin":
        return get_all_users()
    people = {u["user_id"]: u for u in get_managed_profiles(account)}
    if group_ids:
        conn = get_db_connection()
        ph = ",".join("?" * len(group_ids))
        for r in conn.execute(f"SELECT DISTINCT u.* FROM users u JOIN group_members gm ON gm.user_id = u.user_id "
                              f"WHERE gm.group_id IN ({ph})", list(group_ids)).fetchall():
            people.setdefault(r["user_id"], dict(r))
        conn.close()
    return sorted(people.values(), key=lambda u: u["name"].lower())


def circle_name_taken(owner_id, group_name, exclude_group_id=None):
    conn = get_db_connection()
    row = conn.execute("SELECT 1 FROM groups WHERE owner_id IS ? AND LOWER(group_name) = LOWER(?) AND group_id IS NOT ?",
                       (owner_id, str(group_name).strip(), exclude_group_id)).fetchone()
    conn.close()
    return bool(row)


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
def create_group(group_name, owner_id=None):
    group_name = str(group_name or "").strip()
    if not group_name:
        raise ValueError("Circle name is required.")
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO groups (group_name, owner_id) VALUES (?, ?)", (group_name, owner_id))
        conn.commit()
        gid = cur.lastrowid
    except sqlite3.IntegrityError:
        raise ValueError(f"You already have a circle named '{group_name}'.")
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
        raise ValueError(f"There's already a circle named '{group_name}'.")
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

def get_settlements(group_id=None, group_ids=None):
    """Payments in one circle, in the circles listed in group_ids, or (both None) everywhere."""
    if group_id is None and group_ids is not None:
        wanted = set(group_ids)
        return [r for r in get_settlements() if r["group_id"] in wanted]
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

def reset_data():
    """Erase all budget data but keep every account (logins, roles) and app settings.
    Accounts start over with no transactions, budgets, contacts or circles."""
    conn = get_db_connection()
    for t in ["reminder_log", "splits", "shared_expenses", "settlements", "group_members", "groups",
              "category_budgets", "incomes", "expenses"]:
        conn.execute(f"DELETE FROM {t}")
    conn.execute("DELETE FROM users WHERE password_hash IS NULL")
    conn.execute("UPDATE users SET monthly_budget = 0")
    conn.commit()
    conn.close()


# --- Demo Data Generator ---
def _month_start(d, months_back):
    """First day of the month `months_back` months before d (negative = months ahead)."""
    idx = d.year * 12 + (d.month - 1) - months_back
    return date(idx // 12, idx % 12 + 1, 1)

month_start = _month_start


def seed_comprehensive_demo_data(reset=False, as_user_id=None):
    """Populate a realistic six-month dataset for demos and testing. Amounts are in INR.

    With as_user_id (an account), that account plays the main character (the richest
    history) and owns the sample contacts and circles; other accounts are kept, empty."""
    if as_user_id:
        init_db()
        reset_data()
    elif reset:
        reset_database()
    else:
        init_db()

    conn = get_db_connection()
    user_count = conn.execute("SELECT count(*) FROM users WHERE password_hash IS NULL").fetchone()[0]
    conn.close()
    if user_count > 0 and not reset and not as_user_id:
        return False  # Already seeded

    rng = random.Random(42)
    today = date.today()

    if as_user_id:
        u_alice = as_user_id
        update_user(u_alice, monthly_budget=60000.0)
    else:
        u_alice = create_user("Alice Johnson", "alice@example.com", "9876543210", 60000.0)
    owner = as_user_id

    def contact(name, email, phone, budget):
        try:
            return create_user(name, email, phone, budget, owner_id=owner)
        except ValueError:  # an account already uses the sample email or number
            return create_user(name, None, None, budget, owner_id=owner)

    u_bob = contact("Bob Martinez", "bob@example.com", "9876543211", 45000.0)
    u_charlie = contact("Charlie Chen", "charlie@example.com", "9876543212", 40000.0)
    u_diana = contact("Diana Prince", "diana@example.com", "9876543213", 50000.0)

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
    g_apt = create_group("Apartment 4B", owner_id=owner)
    g_trip = create_group("Goa Weekend Trip", owner_id=owner)
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
