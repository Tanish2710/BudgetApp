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

On first launch you can create your profile or load six months of sample data. The SQLite database lives at `data/finance.db` (override with `BUDGET_DB_PATH`).

## Project layout

| File | Purpose |
|---|---|
| `app.py` | Streamlit UI (multi-page navigation) |
| `charts.py` | Plotly chart builders sharing one visual style and colour palette |
| `logic.py` | Balances, debt simplification, budget pacing, reminder statements |
| `reminders.py` | Email rendering and delivery, reminder queue, daily scheduler, CLI |
| `database.py` | SQLite schema, migrations, CRUD and sample data |

## Database schema

```sql
users(user_id, name, email, phone, monthly_budget, created_at)
expenses(exp_id, user_id, amount, category, description, date, payment_method, notes)
incomes(income_id, user_id, amount, source, description, date)
category_budgets(budget_id, user_id, category, monthly_limit)
groups(group_id, group_name, created_at)
group_members(group_id, user_id, joined_at)
shared_expenses(shared_id, group_id, payer_id, amount, description, category, date)
splits(split_id, shared_id, user_id, amount_owed, is_paid)
settlements(settlement_id, from_user, to_user, amount, group_id, date, note, payment_method)
reminder_log(log_id, user_id, group_id, amount, recipient, subject, status, trigger, message, created_at)
app_settings(key, value)
```

Foreign keys are enforced with cascading deletes, and the hot query paths are indexed.
