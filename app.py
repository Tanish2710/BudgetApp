"""
app.py - Smart Budgeter

Personal budgeting (expenses, income, monthly and category budgets, reports) and
shared expenses (circles, bill splitting, settle-up suggestions, payment reminders).
"""
import functools
import html
import os
import sys
from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
import charts  # noqa: E402
import database as db  # noqa: E402
import logic  # noqa: E402
import reminders  # noqa: E402

st.set_page_config(
    page_title="Smart Budgeter",
    page_icon=":material/account_balance_wallet:",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource(show_spinner=False)
def _bootstrap():
    """Runs once per server process: create/migrate the schema and start the reminder scheduler."""
    db.init_db()
    reminders.start_background_scheduler()
    return True


_bootstrap()

SETTINGS = reminders.get_settings()
CURR = SETTINGS.get("currency") or "₹"
CURRENCIES = ["₹", "$", "€", "£", "¥"]

# ---------------------------------------------------------------------------
# Light / dark mode
# ---------------------------------------------------------------------------
# Streamlit's own widgets take their colours from [theme.light] / [theme.dark] in
# .streamlit/config.toml; the browser remembers which one is active in localStorage.
# Python needs to know the choice from the very first run (for the CSS tokens and
# the chart colours), so it is mirrored into a cookie that arrives with the request.
THEME_COOKIE = "sb_theme"
PROFILE_COOKIE = "sb_profile"  # carries "Viewing as" across the reload a theme switch needs

if "dark_mode" not in st.session_state:
    st.session_state["dark_mode"] = st.context.cookies.get(THEME_COOKIE) == "dark"
DARK = st.session_state["dark_mode"]

TOKENS = {
    False: {
        "ink": "#2b2d42", "ink-2": "#565a6e", "muted": "#80849a", "line": "#e2e4ee",
        "surface": "#fcfcfe", "plane": "#f5f6fa", "track": "#eceef5", "accent": "#5274c4",
        "pos": "#2f7d5b", "neg": "#bb4a48", "warn": "#93661a", "blue": "#3f63b0",
        "pos-bg": "#eef8f2", "pos-line": "#cfe8da", "neg-bg": "#fdf2f1", "neg-line": "#f4d6d3",
        "warn-bg": "#fdf7ea", "warn-line": "#f0e0b8", "blue-bg": "#eef2fb", "blue-line": "#d6e0f5",
    },
    True: {
        "ink": "#e3e5f0", "ink-2": "#b3b7ca", "muted": "#8c91a8", "line": "#343849",
        "surface": "#232636", "plane": "#1d1f2b", "track": "#2e3244", "accent": "#6f8dd6",
        "pos": "#86d0aa", "neg": "#f0a19e", "warn": "#e8c47e", "blue": "#a3bbf0",
        "pos-bg": "#1f3329", "pos-line": "#2f4d3d", "neg-bg": "#3a2427", "neg-line": "#5a3436",
        "warn-bg": "#36301f", "warn-line": "#54482b", "blue-bg": "#232c45", "blue-line": "#34416a",
    },
}


def _theme_sync_script(dark, switching, profile_id=None, run=0):
    """Keep Streamlit's painted theme, its stored preference and our cookie in step.

    After the sidebar switch (or on a first visit) the switch wins. Otherwise whatever the
    page is painted in wins, so a change made from Streamlit's own settings menu sticks.
    Either way the page reloads once when Python's idea of the mode was wrong.
    """
    want = "Dark" if dark else "Light"
    profile = f"document.cookie = '{PROFILE_COOKIE}={int(profile_id)}; path=/; max-age=60; SameSite=Lax';" if profile_id else ""
    return f"""<script>
/* run {run} */
(() => {{
  const want = "{want}";
  const key = "stActiveTheme-" + window.location.pathname + "-v2";
  const setCookie = (mode) => {{
    document.cookie = "{THEME_COOKIE}=" + mode.toLowerCase() + "; path=/; max-age=31536000; SameSite=Lax";
  }};
  const reload = () => {{ {profile} window.location.reload(); }};
  const paintedMode = () => {{
    const app = document.querySelector(".stApp");
    const rgb = app ? getComputedStyle(app).backgroundColor.match(/\\d+/g) : null;
    return rgb ? ((0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]) < 128 ? "Dark" : "Light") : null;
  }};
  // Reload as soon as the sidebar switch is clicked, instead of waiting for Python to rerun
  // the page in the old theme first. The Python path below remains for keyboard toggles.
  window.__sbSwitchTo = (mode) => {{
    setCookie(mode);
    window.localStorage.setItem(key, JSON.stringify(mode));
    reload();
  }};
  window.__sbWant = want;
  if (!window.__sbFastSwitch) {{
    window.__sbFastSwitch = true;
    document.addEventListener("click", (e) => {{
      const label = e.target.closest('[data-testid="stSidebar"] label');
      if (label && label.textContent.trim() === "Dark mode") {{
        window.__sbSwitchTo(window.__sbWant === "Dark" ? "Light" : "Dark");
      }}
    }}, true);
  }}
  const painted = paintedMode();
  let stored = null;
  try {{ stored = JSON.parse(window.localStorage.getItem(key)); }} catch (e) {{}}
  // Streamlit stores "System" until someone picks Light or Dark; treat that as no choice yet.
  if ({'true' if switching else 'false'} || (stored !== "Light" && stored !== "Dark")) {{
    setCookie(want);
    window.localStorage.setItem(key, JSON.stringify(want));
    if (painted && painted !== want) return reload();
  }} else if (painted && painted !== want) {{
    setCookie(painted);
    return reload();
  }}
  // The light/dark buttons in Streamlit's own menu repaint without a rerun; follow them.
  clearInterval(window.__sbThemeWatch);
  window.__sbThemeWatch = setInterval(() => {{
    const now = paintedMode();
    if (now && now !== want) {{ clearInterval(window.__sbThemeWatch); setCookie(now); reload(); }}
  }}, 700);
}})();
</script>"""


def _on_theme_toggle():
    st.session_state["_theme_switch"] = True


def theme_toggle(profile_id=None):
    """Sidebar switch between light and dark mode."""
    st.session_state["_theme_runs"] = st.session_state.get("_theme_runs", 0) + 1
    with st.sidebar:
        st.toggle("Dark mode", key="dark_mode", on_change=_on_theme_toggle)
        st.html(_theme_sync_script(st.session_state["dark_mode"], st.session_state.pop("_theme_switch", False),
                                   profile_id, st.session_state["_theme_runs"]),
                unsafe_allow_javascript=True)


# ---------------------------------------------------------------------------
# Styles (layered on the theme in .streamlit/config.toml)
# ---------------------------------------------------------------------------
_root_vars = "; ".join(f"--{k}: {v}" for k, v in TOKENS[DARK].items())
st.markdown(f"<style>:root {{ {_root_vars}; color-scheme: {'dark' if DARK else 'light'}; }}</style>",
            unsafe_allow_html=True)
st.markdown("""
<style>
  .block-container { max-width: 1240px; padding-top: 2.4rem; padding-bottom: 4rem; }
  footer { display: none !important; }
  h1, h2, h3, h4 { letter-spacing: -0.015em; }

  /* Bordered containers read as white cards on the off-white page */
  [data-testid="stLayoutWrapper"] > [data-testid="stVerticalBlock"] { background: var(--surface); }
  /* ...but not the plain container each fragment() renders into (see fragment() below) */
  [data-testid="stLayoutWrapper"] > [data-testid="stVerticalBlock"]:has(> [data-testid="stElementContainer"] .sb-fragment) {
    background: transparent; }
  [data-testid="stElementContainer"]:has(.sb-fragment) { display: none; }

  .page-head { margin: 0 0 1.25rem 0; }
  .page-head h1 { font-size: 1.55rem; font-weight: 700; margin: 0; padding: 0; color: var(--ink); }
  .page-head p { margin: .25rem 0 0 0; color: var(--ink-2); font-size: .92rem; }

  .section-title { font-size: .98rem; font-weight: 600; color: var(--ink); margin: 0 0 .1rem 0; }
  .section-sub { font-size: .82rem; color: var(--muted); margin: 0 0 .6rem 0; }

  .tile { background: var(--surface); border: 1px solid var(--line); border-radius: 10px;
          padding: 14px 16px; height: 100%; min-height: 124px; }
  .tile-label { font-size: .78rem; font-weight: 500; color: var(--ink-2); }
  .tile-value { font-size: 1.55rem; font-weight: 650; color: var(--ink); margin: 4px 0 2px 0;
                letter-spacing: -0.02em; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .tile-sub { font-size: .8rem; color: var(--muted); }
  .tone-pos { color: var(--pos) !important; }
  .tone-neg { color: var(--neg) !important; }
  .tone-warn { color: var(--warn) !important; }
  .meter { height: 6px; background: var(--track); border-radius: 3px; margin: 8px 0 6px 0; overflow: hidden; }
  .meter > span { display: block; height: 100%; border-radius: 3px; }

  .row { display: flex; align-items: center; justify-content: space-between; gap: 12px;
         padding: 10px 0; border-bottom: 1px solid var(--track); }
  .row:last-child { border-bottom: none; }
  .row-main { font-size: .9rem; color: var(--ink); font-weight: 500; }
  .row-meta { font-size: .78rem; color: var(--muted); margin-top: 1px; }
  .row-amt { font-size: .92rem; font-weight: 600; color: var(--ink); white-space: nowrap;
             font-variant-numeric: tabular-nums; }

  .chip { display: inline-block; font-size: .72rem; font-weight: 600; padding: 2px 8px; border-radius: 999px;
          border: 1px solid var(--line); color: var(--ink-2); background: var(--plane); white-space: nowrap; }
  .chip-pos { color: var(--pos); background: var(--pos-bg); border-color: var(--pos-line); }
  .chip-neg { color: var(--neg); background: var(--neg-bg); border-color: var(--neg-line); }
  .chip-warn { color: var(--warn); background: var(--warn-bg); border-color: var(--warn-line); }
  .chip-blue { color: var(--blue); background: var(--blue-bg); border-color: var(--blue-line); }

  .empty { text-align: center; padding: 36px 16px; color: var(--ink-2); }
  .empty b { display: block; color: var(--ink); font-size: 1rem; margin-bottom: 4px; }
  .muted { color: var(--muted); font-size: .82rem; }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
esc = html.escape


def fmt(v, decimals=2):
    try:
        v = float(v or 0)
    except (TypeError, ValueError):
        v = 0.0
    sign = "-" if v < -0.004 else ""
    return f"{sign}{CURR}{abs(v):,.{decimals}f}"


def fmt_signed(v, decimals=2):
    return ("+" if v > 0.004 else "") + fmt(v, decimals)


def nice_date(iso):
    try:
        return date.fromisoformat(str(iso)[:10]).strftime("%d %b %Y")
    except ValueError:
        return str(iso)


def month_label(ym):
    return datetime.strptime(ym, "%Y-%m").strftime("%B %Y")


def money_col(label):
    return st.column_config.NumberColumn(label, format=f"{CURR}%,.2f")


def flash(msg, icon=":material/check_circle:"):
    """Queue a toast that survives the rerun that follows a write."""
    st.session_state.setdefault("_flash", []).append((msg, icon))


def page_header(title, subtitle=""):
    sub = f"<p>{esc(subtitle)}</p>" if subtitle else ""
    st.markdown(f"<div class='page-head'><h1>{esc(title)}</h1>{sub}</div>", unsafe_allow_html=True)


def section(title, subtitle=""):
    st.markdown(f"<div class='section-title'>{esc(title)}</div>"
                + (f"<div class='section-sub'>{esc(subtitle)}</div>" if subtitle else "<div style='height:6px'></div>"),
                unsafe_allow_html=True)


def tile(label, value, sub="", tone="", meter=None, meter_color=charts.SERIES[0]):
    meter_html = ""
    if meter is not None:
        pct = max(0.0, min(1.0, meter)) * 100
        meter_html = f"<div class='meter'><span style='width:{pct:.1f}%;background:{meter_color}'></span></div>"
    st.markdown(
        f"<div class='tile'><div class='tile-label'>{esc(label)}</div>"
        f"<div class='tile-value {('tone-' + tone) if tone else ''}'>{esc(value)}</div>"
        f"{meter_html}<div class='tile-sub'>{sub}</div></div>",
        unsafe_allow_html=True,
    )


def chip(text, tone=""):
    return f"<span class='chip {('chip-' + tone) if tone else ''}'>{esc(text)}</span>"


def empty_state(title, body=""):
    st.markdown(f"<div class='empty'><b>{esc(title)}</b>{esc(body)}</div>", unsafe_allow_html=True)


@st.cache_resource(max_entries=256, show_spinner=False)
def _figure(builder, dark, day, *args, **kwargs):
    """Build a chart once per distinct input. Plotly validates every property it is given,
    which makes building a figure cost far more than drawing it, so reruns that show the
    same numbers (switching pages, toggling a control) reuse the finished figure.
    `day` is part of the key because some charts mark today or the current month."""
    fig = getattr(charts, builder)(*args, **kwargs)
    return charts.to_dark(fig) if dark else fig


def plot(builder, *args, **kwargs):
    """Draw charts.<builder>(*args, **kwargs) in the active theme."""
    st.plotly_chart(_figure(builder, DARK, date.today(), *args, **kwargs), width="stretch",
                    config=charts.PLOTLY_CONFIG)


def fragment(fn):
    """st.fragment: a control inside reruns only this function, not the whole app.

    Streamlit draws a fragment inside a plain container, which the card style above would
    paint white, so each fragment starts with a hidden marker that the CSS uses to skip it.
    """
    @functools.wraps(fn)
    def body(*args, **kwargs):
        st.html("<span class='sb-fragment'></span>")
        return fn(*args, **kwargs)
    return st.fragment(body)


def ensure_choice(key, options, default=None):
    """Drop a stale session value (e.g. a deleted person or circle) before rendering a widget."""
    if key in st.session_state and st.session_state[key] not in options:
        del st.session_state[key]
    if key not in st.session_state and options:
        st.session_state[key] = default if default in options else options[0]


for _msg, _icon in st.session_state.pop("_flash", []):
    st.toast(_msg, icon=_icon)

# ---------------------------------------------------------------------------
# Data shared by every page
# ---------------------------------------------------------------------------
users = db.get_all_users()
user_map = {u["user_id"]: u for u in users}
groups = db.get_all_groups()
group_map = {g["group_id"]: g for g in groups}
today = date.today()
cur_month = today.strftime("%Y-%m")

st.logo(os.path.join(BASE_DIR, "assets", "logo-dark.svg" if DARK else "logo.svg"), icon_image=os.path.join(BASE_DIR, "assets", "mark.svg"), size="large")

# ---------------------------------------------------------------------------
# First run
# ---------------------------------------------------------------------------
if not users:
    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        st.write("")
        page_header("Welcome to Smart Budgeter",
                    "Track your spending against a budget, split bills with friends, and send payment reminders automatically.")
        with st.container(border=True):
            section("Create your profile", "You can add other people later from Settings.")
            with st.form("onboard_user"):
                n = st.text_input("Name", placeholder="e.g. Priya Sharma")
                e = st.text_input("Email", placeholder="priya@example.com")
                b = st.number_input(f"Monthly budget ({CURR})", min_value=0.0, value=40000.0, step=1000.0)
                if st.form_submit_button("Create profile", type="primary", width="stretch"):
                    ok, err, c_em, c_ph = logic.validate_user_data(n, e, None)
                    if not ok:
                        st.error(err)
                    else:
                        db.create_user(n.strip(), c_em, c_ph, float(b))
                        st.rerun()
        st.markdown("<div class='muted' style='text-align:center;margin:12px 0 8px'>or</div>", unsafe_allow_html=True)
        if st.button("Explore with sample data", width="stretch"):
            db.seed_comprehensive_demo_data(reset=True)
            st.rerun()
    theme_toggle()
    st.stop()

# ---------------------------------------------------------------------------
# Sidebar: active profile
# ---------------------------------------------------------------------------
user_ids = [u["user_id"] for u in users]
_profile_cookie = st.context.cookies.get(PROFILE_COOKIE, "")
ensure_choice("active_user_id", user_ids, int(_profile_cookie) if _profile_cookie.isdigit() else None)
with st.sidebar:
    st.selectbox("Viewing as", user_ids, format_func=lambda i: user_map[i]["name"], key="active_user_id")

ACTIVE_ID = st.session_state["active_user_id"]
ACTIVE = user_map[ACTIVE_ID]
FIRST_NAME = ACTIVE["name"].split()[0]


# ---------------------------------------------------------------------------
# Dialogs
# ---------------------------------------------------------------------------
@st.dialog("Record a payment")
def record_payment_dialog(from_uid, to_uid, amount, group_id, note=""):
    f_name = user_map.get(from_uid, {}).get("name", "Unknown")
    t_name = user_map.get(to_uid, {}).get("name", "Unknown")
    g_name = group_map.get(group_id, {}).get("group_name", "No circle")
    st.markdown(
        f"<div class='row' style='border:1px solid var(--line);border-radius:8px;padding:12px 14px;margin-bottom:12px'>"
        f"<div><div class='row-main'>{esc(f_name)} &rarr; {esc(t_name)}</div><div class='row-meta'>{esc(g_name)}</div></div>"
        f"<div class='row-amt'>{fmt(amount)}</div></div>",
        unsafe_allow_html=True,
    )
    with st.form("dlg_payment"):
        c1, c2 = st.columns(2)
        amt = c1.number_input(f"Amount ({CURR})", min_value=0.01, value=float(round(amount, 2)), step=100.0, format="%.2f")
        pay_date = c2.date_input("Date", value=today, max_value=today)
        method = st.selectbox("Method", db.SETTLEMENT_METHODS)
        ref = st.text_input("Note", value=note)
        if st.form_submit_button("Record payment", type="primary", width="stretch"):
            db.add_settlement(from_uid, to_uid, float(amt), group_id, ref.strip(), method,
                              date=f"{pay_date.isoformat()} {datetime.now().strftime('%H:%M:%S')}")
            flash(f"Recorded {fmt(amt)} from {f_name} to {t_name}")
            st.rerun()


@st.dialog("Reminder preview", width="large")
def preview_reminder_dialog(statement):
    s = reminders.get_settings()
    creds = reminders.get_smtp_credentials(s)
    st.markdown(
        f"<div class='muted'>To <b style='color:var(--ink)'>{esc(statement['email'] or 'no email on file')}</b></div>"
        f"<div class='muted' style='margin-bottom:10px'>Subject <b style='color:var(--ink)'>{esc(reminders.build_subject(statement, CURR))}</b></div>",
        unsafe_allow_html=True,
    )
    st.html(reminders.build_statement_html(statement, CURR, creds["sender_name"]))


# ---------------------------------------------------------------------------
# Page: Overview
# ---------------------------------------------------------------------------
def page_overview():
    hour = datetime.now().hour
    greeting = "Good morning" if hour < 12 else ("Good afternoon" if hour < 18 else "Good evening")
    page_header(f"{greeting}, {FIRST_NAME}", f"Your finances for {month_label(cur_month)}.")

    bs = logic.get_budget_status(ACTIVE_ID, cur_month)
    cf = logic.get_cash_flow_summary(ACTIVE_ID, cur_month)
    shared_net = logic.compute_balances(None).get(ACTIVE_ID, 0.0)
    my_groups = db.get_user_groups(ACTIVE_ID)

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        if bs["budget"] > 0:
            over = bs["spent"] > bs["budget"]
            tile("Spent this month", fmt(bs["spent"]),
                 f"{bs['pct_used']:.0f}% of {fmt(bs['budget'], 0)} budget",
                 meter=bs["spent"] / bs["budget"], meter_color=charts.CRITICAL if over else charts.SERIES[0])
        else:
            tile("Spent this month", fmt(bs["spent"]), "No monthly budget set")
    with k2:
        tile("Net cash flow", fmt_signed(cf["net_cashflow"]),
             f"Income {fmt(cf['total_income'], 0)} &middot; {cf['savings_rate']:.0f}% saved",
             tone="pos" if cf["net_cashflow"] > 0 else ("neg" if cf["net_cashflow"] < 0 else ""))
    with k3:
        if bs["budget"] > 0:
            if bs["is_over_budget"]:
                sub, tone = f"Over budget by {fmt(-bs['remaining'], 0)}", "neg"
            elif bs["is_pacing_fast"]:
                sub, tone = f"{bs['days_remaining']} days left &middot; on pace for {fmt(bs['projected_spend'], 0)}", "warn"
            else:
                sub, tone = f"{bs['days_remaining']} days left &middot; on track", ""
            tile("Daily allowance", fmt(bs["safe_daily_spend"]), sub, tone=tone if tone == "neg" else "")
        else:
            tile("Daily allowance", "—", "Set a monthly budget to see this")
    with k4:
        if shared_net > 0.01:
            tile("Shared balance", fmt(shared_net), f"You're owed &middot; {len(my_groups)} circle(s)", tone="pos")
        elif shared_net < -0.01:
            tile("Shared balance", fmt(-shared_net), f"You owe &middot; {len(my_groups)} circle(s)", tone="neg")
        else:
            tile("Shared balance", fmt(0), f"All settled &middot; {len(my_groups)} circle(s)")

    cat_status = logic.get_category_budget_status(ACTIVE_ID, cur_month)
    over_cats = [c for c in cat_status if c["has_budget"] and c["spent"] > c["budget"]]
    if over_cats:
        names = ", ".join(f"{c['category']} (by {fmt(c['spent'] - c['budget'], 0)})" for c in over_cats)
        st.warning(f"Over the limit this month: {names}", icon=":material/error:")

    st.write("")
    left, right = st.columns([3, 2], gap="medium")
    with left:
        with st.container(border=True):
            section("Spending this month", "Cumulative spending against an even pace to your monthly budget.")
            daily = db.get_daily_spending(ACTIVE_ID, cur_month)
            if daily:
                plot("spending_pace", daily, cur_month, bs["budget"], CURR, bs["projected_spend"])
            else:
                empty_state("No spending yet this month", "")
    with right:
        with st.container(border=True):
            section("By category", "Bars show spending; ticks mark your limits.")
            if any(c["spent"] > 0 for c in cat_status):
                plot("category_vs_budget", cat_status, CURR, max_rows=7)
            else:
                empty_state("Nothing to show yet", "")
            st.page_link(PAGE_BUDGETS, label="Manage budgets", icon=":material/arrow_forward:")

    left, right = st.columns([3, 2], gap="medium")
    with left:
        with st.container(border=True):
            section("Recent activity")
            exp = db.get_expenses_filtered(user_id=ACTIVE_ID, limit=8)
            inc = db.get_incomes_filtered(user_id=ACTIVE_ID, limit=8)
            rows = [{"Date": e["date"], "Description": e["description"] or e["category"], "Category": e["category"],
                     "Amount": -e["amount"]} for e in exp]
            rows += [{"Date": i["date"], "Description": i["description"] or i["source"], "Category": i["source"],
                      "Amount": i["amount"]} for i in inc]
            rows = sorted(rows, key=lambda r: r["Date"], reverse=True)[:8]
            if rows:
                df = pd.DataFrame(rows)
                df["Date"] = pd.to_datetime(df["Date"])
                df["Amount"] = df["Amount"].map(fmt_signed)
                st.dataframe(df, hide_index=True, width="stretch", column_config={
                    "Date": st.column_config.DateColumn("Date", format="DD MMM"),
                    "Amount": st.column_config.TextColumn("Amount", alignment="right"),
                })
            else:
                empty_state("No transactions yet", "")
            st.page_link(PAGE_TRANSACTIONS, label="All transactions", icon=":material/arrow_forward:")
    with right:
        with st.container(border=True):
            section("Shared balances", "Suggested payments involving you.")
            plan = [t for t in logic.get_settlement_plan(None) if ACTIVE_ID in (t["from_user"], t["to_user"])]
            if not plan:
                empty_state("You're all settled up", "")
            for i, t in enumerate(plan):
                you_pay = t["from_user"] == ACTIVE_ID
                c1, c2 = st.columns([3, 1], vertical_alignment="center")
                with c1:
                    who = f"You owe {esc(t['to_name'])}" if you_pay else f"{esc(t['from_name'])} owes you"
                    st.markdown(f"<div class='row-main'>{who} <span class='{'tone-neg' if you_pay else 'tone-pos'}' style='font-weight:600'>{fmt(t['amount'])}</span></div>"
                                f"<div class='row-meta'>{esc(t['group_name'])}</div>", unsafe_allow_html=True)
                with c2:
                    if st.button("Settle", key=f"ov_settle_{i}", width="stretch"):
                        record_payment_dialog(t["from_user"], t["to_user"], t["amount"], t["group_id"],
                                              f"{t['group_name']} settle-up")
            st.page_link(PAGE_SETTLE, label="Settle up", icon=":material/arrow_forward:")


# ---------------------------------------------------------------------------
# Page: Transactions
# ---------------------------------------------------------------------------
PERIODS = {
    "This month": lambda: (today.replace(day=1), today),
    "Last 30 days": lambda: (today - timedelta(days=29), today),
    "Last 3 months": lambda: (db.month_start(today, 2), today),
    "This year": lambda: (date(today.year, 1, 1), today),
    "All time": lambda: (None, None),
}


def page_transactions():
    page_header("Transactions", f"Record and review spending and income for {ACTIVE['name']}.")
    _add_transaction()
    st.write("")
    _ledger()


# The add form and the history list are fragments: switching Expense/Income, filtering or
# selecting a row reruns only that part. Saving still reruns the whole app (st.rerun()).
@fragment
def _add_transaction():
    with st.container(border=True):
        kind = st.segmented_control("Add", ["Expense", "Income"], default="Expense", key="add_kind") or "Expense"
        if kind == "Expense":
            with st.form("add_expense", clear_on_submit=True):
                c1, c2, c3 = st.columns(3)
                amt = c1.number_input(f"Amount ({CURR})", min_value=0.01, value=None, step=100.0, format="%.2f",
                                      placeholder="0.00")
                cat = c2.selectbox("Category", db.EXPENSE_CATEGORIES)
                d = c3.date_input("Date", value=today, max_value=today)
                c4, c5, c6 = st.columns(3)
                desc = c4.text_input("Description", placeholder="e.g. Groceries at Nature's Basket")
                method = c5.selectbox("Paid with", db.PAYMENT_METHODS)
                notes = c6.text_input("Notes", placeholder="Optional")
                if st.form_submit_button("Add expense", type="primary"):
                    if not amt:
                        st.error("Enter an amount.")
                    else:
                        db.add_expense(ACTIVE_ID, float(amt), cat, d.isoformat(), desc.strip() or cat, method, notes.strip())
                        flash(f"Added expense of {fmt(amt)}")
                        st.rerun()
        else:
            with st.form("add_income", clear_on_submit=True):
                c1, c2, c3 = st.columns(3)
                amt = c1.number_input(f"Amount ({CURR})", min_value=0.01, value=None, step=1000.0, format="%.2f",
                                      placeholder="0.00")
                src = c2.selectbox("Source", db.INCOME_SOURCES)
                d = c3.date_input("Date", value=today, max_value=today)
                desc = st.text_input("Description", placeholder="e.g. October salary")
                if st.form_submit_button("Add income", type="primary"):
                    if not amt:
                        st.error("Enter an amount.")
                    else:
                        db.add_income(ACTIVE_ID, float(amt), src, d.isoformat(), desc.strip() or src)
                        flash(f"Added income of {fmt(amt)}")
                        st.rerun()


@fragment
def _ledger():
    section("History")
    f1, f2, f3, f4 = st.columns([1.1, 2, 1.4, 1.3])
    view = f1.segmented_control("Show", ["Expenses", "Income"], default="Expenses", key="ledger_view") or "Expenses"
    search = f2.text_input("Search", placeholder="Description or notes", key="ledger_search")
    if view == "Expenses":
        cat = f3.selectbox("Category", ["All categories"] + db.get_distinct_categories(ACTIVE_ID), key="ledger_cat")
    else:
        cat = None
        f3.empty()
    period = f4.selectbox("Period", list(PERIODS), index=4, key="ledger_period")
    start, end = PERIODS[period]()
    s_iso = start.isoformat() if start else None
    e_iso = end.isoformat() if end else None

    if view == "Expenses":
        rows = db.get_expenses_filtered(user_id=ACTIVE_ID, category=None if cat == "All categories" else cat,
                                        start_date=s_iso, end_date=e_iso, search=search.strip() or None)
        id_key = "exp_id"
        cols = ["date", "description", "category", "payment_method", "notes", "amount"]
        names = {"date": "Date", "description": "Description", "category": "Category",
                 "payment_method": "Paid with", "notes": "Notes", "amount": "Amount"}
    else:
        rows = db.get_incomes_filtered(user_id=ACTIVE_ID, start_date=s_iso, end_date=e_iso, search=search.strip() or None)
        id_key = "income_id"
        cols = ["date", "description", "source", "amount"]
        names = {"date": "Date", "description": "Description", "source": "Source", "amount": "Amount"}

    if not rows:
        with st.container(border=True):
            empty_state("No matching transactions", "Try a different period or search.")
        return

    df = pd.DataFrame(rows)
    show = df[cols].rename(columns=names)
    show["Date"] = pd.to_datetime(show["Date"])
    total = df["amount"].sum()
    st.markdown(f"<div class='muted' style='margin:2px 0 6px'>{len(df)} {'transactions' if len(df) != 1 else 'transaction'} &middot; total <b style='color:var(--ink)'>{fmt(total)}</b> &middot; select a row to edit it</div>",
                unsafe_allow_html=True)
    event = st.dataframe(
        show, hide_index=True, width="stretch", height=min(420, 38 + 35 * len(show)),
        on_select="rerun", selection_mode="single-row", key=f"ledger_{view}",
        column_config={"Date": st.column_config.DateColumn("Date", format="DD MMM YYYY"), "Amount": money_col("Amount")},
    )
    c_dl, _ = st.columns([1, 4])
    c_dl.download_button("Download CSV", data=df.to_csv(index=False).encode("utf-8"),
                         file_name=f"{view.lower()}_{period.lower().replace(' ', '_')}.csv", mime="text/csv",
                         icon=":material/download:", on_click="ignore")

    sel = event.selection.rows if event and event.selection else []
    if not sel:
        return
    rec = rows[sel[0]]
    rid = rec[id_key]
    with st.container(border=True):
        section(f"Edit {'expense' if view == 'Expenses' else 'income'}", f"{nice_date(rec['date'])} · {rec['description'] or ''}")
        with st.form(f"edit_{id_key}_{rid}"):
            c1, c2, c3 = st.columns(3)
            amt = c1.number_input(f"Amount ({CURR})", min_value=0.01, value=float(rec["amount"]), step=100.0, format="%.2f")
            d = c3.date_input("Date", value=date.fromisoformat(rec["date"][:10]))
            if view == "Expenses":
                cats = db.EXPENSE_CATEGORIES if rec["category"] in db.EXPENSE_CATEGORIES else db.EXPENSE_CATEGORIES + [rec["category"]]
                cat_v = c2.selectbox("Category", cats, index=cats.index(rec["category"]))
                c4, c5, c6 = st.columns(3)
                desc = c4.text_input("Description", value=rec["description"] or "")
                methods = db.PAYMENT_METHODS if rec["payment_method"] in db.PAYMENT_METHODS else db.PAYMENT_METHODS + [rec["payment_method"] or "Other"]
                meth = c5.selectbox("Paid with", methods, index=methods.index(rec["payment_method"] or "Other"))
                notes = c6.text_input("Notes", value=rec["notes"] or "")
            else:
                srcs = db.INCOME_SOURCES if rec["source"] in db.INCOME_SOURCES else db.INCOME_SOURCES + [rec["source"]]
                src_v = c2.selectbox("Source", srcs, index=srcs.index(rec["source"]))
                desc = st.text_input("Description", value=rec["description"] or "")
            b1, b2, _ = st.columns([1, 1, 3])
            save = b1.form_submit_button("Save changes", type="primary", width="stretch")
            delete = b2.form_submit_button("Delete", width="stretch")
            confirm = st.checkbox("Yes, delete this record", key=f"confirm_del_{id_key}_{rid}")
        if save:
            if view == "Expenses":
                db.update_expense(rid, amount=float(amt), category=cat_v, description=desc.strip(), date=d.isoformat(),
                                  payment_method=meth, notes=notes.strip())
            else:
                db.update_income(rid, amount=float(amt), source=src_v, description=desc.strip(), date=d.isoformat())
            flash("Changes saved")
            st.rerun()
        if delete:
            if not confirm:
                st.warning("Tick the confirmation box to delete this record.")
            else:
                (db.delete_expense if view == "Expenses" else db.delete_income)(rid)
                flash("Record deleted", ":material/delete:")
                st.rerun()


# ---------------------------------------------------------------------------
# Page: Budgets
# ---------------------------------------------------------------------------
def page_budgets():
    page_header("Budgets", "A monthly budget plus optional limits per category.")

    months = sorted({m["month"] for m in db.get_monthly_spending(ACTIVE_ID)} | {cur_month}, reverse=True)[:12]
    c_m, _ = st.columns([1, 3])
    month = c_m.selectbox("Month", months, format_func=month_label, key="budget_month")
    is_current = month == cur_month

    bs = logic.get_budget_status(ACTIVE_ID, month)
    cat_status = logic.get_category_budget_status(ACTIVE_ID, month)

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        tile("Monthly budget", fmt(bs["budget"]) if bs["budget"] else "Not set",
             f"{len([c for c in cat_status if c['has_budget']])} category limits")
    with k2:
        tile("Spent", fmt(bs["spent"]), f"{bs['pct_used']:.0f}% of budget" if bs["budget"] else "",
             meter=(bs["spent"] / bs["budget"]) if bs["budget"] else None,
             meter_color=charts.CRITICAL if bs["is_over_budget"] else charts.SERIES[0])
    with k3:
        if bs["budget"]:
            tile("Over budget" if bs["is_over_budget"] else "Remaining", fmt(abs(bs["remaining"])),
                 f"{fmt(bs['safe_daily_spend'])} a day for {bs['days_remaining']} days" if is_current and not bs["is_over_budget"] else "",
                 tone="neg" if bs["is_over_budget"] else "")
        else:
            tile("Remaining", "—", "Set a monthly budget")
    with k4:
        if is_current:
            proj_tone = "neg" if bs["budget"] and bs["projected_spend"] > bs["budget"] else ""
            tile("Projected month-end", fmt(bs["projected_spend"]),
                 "Rent counted once; day-to-day spending extrapolated", tone=proj_tone)
        else:
            tile("Month closed", fmt(bs["spent"]), "Final spending for the month")

    st.write("")
    left, right = st.columns([3, 2], gap="medium")
    with left:
        with st.container(border=True):
            section("Spending by category", f"{month_label(month)}. Bars turn red once a category passes its limit.")
            if cat_status:
                plot("category_vs_budget", cat_status, CURR, max_rows=12)
            else:
                empty_state("No spending recorded for this month", "")
    with right:
        with st.container(border=True):
            section("Monthly budget")
            with st.form("form_monthly_budget"):
                nb = st.number_input(f"Amount ({CURR})", min_value=0.0, value=float(ACTIVE.get("monthly_budget") or 0),
                                     step=1000.0, format="%.2f")
                if st.form_submit_button("Save budget", width="stretch"):
                    db.update_user(ACTIVE_ID, monthly_budget=float(nb))
                    flash("Monthly budget updated")
                    st.rerun()
        with st.container(border=True):
            section("Category limit", "Set or change the monthly limit for a category.")
            existing = {c["category"]: c["budget"] for c in cat_status if c["has_budget"]}
            with st.form("form_cat_limit"):
                cat = st.selectbox("Category", db.EXPENSE_CATEGORIES)
                lim = st.number_input(f"Monthly limit ({CURR})", min_value=0.0, value=5000.0, step=500.0, format="%.2f")
                if st.form_submit_button("Save limit", width="stretch"):
                    if lim <= 0:
                        db.delete_category_budget(ACTIVE_ID, cat)
                        flash(f"Removed the limit for {cat}")
                    else:
                        db.set_category_budget(ACTIVE_ID, cat, float(lim))
                        flash(f"Limit for {cat} set to {fmt(lim)}")
                    st.rerun()
            if existing:
                rc1, rc2 = st.columns([2, 1], vertical_alignment="bottom")
                rm = rc1.selectbox("Remove a limit", list(existing), key="rm_limit")
                if rc2.button("Remove", width="stretch"):
                    db.delete_category_budget(ACTIVE_ID, rm)
                    flash(f"Removed the limit for {rm}", ":material/delete:")
                    st.rerun()

    if cat_status:
        with st.container(border=True):
            section("Category detail")
            df = pd.DataFrame(cat_status)
            df["limit"] = df["budget"].where(df["has_budget"])
            df["used"] = df["pct_used"]
            st.dataframe(
                df[["category", "spent", "limit", "remaining", "used"]], hide_index=True, width="stretch",
                column_config={
                    "category": "Category", "spent": money_col("Spent"), "limit": money_col("Limit"),
                    "remaining": money_col("Remaining"),
                    "used": st.column_config.ProgressColumn("Used", min_value=0, max_value=100, format="%.0f%%"),
                },
            )


# ---------------------------------------------------------------------------
# Page: Reports
# ---------------------------------------------------------------------------
def page_reports():
    page_header("Reports", "How your income, spending and savings have moved over time.")

    rng = st.segmented_control("Range", ["6 months", "12 months", "All time"], default="6 months", key="report_range") or "6 months"
    spend = {r["month"]: r["total"] for r in db.get_monthly_spending(ACTIVE_ID)}
    income = {r["month"]: r["total"] for r in db.get_monthly_income(ACTIVE_ID)}
    all_months = sorted(set(spend) | set(income) | {cur_month})
    first = all_months[0]
    if rng != "All time":
        n = 6 if rng == "6 months" else 12
        first = max(first, db.month_start(today, n - 1).strftime("%Y-%m"))
    # Continuous month index so gaps show as zero instead of disappearing
    months, d = [], date.fromisoformat(first + "-01")
    while d.strftime("%Y-%m") <= cur_month:
        months.append(d.strftime("%Y-%m"))
        d = db.month_start(d, -1)
    merged = pd.DataFrame({"month": months,
                           "Income": [income.get(m, 0.0) for m in months],
                           "Expenses": [spend.get(m, 0.0) for m in months]})

    if not (merged["Income"].sum() or merged["Expenses"].sum()):
        with st.container(border=True):
            empty_state("No data yet", "Reports appear once you've recorded some transactions.")
        return

    # Averages exclude the current, unfinished month
    closed = merged[merged["month"] < cur_month]
    basis = closed if len(closed) else merged
    avg_inc, avg_exp = basis["Income"].mean(), basis["Expenses"].mean()
    avg_rate = ((basis["Income"] - basis["Expenses"]).sum() / basis["Income"].sum() * 100) if basis["Income"].sum() else 0
    # Like-for-like: this month so far vs the same days of last month
    prev_m = db.month_start(today, 1).strftime("%Y-%m")
    this_so_far = sum(r["total"] for r in db.get_daily_spending(ACTIVE_ID, cur_month))
    prev_same = sum(r["total"] for r in db.get_daily_spending(ACTIVE_ID, prev_m) if int(r["date"][8:10]) <= today.day)

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        tile("Average monthly income", fmt(avg_inc, 0), f"Over {len(basis)} completed month(s)")
    with k2:
        tile("Average monthly spending", fmt(avg_exp, 0), f"Over {len(basis)} completed month(s)")
    with k3:
        tile("Savings rate", f"{avg_rate:.0f}%", "Share of income kept", tone="pos" if avg_rate > 0 else ("neg" if avg_rate < 0 else ""))
    with k4:
        diff = this_so_far - prev_same
        pct = f" ({diff / prev_same * 100:+.0f}%)" if prev_same else ""
        prev_abbr = datetime.strptime(prev_m, "%Y-%m").strftime("%b")
        tile("Spending vs last month", fmt_signed(diff, 0) + pct,
             f"{today:%b} 1–{today.day} vs {prev_abbr} 1–{today.day}",
             tone="neg" if diff > 0 else ("pos" if diff < 0 else ""))

    st.write("")
    left, right = st.columns(2, gap="medium")
    with left:
        with st.container(border=True):
            section("Income and spending", "Monthly totals.")
            plot("income_vs_expenses", merged, CURR)
    with right:
        with st.container(border=True):
            section("Net savings", "Income minus spending each month.")
            plot("net_savings", merged, CURR)

    with st.container(border=True):
        section("Spending mix", "Your five largest categories; everything else is grouped as Other.")
        cat_rows = [r for r in db.get_monthly_category_spending(ACTIVE_ID) if r["month"] >= months[0]]
        if cat_rows:
            plot("category_trend", cat_rows, CURR)
        with st.expander("Table view"):
            table = merged.copy()
            table["Net"] = table["Income"] - table["Expenses"]
            table["month"] = table["month"].map(month_label)
            st.dataframe(table.rename(columns={"month": "Month"}), hide_index=True, width="stretch",
                         column_config={c: money_col(c) for c in ["Income", "Expenses", "Net"]})
            if cat_rows:
                pivot = pd.DataFrame(cat_rows).pivot_table(index="category", columns="month", values="total",
                                                           aggfunc="sum", fill_value=0)
                pivot.columns = [datetime.strptime(c, "%Y-%m").strftime("%b %y") for c in pivot.columns]
                st.dataframe(pivot, width="stretch",
                             column_config={c: money_col(c) for c in pivot.columns})


# ---------------------------------------------------------------------------
# Page: Circles
# ---------------------------------------------------------------------------
def _new_circle_form(key):
    with st.form(key, clear_on_submit=True):
        name = st.text_input("Circle name", placeholder="e.g. Flat 302, Ladakh trip")
        include_me = st.checkbox(f"Add {FIRST_NAME} as a member", value=True)
        if st.form_submit_button("Create circle", type="primary", width="stretch"):
            try:
                gid = db.create_group(name)
                if include_me:
                    db.add_member_to_group(gid, ACTIVE_ID)
                st.session_state["circle_id"] = gid
                flash(f"Created {name.strip()}")
                st.rerun()
            except ValueError as e:
                st.error(str(e))


def page_circles():
    page_header("Circles", "Shared expenses with flatmates, friends and trips.")
    if not groups:
        with st.container(border=True):
            empty_state("No circles yet", "Create a circle to start splitting bills.")
            _, mid, _ = st.columns([1, 2, 1])
            with mid:
                _new_circle_form("first_circle")
        return

    gids = [g["group_id"] for g in groups]
    mine = [g["group_id"] for g in db.get_user_groups(ACTIVE_ID)]
    ensure_choice("circle_id", gids, default=mine[0] if mine else None)
    c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
    gid = c1.selectbox("Circle", gids, format_func=lambda i: group_map[i]["group_name"], key="circle_id")
    with c2:
        with st.popover("New circle", icon=":material/add:", width="stretch"):
            _new_circle_form("new_circle")

    members = db.get_group_members(gid)
    member_ids = [m["user_id"] for m in members]
    bills = db.get_group_shared_expenses(gid)
    balances = logic.compute_balances(gid)
    open_items = logic.get_unpaid_splits(gid)
    my_bal = balances.get(ACTIVE_ID, 0.0)

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        tile("Total spent", fmt(sum(b["amount"] for b in bills)), f"{len(bills)} bill(s)")
    with k2:
        tile("Members", str(len(members)), ", ".join(esc(m["name"].split()[0]) for m in members[:4])
             + ("…" if len(members) > 4 else ""))
    with k3:
        if ACTIVE_ID not in member_ids:
            tile("Your balance", "—", f"{esc(FIRST_NAME)} isn't a member")
        elif my_bal > 0.01:
            tile("Your balance", fmt(my_bal), "You're owed", tone="pos")
        elif my_bal < -0.01:
            tile("Your balance", fmt(-my_bal), "You owe", tone="neg")
        else:
            tile("Your balance", fmt(0), "Settled up")
    with k4:
        tile("Open items", str(len(open_items)), f"{fmt(sum(s['amount_owed'] for s in open_items))} in unpaid shares")

    st.write("")
    t_bills, t_add, t_members = st.tabs(["Bills", "Add a bill", "Members & settings"])

    with t_bills:
        _bill_list(gid, bills)

    with t_add:
        if not members:
            with st.container(border=True):
                empty_state("This circle has no members", "Add members in the “Members & settings” tab first.")
        else:
            _bill_builder(gid, members)

    with t_members:
        _circle_settings(gid, members, balances)


@fragment
def _bill_list(gid, bills):
    if not bills:
        with st.container(border=True):
            empty_state("No bills yet", "Add the first bill in the “Add a bill” tab.")
    show_all = len(bills) <= 15 or st.toggle(f"Show all {len(bills)} bills", key=f"all_bills_{gid}")
    splits_by_bill = {}
    for s in db.get_all_splits_for_group(gid):
        splits_by_bill.setdefault(s["shared_id"], []).append(s)
    for b in (bills if show_all else bills[:15]):
        splits = sorted(splits_by_bill.get(b["shared_id"], []), key=lambda s: s["debtor_name"])
        owing = [s for s in splits if s["user_id"] != b["payer_id"]]
        paid_n = sum(1 for s in owing if s["is_paid"])
        with st.container(border=True):
            h1, h2 = st.columns([4, 1], vertical_alignment="center")
            with h1:
                status = chip("Settled", "pos") if owing and paid_n == len(owing) else chip(f"{paid_n}/{len(owing)} paid")
                st.markdown(f"<div class='row-main'>{esc(b['description'])} &nbsp;{status}</div>"
                            f"<div class='row-meta'>{nice_date(b['date'])} &middot; paid by {esc(b['payer_name'])} &middot; {esc(b.get('category') or 'General')}</div>",
                            unsafe_allow_html=True)
            with h2:
                st.markdown(f"<div class='row-amt' style='text-align:right;font-size:1rem'>{fmt(b['amount'])}</div>",
                            unsafe_allow_html=True)
            with st.expander("Split details"):
                for s in splits:
                    r1, r2, r3 = st.columns([3, 1.2, 1.2], vertical_alignment="center")
                    r1.markdown(f"<div class='row-main' style='font-weight:400'>{esc(s['debtor_name'])}</div>", unsafe_allow_html=True)
                    r2.markdown(f"<div class='row-amt'>{fmt(s['amount_owed'])}</div>", unsafe_allow_html=True)
                    with r3:
                        if s["user_id"] == b["payer_id"]:
                            st.markdown(chip("Paid the bill", "blue"), unsafe_allow_html=True)
                        elif s["is_paid"]:
                            if st.button("Mark unpaid", key=f"unpaid_{s['split_id']}", type="tertiary"):
                                db.mark_split_paid(s["split_id"], False)
                                st.rerun()
                        else:
                            if st.button("Mark paid", key=f"paid_{s['split_id']}"):
                                db.mark_split_paid(s["split_id"], True)
                                flash(f"{s['debtor_name']}'s share marked as paid")
                                st.rerun()
                st.caption("Mark a share as paid when it was paid back directly for this bill. "
                           "For lump-sum payments use Settle up instead (don't do both for the same money).")
                with st.popover("Delete bill", icon=":material/delete:"):
                    st.write(f"Delete **{b['description']}** and all its splits?")
                    if st.button("Delete", type="primary", key=f"del_bill_{b['shared_id']}"):
                        db.delete_shared_expense(b["shared_id"])
                        flash("Bill deleted", ":material/delete:")
                        st.rerun()


@fragment
def _bill_builder(gid, members):
    name = {m["user_id"]: m["name"] for m in members}
    ids = list(name)
    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        desc = c1.text_input("Description", placeholder="e.g. Electricity bill", key=f"bb_desc_{gid}")
        total = c2.number_input(f"Total ({CURR})", min_value=0.0, value=None, step=100.0, format="%.2f",
                                placeholder="0.00", key=f"bb_total_{gid}")
        d = c3.date_input("Date", value=today, max_value=today, key=f"bb_date_{gid}")
        c4, c5 = st.columns(2)
        payer = c4.selectbox("Paid by", ids, format_func=name.get,
                             index=ids.index(ACTIVE_ID) if ACTIVE_ID in ids else 0, key=f"bb_payer_{gid}")
        category = c5.selectbox("Category", db.SHARED_CATEGORIES, key=f"bb_cat_{gid}")
        parts = st.multiselect("Split between", ids, default=ids, format_func=name.get, key=f"bb_parts_{gid}")
        mode = st.segmented_control("Split", ["Equally", "Exact amounts", "Percentages", "Shares"],
                                    default="Equally", key=f"bb_mode_{gid}") or "Equally"
        total = float(total or 0)

        splits, problem = None, None
        if not parts:
            problem = "Choose at least one person to split with."
        elif total <= 0:
            problem = "Enter the bill total."
        if parts:
            cols = st.columns(min(4, len(parts)))
            if mode == "Equally":
                if total > 0:
                    splits = dict(zip(parts, db.allocate_amounts(total, [1] * len(parts))))
                    st.markdown(f"<div class='muted'>{fmt(total / len(parts))} each</div>", unsafe_allow_html=True)
            elif mode == "Exact amounts":
                vals = {}
                for i, uid in enumerate(parts):
                    vals[uid] = cols[i % len(cols)].number_input(name[uid], min_value=0.0, value=0.0, step=50.0,
                                                                 format="%.2f", key=f"bb_ex_{gid}_{uid}")
                left = round(total - sum(vals.values()), 2)
                if abs(left) > 0.009:
                    problem = problem or (f"{fmt(left)} left to assign." if left > 0 else f"Assigned {fmt(-left)} more than the total.")
                else:
                    splits = vals
            elif mode == "Percentages":
                vals = {}
                default = round(100 / len(parts), 2)
                for i, uid in enumerate(parts):
                    vals[uid] = cols[i % len(cols)].number_input(f"{name[uid]} (%)", min_value=0.0, max_value=100.0,
                                                                 value=default, step=5.0, key=f"bb_pct_{gid}_{uid}_{len(parts)}")
                pct_total = round(sum(vals.values()), 2)
                if abs(pct_total - 100) > 0.05:
                    problem = problem or f"Percentages add up to {pct_total:g}%, not 100%."
                elif total > 0:
                    splits = dict(zip(vals, db.allocate_amounts(total, list(vals.values()))))
            else:
                vals = {}
                for i, uid in enumerate(parts):
                    vals[uid] = cols[i % len(cols)].number_input(f"{name[uid]} (shares)", min_value=0, value=1, step=1,
                                                                 key=f"bb_sh_{gid}_{uid}")
                if sum(vals.values()) <= 0:
                    problem = problem or "At least one person needs a share."
                elif total > 0:
                    splits = dict(zip(vals, db.allocate_amounts(total, list(vals.values()))))

        if splits and mode != "Equally":
            st.markdown("<div class='muted'>" + " &middot; ".join(f"{esc(name[u])} {fmt(v)}" for u, v in splits.items())
                        + "</div>", unsafe_allow_html=True)
        if problem and (total > 0 or not parts):
            st.markdown(f"<div class='muted tone-warn'>{esc(problem)}</div>", unsafe_allow_html=True)

        if st.button("Add bill", type="primary", disabled=bool(problem) or not splits, key=f"bb_submit_{gid}"):
            try:
                db.add_shared_expense(gid, payer, total, desc.strip() or "Shared bill", d.isoformat(),
                                      custom_splits={u: v for u, v in splits.items() if v > 0}, category=category)
                for k in [f"bb_desc_{gid}", f"bb_total_{gid}"]:
                    st.session_state.pop(k, None)
                flash(f"Added {desc.strip() or 'bill'} for {fmt(total)}")
                st.rerun()
            except ValueError as e:
                st.error(str(e))


def _circle_settings(gid, members, balances):
    left, right = st.columns([3, 2], gap="medium")
    with left:
        with st.container(border=True):
            section("Members", "Positive balances are owed money; negative balances owe money.")
            if not members:
                empty_state("No members yet", "")
            for m in members:
                bal = balances.get(m["user_id"], 0.0)
                tone = "pos" if bal > 0.01 else ("neg" if bal < -0.01 else "")
                st.markdown(f"<div class='row'><div><div class='row-main'>{esc(m['name'])}</div>"
                            f"<div class='row-meta'>{esc(m.get('email') or 'No email')}</div></div>"
                            f"<div class='row-amt tone-{tone}'>{fmt_signed(bal) if tone else 'Settled'}</div></div>",
                            unsafe_allow_html=True)
    with right:
        with st.container(border=True):
            section("Add or remove members")
            member_ids = [m["user_id"] for m in members]
            addable = [u["user_id"] for u in users if u["user_id"] not in member_ids]
            if addable:
                a1, a2 = st.columns([2, 1], vertical_alignment="bottom")
                to_add = a1.selectbox("Add", addable, format_func=lambda i: user_map[i]["name"], key=f"add_m_{gid}")
                if a2.button("Add", key=f"add_m_btn_{gid}", width="stretch"):
                    db.add_member_to_group(gid, to_add)
                    flash(f"Added {user_map[to_add]['name']}")
                    st.rerun()
            else:
                st.markdown("<div class='muted'>Everyone is already a member. Add new people in Settings.</div>",
                            unsafe_allow_html=True)
            if members:
                r1, r2 = st.columns([2, 1], vertical_alignment="bottom")
                to_rm = r1.selectbox("Remove", member_ids, format_func=lambda i: user_map[i]["name"], key=f"rm_m_{gid}")
                if r2.button("Remove", key=f"rm_m_btn_{gid}", width="stretch"):
                    if abs(balances.get(to_rm, 0.0)) > 0.01:
                        st.error(f"{user_map[to_rm]['name']} still has an open balance in this circle. Settle it first.")
                    else:
                        db.remove_member_from_group(gid, to_rm)
                        flash(f"Removed {user_map[to_rm]['name']}", ":material/person_remove:")
                        st.rerun()
        with st.container(border=True):
            section("Circle settings")
            with st.form(f"rename_{gid}"):
                new_name = st.text_input("Name", value=group_map[gid]["group_name"])
                if st.form_submit_button("Rename", width="stretch"):
                    try:
                        db.rename_group(gid, new_name)
                        flash("Circle renamed")
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))
            with st.popover("Delete circle", icon=":material/delete:", width="stretch"):
                st.write("This permanently deletes the circle, its bills and its splits.")
                ok = st.checkbox("I understand", key=f"del_c_ok_{gid}")
                if st.button("Delete circle", type="primary", disabled=not ok, key=f"del_c_{gid}"):
                    db.delete_group(gid)
                    st.session_state.pop("circle_id", None)
                    flash("Circle deleted", ":material/delete:")
                    st.rerun()


# ---------------------------------------------------------------------------
# Page: Settle up
# ---------------------------------------------------------------------------
def page_settle():
    page_header("Settle up", "Who owes whom, the fewest payments that clear it, and payments recorded so far.")

    scope_opts = [0] + [g["group_id"] for g in groups]
    ensure_choice("settle_scope", scope_opts)
    c_s, _ = st.columns([1, 2])
    scope = c_s.selectbox("Circle", scope_opts, format_func=lambda i: "All circles" if i == 0 else group_map[i]["group_name"],
                          key="settle_scope")
    gid = scope or None

    plan = logic.get_settlement_plan(gid)
    bal_details = logic.compute_balances_detailed(gid)
    i_owe = sum(t["amount"] for t in plan if t["from_user"] == ACTIVE_ID)
    owed_me = sum(t["amount"] for t in plan if t["to_user"] == ACTIVE_ID)

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        tile("You owe", fmt(i_owe), f"{sum(1 for t in plan if t['from_user'] == ACTIVE_ID)} payment(s) to make",
             tone="neg" if i_owe else "")
    with k2:
        tile("You're owed", fmt(owed_me), f"{sum(1 for t in plan if t['to_user'] == ACTIVE_ID)} payment(s) to receive",
             tone="pos" if owed_me else "")
    with k3:
        tile("Payments needed", str(len(plan)), "To settle everyone in scope")
    with k4:
        tile("Outstanding", fmt(sum(t["amount"] for t in plan)), "Total still to be paid")

    st.write("")
    left, right = st.columns([3, 2], gap="medium")
    with left:
        with st.container(border=True):
            section("Suggested payments", "Debts are simplified within each circle to the fewest transfers.")
            if not plan:
                empty_state("Everyone is settled up", "")
            for i, t in enumerate(plan):
                mine = ACTIVE_ID in (t["from_user"], t["to_user"])
                c1, c2, c3 = st.columns([3, 1.2, 1.1], vertical_alignment="center")
                c1.markdown(f"<div class='row-main'>{esc(t['from_name'])} &rarr; {esc(t['to_name'])}"
                            f"{' &nbsp;' + chip('You', 'blue') if mine else ''}</div>"
                            f"<div class='row-meta'>{esc(t['group_name'])}</div>", unsafe_allow_html=True)
                c2.markdown(f"<div class='row-amt' style='text-align:right'>{fmt(t['amount'])}</div>", unsafe_allow_html=True)
                if c3.button("Record", key=f"settle_{i}", width="stretch", type="primary" if mine else "secondary"):
                    record_payment_dialog(t["from_user"], t["to_user"], t["amount"], t["group_id"],
                                          f"{t['group_name']} settle-up")
    with right:
        with st.container(border=True):
            section("Net balances", "Blue is owed money, red owes money.")
            if bal_details:
                plot("net_balances", bal_details, CURR)
            else:
                empty_state("No balances yet", "")

    if plan:
        with st.container(border=True):
            section("Payment flow", "Width shows how much each person pays.")
            plot("debt_flow", plan, CURR)

    history = db.get_settlements(gid)
    with st.container(border=True):
        section("Payment history", "Select a row to delete a payment recorded by mistake.")
        if not history:
            empty_state("No payments recorded yet", "")
            return
        df = pd.DataFrame(history)
        show = pd.DataFrame({
            "Date": pd.to_datetime(df["date"].str[:10]), "From": df["from_name"], "To": df["to_name"],
            "Amount": df["amount"], "Method": df["payment_method"], "Circle": df["group_name"].fillna("—"),
            "Note": df["note"].fillna(""),
        })
        ev = st.dataframe(show, hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row",
                          key=f"settle_hist_{scope}", height=min(360, 38 + 35 * len(show)),
                          column_config={"Date": st.column_config.DateColumn(format="DD MMM YYYY"), "Amount": money_col("Amount")})
        sel = ev.selection.rows if ev and ev.selection else []
        if sel:
            rec = history[sel[0]]
            d1, d2 = st.columns([3, 1], vertical_alignment="center")
            d1.markdown(f"<div class='muted'>Selected: {esc(rec['from_name'])} &rarr; {esc(rec['to_name'])}, {fmt(rec['amount'])} on {nice_date(rec['date'])}</div>",
                        unsafe_allow_html=True)
            if d2.button("Delete payment", key=f"del_settle_{rec['settlement_id']}", width="stretch"):
                db.delete_settlement(rec["settlement_id"])
                flash("Payment deleted", ":material/delete:")
                st.rerun()


# ---------------------------------------------------------------------------
# Page: Reminders
# ---------------------------------------------------------------------------
STATUS_CHIPS = {
    "due": ("Due", "neg"),
    "cooldown": ("Recently reminded", "blue"),
    "not_overdue": ("Not overdue yet", ""),
    "below_min": ("Below minimum", ""),
    "no_email": ("No email", "warn"),
}


def _when(dt):
    if not dt:
        return "never"
    days = (today - dt.date()).days
    return "today" if days == 0 else ("yesterday" if days == 1 else f"{days} days ago")


def page_reminders():
    page_header("Reminders", "Email people who owe money a clear statement of what they owe and whom to pay.")
    s = reminders.get_settings()
    queue = reminders.get_reminder_queue(None, s)
    due = [q for q in queue if q["status"] == "due"]
    nxt = reminders.next_auto_run(s)
    live = bool(s["live_mode"])
    smtp_ok = reminders.smtp_is_configured(s)

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        if s["auto_enabled"]:
            when = "now" if nxt and nxt <= datetime.now() else (
                f"today {nxt:%H:%M}" if nxt.date() == today else f"{nxt:%a %d %b, %H:%M}")
            tile("Automatic reminders", "On", f"Daily at {int(s['send_hour']):02d}:00 &middot; next run {when}", tone="pos")
        else:
            tile("Automatic reminders", "Off", "Turn on in the Schedule tab")
    with k2:
        tile("Delivery", "Live email" if live else "Dry run",
             ("Emails are sent" if smtp_ok else "Email not configured") if live else "Emails are previewed and logged, not sent",
             tone="neg" if live and not smtp_ok else "")
    with k3:
        tile("Due for a reminder", str(len(due)), f"{fmt(sum(q['total_owed'] for q in due))} outstanding")
    with k4:
        tile("Owing money", str(len(queue)), f"{fmt(sum(q['total_owed'] for q in queue))} across all circles")

    if live and not smtp_ok:
        st.warning("Live delivery is on but email isn't set up. Add SMTP details in the Email delivery tab.",
                   icon=":material/mail_lock:")

    st.write("")
    t_queue, t_sched, t_email, t_hist = st.tabs(["Queue", "Schedule", "Email delivery", "History"])

    with t_queue:
        left, right = st.columns([3, 2], gap="medium")
        with left:
            with st.container(border=True):
                h1, h2 = st.columns([2, 1.3], vertical_alignment="center")
                with h1:
                    section("People who owe money",
                            f"Due once the oldest open item is {int(s['overdue_days'])}+ days old, at most every {int(s['cadence_days'])} days.")
                with h2:
                    label = (f"{'Send' if live else 'Simulate'} {len(due)} due reminder{'s' if len(due) != 1 else ''}"
                             if due else "No reminders due")
                    if st.button(label, type="primary", disabled=not due, width="stretch", key="send_all_due"):
                        res = reminders.run_reminders(trigger="manual", settings=s)
                        st.session_state["last_reminder_run"] = res["results"]
                        flash(res["message"], ":material/send:")
                        st.rerun()
                if not queue:
                    empty_state("Nobody owes anything", "All circles are settled up.")
                for q in queue:
                    label, tone = STATUS_CHIPS[q["status"]]
                    extra = f" until {q['next_eligible']:%d %b}" if q["status"] == "cooldown" and q["next_eligible"] else ""
                    circles = ", ".join(c["group_name"] for c in q["circles"])
                    c1, c2, c3 = st.columns([3, 1.1, 1.6], vertical_alignment="center")
                    c1.markdown(
                        f"<div class='row-main'>{esc(q['name'])} &nbsp;{chip(label + extra, tone)}</div>"
                        f"<div class='row-meta'>{esc(circles)} &middot; oldest item {q['days_outstanding']} days &middot; last reminded {_when(q['last_reminded'])}</div>",
                        unsafe_allow_html=True)
                    c2.markdown(f"<div class='row-amt' style='text-align:right'>{fmt(q['total_owed'])}</div>", unsafe_allow_html=True)
                    with c3:
                        b1, b2 = st.columns(2)
                        if b1.button("Preview", key=f"prev_{q['user_id']}", width="stretch", type="tertiary"):
                            preview_reminder_dialog(q)
                        if b2.button("Send", key=f"send_{q['user_id']}", width="stretch", disabled=not q["email"],
                                     help="Sends now, ignoring the schedule" + ("" if live else " (dry run)")):
                            r = reminders.send_statement_reminder(q, is_dry_run=not live, settings=s, trigger="manual")
                            flash(r["msg"], ":material/send:" if r["success"] else ":material/error:")
                            st.rerun()
            last = st.session_state.get("last_reminder_run")
            if last:
                with st.expander("Last run results", expanded=True):
                    st.dataframe(pd.DataFrame([{"Person": r["name"], "To": r["to"], "Amount": r["amount"],
                                                "Result": r["status"], "Details": r["msg"]} for r in last]),
                                 hide_index=True, width="stretch", column_config={"Amount": money_col("Amount")})
        with right:
            with st.container(border=True):
                section("Outstanding by age", "Based on each person's oldest unpaid item.")
                if queue:
                    plot("outstanding_by_age", queue, CURR)
                else:
                    empty_state("Nothing outstanding", "")

    with t_sched:
        left, right = st.columns([3, 2], gap="medium")
        with left:
            with st.container(border=True):
                section("Automatic schedule")
                with st.form("form_schedule"):
                    enabled = st.toggle("Send reminders automatically every day", value=bool(s["auto_enabled"]))
                    c1, c2 = st.columns(2)
                    hour = c1.selectbox("Send at", list(range(24)), index=int(s["send_hour"]), format_func=lambda h: f"{h:02d}:00")
                    min_amt = c2.number_input(f"Skip balances under ({CURR})", min_value=0.0, value=float(s["min_amount"]), step=50.0)
                    c3, c4 = st.columns(2)
                    overdue = c3.number_input("Remind once the oldest item is at least (days)", min_value=0, max_value=90,
                                              value=int(s["overdue_days"]))
                    cadence = c4.number_input("Wait between reminders to the same person (days)", min_value=1, max_value=60,
                                              value=int(s["cadence_days"]))
                    live_v = st.toggle("Send real emails (turn off for a dry run)", value=live)
                    if st.form_submit_button("Save schedule", type="primary"):
                        reminders.save_settings({"auto_enabled": enabled, "send_hour": int(hour), "min_amount": float(min_amt),
                                                 "overdue_days": int(overdue), "cadence_days": int(cadence), "live_mode": live_v})
                        flash("Reminder schedule saved")
                        st.rerun()
        with right:
            with st.container(border=True):
                section("How it works")
                st.markdown(
                    "- Each day at the chosen time, everyone marked **Due** gets one email covering all their circles.\n"
                    "- Balances account for recorded payments and shares marked paid, so people who've paid stop getting reminders.\n"
                    "- A person is only emailed again after the waiting period, even if you also send manually.\n"
                    "- In a dry run, emails are rendered and logged in History but not sent."
                )
                st.markdown("<div class='muted' style='margin-top:6px'>The schedule runs while this app is running. "
                            "To keep it running when the app is closed, add this to cron (it uses the same settings and never double-sends):</div>",
                            unsafe_allow_html=True)
                st.code(f"5 * * * * cd {BASE_DIR} && {sys.executable} reminders.py --auto >> reminders.log 2>&1", language="bash")

    with t_email:
        left, right = st.columns([3, 2], gap="medium")
        creds = reminders.get_smtp_credentials(s)
        with left:
            with st.container(border=True):
                section("SMTP server", "For Gmail use smtp.gmail.com, port 587 and an app password.")
                with st.form("form_smtp"):
                    c1, c2 = st.columns([3, 1])
                    host = c1.text_input("Server", value=s["smtp_host"] or creds["host"])
                    port = c2.number_input("Port", min_value=1, max_value=65535, value=int(s["smtp_port"] or creds["port"]))
                    c3, c4 = st.columns(2)
                    user = c3.text_input("Username", value=s["smtp_user"] or creds["user"], placeholder="you@gmail.com")
                    pw = c4.text_input("App password", value="", type="password",
                                       placeholder="Saved — leave blank to keep" if creds["pass"] else "Not set")
                    c5, c6 = st.columns(2)
                    from_email = c5.text_input("From address", value=s["from_email"] or creds["from_email"],
                                               placeholder="Defaults to the username")
                    sender = c6.text_input("Sender name", value=s["sender_name"] or reminders.APP_NAME)
                    test_to = st.text_input("Send a test email to", value=ACTIVE.get("email") or "")
                    b1, b2, _ = st.columns([1, 1, 2])
                    save = b1.form_submit_button("Save", type="primary", width="stretch")
                    test = b2.form_submit_button("Save and test", width="stretch")
                if save or test:
                    values = {"smtp_host": host.strip(), "smtp_port": int(port), "smtp_user": user.strip(),
                              "from_email": from_email.strip(), "sender_name": sender.strip() or reminders.APP_NAME}
                    if pw.strip():
                        values["smtp_pass"] = pw.strip()
                    reminders.save_settings(values)
                    if test:
                        with st.spinner("Connecting…"):
                            ok, msg = reminders.test_smtp_connection(test_to_email=test_to.strip() or None)
                        (st.success if ok else st.error)(msg)
                    else:
                        flash("Email settings saved")
                        st.rerun()
        with right:
            with st.container(border=True):
                section("Status")
                rows = [("Server", f"{creds['host']}:{creds['port']}"), ("Username", creds["user"] or "Not set"),
                        ("Password", "Saved" if creds["pass"] else "Not set"), ("From", creds["from_email"] or "Not set")]
                st.markdown("".join(f"<div class='row'><div class='row-meta'>{k}</div><div class='row-main'>{esc(v)}</div></div>"
                                    for k, v in rows), unsafe_allow_html=True)
                st.markdown("<div class='muted' style='margin-top:8px'>Settings are stored in the local database (data/finance.db). "
                            "Any field left blank falls back to the SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS and FROM_EMAIL environment variables.</div>",
                            unsafe_allow_html=True)
                if s["smtp_pass"] and st.button("Forget saved password", type="tertiary"):
                    reminders.save_settings({"smtp_pass": ""})
                    flash("Saved password removed", ":material/key_off:")
                    st.rerun()

    with t_hist:
        log = db.get_reminder_log(200)
        with st.container(border=True):
            if not log:
                empty_state("No reminders yet", "Sent and simulated reminders will appear here.")
            else:
                df = pd.DataFrame(log)
                show = pd.DataFrame({
                    "When": pd.to_datetime(df["created_at"]), "Person": df["user_name"].fillna("Deleted person"),
                    "Amount": df["amount"], "Result": df["status"].str.capitalize(),
                    "Trigger": df["trigger"].str.capitalize(), "To": df["recipient"], "Details": df["message"],
                })
                st.dataframe(show, hide_index=True, width="stretch",
                             column_config={"When": st.column_config.DatetimeColumn(format="DD MMM YYYY, HH:mm"),
                                            "Amount": money_col("Amount")})


# ---------------------------------------------------------------------------
# Page: Settings
# ---------------------------------------------------------------------------
def page_settings():
    page_header("Settings", "Preferences, people and data.")
    t_pref, t_people, t_data = st.tabs(["Preferences", "People", "Data"])

    with t_pref:
        left, right = st.columns(2, gap="medium")
        with left:
            with st.container(border=True):
                section("Currency", "Used throughout the app and in reminder emails.")
                cur = st.selectbox("Currency symbol", CURRENCIES, index=CURRENCIES.index(CURR) if CURR in CURRENCIES else 0)
                if cur != CURR:
                    reminders.save_settings({"currency": cur})
                    flash(f"Currency set to {cur}")
                    st.rerun()
        with right:
            with st.container(border=True):
                section("Your profile", ACTIVE["name"])
                with st.form("form_profile"):
                    n = st.text_input("Name", value=ACTIVE["name"])
                    e = st.text_input("Email", value=ACTIVE.get("email") or "")
                    p = st.text_input("Mobile (optional)", value=ACTIVE.get("phone") or "")
                    if st.form_submit_button("Save profile", type="primary"):
                        ok, err, c_em, c_ph = logic.validate_user_data(n, e, p, exclude_user_id=ACTIVE_ID)
                        if not ok:
                            st.error(err)
                        else:
                            try:
                                db.update_user(ACTIVE_ID, name=n, email=c_em, phone=c_ph or "")
                                flash("Profile saved")
                                st.rerun()
                            except ValueError as ex:
                                st.error(str(ex))

    with t_people:
        left, right = st.columns([3, 2], gap="medium")
        with left:
            with st.container(border=True):
                section("People", f"{len(users)} profile(s). Everyone can be added to circles and receive reminders.")
                df = pd.DataFrame(users)
                st.dataframe(df[["name", "email", "phone", "monthly_budget"]], hide_index=True, width="stretch",
                             column_config={"name": "Name", "email": "Email", "phone": "Mobile",
                                            "monthly_budget": money_col("Monthly budget")})
        with right:
            with st.container(border=True):
                section("Add a person")
                with st.form("form_add_person", clear_on_submit=True):
                    n = st.text_input("Name")
                    e = st.text_input("Email")
                    p = st.text_input("Mobile (optional)")
                    b = st.number_input(f"Monthly budget ({CURR})", min_value=0.0, value=0.0, step=1000.0)
                    if st.form_submit_button("Add person", type="primary", width="stretch"):
                        ok, err, c_em, c_ph = logic.validate_user_data(n, e, p)
                        if not ok:
                            st.error(err)
                        else:
                            try:
                                db.create_user(n.strip(), c_em, c_ph, float(b))
                                flash(f"Added {n.strip()}")
                                st.rerun()
                            except ValueError as ex:
                                st.error(str(ex))
            with st.container(border=True):
                section("Remove a person", "Deletes their transactions, splits and payments.")
                others = [u["user_id"] for u in users]
                victim = st.selectbox("Person", others, format_func=lambda i: user_map[i]["name"], key="rm_person")
                ok = st.checkbox("I understand this can't be undone", key="rm_person_ok")
                if st.button("Remove person", disabled=not ok or len(users) <= 1, width="stretch"):
                    db.delete_user(victim)
                    flash(f"Removed {user_map[victim]['name']}", ":material/person_remove:")
                    st.rerun()

    with t_data:
        c1, c2, c3 = st.columns(3, gap="medium")
        exports = [
            (c1, "Expenses", db.get_all_expenses(), "expenses"),
            (c2, "Income", db.get_user_incomes(), "income"),
            (c3, "Payments", db.get_settlements(), "payments"),
        ]
        for col, title, rows, slug in exports:
            with col:
                with st.container(border=True):
                    section(title, f"{len(rows)} record(s), all people")
                    st.download_button("Download CSV", data=pd.DataFrame(rows).to_csv(index=False).encode("utf-8"),
                                       file_name=f"{slug}_{today.isoformat()}.csv", mime="text/csv",
                                       disabled=not rows, width="stretch", key=f"dl_{slug}", icon=":material/download:",
                                       on_click="ignore")
        with st.container(border=True):
            section("Reset", "Both actions replace everything in the database. Reminder and email settings are kept.")
            ok = st.checkbox("I understand all current data will be erased", key="reset_ok")
            b1, b2, _ = st.columns([1, 1, 2])
            if b1.button("Load sample data", disabled=not ok, width="stretch"):
                db.seed_comprehensive_demo_data(reset=True)
                st.session_state.clear()
                flash("Sample data loaded")
                st.rerun()
            if b2.button("Erase everything", disabled=not ok, width="stretch"):
                db.reset_database()
                st.session_state.clear()
                st.rerun()


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------
# Each page is a fragment, so a control on a page (a month picker, a tab's toggle, a table
# selection) reruns just that page instead of the whole app with its sidebar. Anything that
# writes data calls st.rerun(), which still refreshes the whole app.
PAGE_OVERVIEW = st.Page(fragment(page_overview), title="Overview", icon=":material/space_dashboard:", url_path="overview", default=True)
PAGE_TRANSACTIONS = st.Page(fragment(page_transactions), title="Transactions", icon=":material/receipt_long:", url_path="transactions")
PAGE_BUDGETS = st.Page(fragment(page_budgets), title="Budgets", icon=":material/savings:", url_path="budgets")
PAGE_REPORTS = st.Page(fragment(page_reports), title="Reports", icon=":material/insights:", url_path="reports")
PAGE_CIRCLES = st.Page(fragment(page_circles), title="Circles", icon=":material/group:", url_path="circles")
PAGE_SETTLE = st.Page(fragment(page_settle), title="Settle up", icon=":material/handshake:", url_path="settle-up")
PAGE_REMINDERS = st.Page(fragment(page_reminders), title="Reminders", icon=":material/notifications:", url_path="reminders")
PAGE_SETTINGS = st.Page(fragment(page_settings), title="Settings", icon=":material/settings:", url_path="settings")

nav = st.navigation({
    "Personal": [PAGE_OVERVIEW, PAGE_TRANSACTIONS, PAGE_BUDGETS, PAGE_REPORTS],
    "Shared": [PAGE_CIRCLES, PAGE_SETTLE, PAGE_REMINDERS],
    "Account": [PAGE_SETTINGS],
})

with st.sidebar:
    st.markdown(
        f"<div class='muted' style='margin-top:4px'>Automatic reminders: "
        f"<b style='color:var(--ink)'>{'On' if SETTINGS['auto_enabled'] else 'Off'}</b>"
        f"{' &middot; dry run' if SETTINGS['auto_enabled'] and not SETTINGS['live_mode'] else ''}</div>",
        unsafe_allow_html=True,
    )
theme_toggle(ACTIVE_ID)

nav.run()
