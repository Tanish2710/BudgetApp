# Smart Budgeter ✦ Debt-Splitter Pro

An executive personal finance command center and Splitwise-style group debt-splitting ecosystem. Log personal expenses and incomes, establish category-level budgets with live pacing analysis, split group bills across 4 flexible modes, simplify multi-party debts with greedy algorithms, settle up with 1-click flows, and dispatch automated payment reminder statements via Email.

---

## 🚀 Key Improvements & Features

### 1. Modern Financial Design System
- **Executive KPI Cards**: Real-time monthly spend, net cash flow, savings rate, daily safe spend pacing, and circle split position.
- **Rupees (₹) Default & Three-Dots (⋮) Settings**: Currency defaults to Indian Rupees (`₹`). Currency preference, profile editing, and database actions are cleanly housed in a floating three-dots (`⋮`) popover menu in the top navigation bar.

### 2. Personal Budgeting & Cash Flow Tracking
- **Income & Cash Flow Engine**: Track multiple income streams (Salary, Freelance, Investments) and monitor Net Cash Flow (`Income - Expense`) and Savings Rate %.
- **Daily Budget Pacing & Health**: Live calculation of daily burn rate, remaining days in month, and safe spending allowance per day to prevent month-end budget deficits.
- **Category-Level Budgets**: Allocate explicit monthly spending caps per category (Dining, Rent, Utilities, Groceries, Entertainment) with progress bars and color-coded threshold alerts.
- **Ledger Search & Filters**: Search transactions by keyword, filter by category/user/date range, and export to CSV.

### 3. Splitwise-Style Shared Expenses & Debt Engine
- **4 Flexible Splitting Modes**:
  1. **Equal Split (=)**: Auto-divides bill evenly with exact penny remainder handling.
  2. **Exact Dollar Amounts ($)**: Custom per-person dollar amounts with live mathematical balance validation.
  3. **Percentage Split (%)**: Custom percentage allocation with 100% total validation.
  4. **Shares / Parts (x)**: Weighted splitting (e.g. 2 shares vs 1 share).
- **Circle & Group Management**: Create circles (Roommates, Trip Squad), add/remove members, and manage shared bill history.
- **Split Toggles**: Toggle individual splits between "Paid" and "Unpaid" with instant balance recalibration.

### 4. Greedy Debt Simplification & 1-Click Settle
- **Minimal Transaction Settlement**: Reduces $N$ circular group debts to the minimum direct transactions required using greedy matching between largest debtors and largest creditors.
- **Directional Sankey Flow Graph**: Plotly Sankey diagram illustrating directional debt flows between circle members.
- **⚡ 1-Click "Settle Up"**: Click "Settle Up" on any debt card to instantly pre-fill payer, receiver, amount, and notes in the settlement form.
- **Payment Method Tracking**: Record repayments via Cash, Venmo, UPI, Bank Transfer, Zelle, or PayPal.

### 5. Automated Email Reminders & Statements Engine
- **Dedicated Email Delivery**: Send formal payment statements and gentle payment reminders via email (SMTP) to delinquent debtors.
- **HTML & Plain-Text Statement Templates**: Responsive, professional financial statements featuring item details, original payer, debt share, and settlement instructions.
- **In-App Preview & 1-Click Send**: Preview the rendered HTML email statement before sending, with 1-click dispatch per split or bulk dispatch across all overdue debts.
- **Dry-Run Safe Mode**: Default simulation mode verifies recipient emails, templates, and triggers without sending live messages.
- **Interactive SMTP Config & Connection Test**: Enter and test SMTP credentials (e.g. Gmail App Passwords) directly in the UI.
- **Headless CLI & Cron Automation**: Standalone `reminders.py --live` for scheduled daily reminder dispatching.

---

## 🛠️ Database Schema (SQLite)

```sql
users(user_id, name, email, monthly_budget, created_at)
expenses(exp_id, user_id, amount, category, description, date, payment_method, notes)
incomes(income_id, user_id, amount, source, description, date)
category_budgets(budget_id, user_id, category, monthly_limit)
groups(group_id, group_name, created_at)
group_members(group_id, user_id, joined_at)
shared_expenses(shared_id, group_id, payer_id, amount, description, category, date)
splits(split_id, shared_id, user_id, amount_owed, is_paid)
settlements(settlement_id, from_user, to_user, amount, group_id, date, note, payment_method)
```

Indexes on `expenses(user_id, date)`, `incomes(user_id, date)`, `shared_expenses(group_id)`, `splits(user_id)`. Foreign keys enforced with cascading deletes.

---

## 💻 Setup & Running

```bash
# 1. Install dependencies
/home/tanishagrawal/.local/bin/python3.11 -m pip install -r requirements.txt

# 2. Initialize database & seed demo data
/home/tanishagrawal/.local/bin/python3.11 database.py

# 3. Launch the Streamlit application
./run.sh
# or:
/home/tanishagrawal/.local/bin/python3.11 -m streamlit run app.py
```

---

## 🔔 Automation Setup (Reminders CLI)

```bash
# Print summary of pending and overdue splits:
python reminders.py --summary

# Simulate dispatch (Dry-run mode):
python reminders.py --overdue-days 3

# Send live emails & Discord notifications:
export SMTP_HOST="smtp.gmail.com"
export SMTP_PORT="587"
export SMTP_USER="you@gmail.com"
export SMTP_PASS="your-app-password"
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."

python reminders.py --live --overdue-days 3

# Cron setup: Run daily at 9:00 AM
# 0 9 * * * cd /home/tanishagrawal/BudgetApp && /home/tanishagrawal/.local/bin/python3.11 reminders.py --live >> reminders.log 2>&1
```

---

## 💼 Resume & Portfolio Highlights
- **Engineered Full Financial Architecture**: Designed normalized SQLite schema with 9 tables, foreign key constraints, composite keys, and indexing.
- **Greedy Optimization Algorithm**: Implemented minimal cash-flow debt simplification reducing $O(N^2)$ circular debts to minimal direct transfers.
- **Automated Email Reminders & Statements Engine**: Created an automated email notification pipeline using Python's `smtplib` and `email` packages to render and dispatch professional multipart (HTML + plain text) financial statements with live and dry-run modes.
