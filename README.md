# Smart Budgeter

Personal budgeting and shared expenses in one Streamlit app: track spending against a monthly budget and category limits, see trends over time, split bills with flatmates or on trips, settle up with the fewest payments, and email payment reminders automatically.

## Features

**Personal**
- **Overview**: this month's spending, cash flow, a daily allowance that keeps you within budget, and your shared balance. Charts show cumulative spending against an even budget pace (with a month-end projection) and spending by category against limits.
- **Transactions**: add expenses and income; search, filter by category and period, edit or delete any record; export to CSV.
- **Budgets**: a monthly budget plus per-category limits, viewable for any past month.
- **Reports**: income vs spending, net savings and spending mix by month, with a table view.

**Shared**
- **Circles**: groups of people who share bills. Split a bill equally, by exact amounts, by percentages or by shares; amounts are allocated to the cent so they always add up to the total.
- **Settle up**: net balances, the fewest payments needed within each circle, one-click payment recording, a payment-flow diagram and a payment history.
- **Reminders**: one consolidated email per person who owes money, covering every circle, with the items, payments already made, balance due and exactly whom to pay.

**Light and dark mode**: a *Dark mode* switch at the bottom of the sidebar. The app starts in light mode and each browser remembers its choice; the light/dark buttons in Streamlit's ⋮ menu stay in step with the switch. Both palettes live in `.streamlit/config.toml` (`[theme.light]`, `[theme.dark]`), with matching CSS tokens in `app.py` and chart colours in `charts.py`.

## Accounts and roles

Everyone logs in with an email and password. Accounts are created from the **Create account** tab on the login screen, and only exist once the person enters the 6-digit code emailed to that address, so nobody can sign up with an email they don't control. Changing your login email in Settings works the same way. Codes expire after 15 minutes and stop working after 5 wrong tries.

Verification emails go out through the same SMTP server as reminders (see [Email (SMTP)](#email-smtp)). Until one is configured nobody can sign up, so set the `SMTP_*` environment variables before creating the first account.

- **The first account becomes the admin.** Anything already in the database (people, circles, transactions) is assigned to that admin, so nothing is lost when upgrading. Every later account is a regular user.
- **Users** see and edit only their own budget, the people they've added to split bills with, and the circles they created or belong to. To split with someone who has their own account, add them to a circle by their account email. If you add a person and they later sign up with the same email, they take over that profile, including the bills already recorded for them.
- **Admins** can do everything a user can, plus: the **Admin** page (every account, promote/demote, deactivate/reactivate, set a new password, delete an account, open new sign-ups or close them), the **Reminders** page (the app-wide email server and schedule), the app currency, and resetting or loading sample data. The *Viewing as* box in the sidebar lets an admin open anyone's budget.

Passwords are stored as salted PBKDF2-SHA256 hashes. Logging in creates a 30-day session; the browser keeps a random token in a cookie and the database keeps only its hash, so logging out or deactivating an account ends it. After five wrong passwords for an email, logins for it pause for five minutes. There's no email-based password reset: an admin sets a new password from the Admin page.

## Automatic reminders

Configure everything on the **Reminders** page:

| Setting | Meaning |
|---|---|
| Send automatically | Run once a day at the chosen hour |
| Oldest item at least (days) | Only remind once the oldest unpaid item is this old |
| Wait between reminders (days) | Never email the same person more often than this |
| Skip balances under | Ignore trivial amounts |
| Send real emails | Off = dry run: emails are rendered and logged, not sent |

Balances account for recorded payments and shares marked paid, so people who have paid stop receiving reminders. Every attempt (sent, simulated, failed) is logged in the History tab.

The schedule runs inside the app process while it is running. To run it when the app is closed, call the CLI from cron. It reads the same settings and claims each day's run atomically, so the app and cron never double-send:

```bash
# Check hourly; the run happens once per day after the configured send hour
5 * * * * cd /path/to/BudgetApp && python3 reminders.py --auto >> reminders.log 2>&1
```

Other CLI commands:

```bash
python3 reminders.py --summary            # who owes what and who is due
python3 reminders.py --run-now            # send to everyone due now (uses the saved live/dry-run mode)
python3 reminders.py --run-now --dry-run  # force a dry run
```

### Email (SMTP)

Enter SMTP details under **Reminders → Email delivery** (for Gmail: `smtp.gmail.com`, port `587`, and an [app password](https://support.google.com/accounts/answer/185833)). Port 465 uses implicit SSL; other ports use STARTTLS. Settings are stored in the local database; any field left blank falls back to these environment variables:

```bash
export SMTP_HOST="smtp.gmail.com" SMTP_PORT="587"
export SMTP_USER="you@gmail.com" SMTP_PASS="your-app-password" FROM_EMAIL="you@gmail.com"
```

## Setup

```bash
pip install -r requirements.txt
./run.sh            # or: python3 -m streamlit run app.py
```

On first launch you create the admin account, optionally filled with six months of sample data. The SQLite database lives at `data/finance.db` (override with `BUDGET_DB_PATH`).

## Project layout

| File | Purpose |
|---|---|
| `app.py` | Streamlit UI (multi-page navigation) |
| `charts.py` | Plotly chart builders sharing one visual style and colour palette |
| `logic.py` | Balances, debt simplification, budget pacing, reminder statements |
| `reminders.py` | Email rendering and delivery, reminder queue, daily scheduler, CLI |
| `auth.py` | Password hashing, sign-up, login, sessions |
| `database.py` | SQLite schema, migrations, CRUD, per-account visibility and sample data |
| `tests/` | Checks for balances, accounts, circles and passwords (`pip install pytest`, then `python -m pytest tests`) |

## Database schema

```sql
users(user_id, name, email, phone, monthly_budget, created_at,
      password_hash, role, is_active, owner_id, last_login)   -- accounts have a password; contacts belong to owner_id
sessions(token_hash, user_id, expires_at, created_at)
expenses(exp_id, user_id, amount, category, description, date, payment_method, notes)
incomes(income_id, user_id, amount, source, description, date)
category_budgets(budget_id, user_id, category, monthly_limit)
groups(group_id, group_name, created_at, owner_id)            -- circle names are unique per owner
group_members(group_id, user_id, joined_at)
shared_expenses(shared_id, group_id, payer_id, amount, description, category, date)
splits(split_id, shared_id, user_id, amount_owed, is_paid)
settlements(settlement_id, from_user, to_user, amount, group_id, date, note, payment_method)
reminder_log(log_id, user_id, group_id, amount, recipient, subject, status, trigger, message, created_at)
app_settings(key, value)
```

Foreign keys are enforced with cascading deletes, and the hot query paths are indexed.
