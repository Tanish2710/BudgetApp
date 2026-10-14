"""
app.py - Smart Budgeter | Institutional Financial Command Center
High-performance personal expenditure tracking, Splitwise-style circle bill allocation,
debt simplification algorithms, cash flow telemetry, and automated email statements.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date, timedelta
import os
import sys

# Ensure local module discovery
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import database as db
import logic
import reminders

# --- Page Configuration ---
st.set_page_config(
    page_title="Smart Budgeter — Financial Operations",
    page_icon="■",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Idempotent DB initialization
@st.cache_resource(show_spinner=False)
def _init_db_once():
    db.init_db()
    return True

_init_db_once()

# --- Session State Initialization ---
if "currency" not in st.session_state:
    st.session_state["currency"] = "₹"
if "settle_prefill" not in st.session_state:
    st.session_state["settle_prefill"] = None
if "selected_tab" not in st.session_state:
    st.session_state["selected_tab"] = "Overview"
if "smtp_config" not in st.session_state:
    st.session_state["smtp_config"] = {
        "host": reminders.DEFAULT_SMTP_HOST,
        "port": reminders.DEFAULT_SMTP_PORT,
        "user": reminders.DEFAULT_SMTP_USER,
        "pass": reminders.DEFAULT_SMTP_PASS,
        "from_email": reminders.DEFAULT_FROM_EMAIL
    }
if "last_reminder_results" not in st.session_state:
    st.session_state["last_reminder_results"] = None

CURR = st.session_state["currency"]

# --- Institutional Design System (Non-gimmicky, authoritative, muted palette) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap');
    
    /* Base Reset & Architecture */
    html, body, .stApp {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
        background-color: #0A0D14 !important;
        color: #E2E8F0 !important;
        -webkit-font-smoothing: antialiased;
        letter-spacing: -0.01em;
    }

    /* Strict Typography Enforcement */
    p, h1, h2, h3, h4, h5, h6, label, input, select, textarea, div[data-testid="stMarkdownContainer"] {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif !important;
    }

    /* Monospace for Numbers, Codes, and Balances */
    .mono-num, .metric-amount, code, pre {
        font-family: 'JetBrains Mono', 'Roboto Mono', 'SF Mono', monospace !important;
        letter-spacing: -0.02em;
    }

    /* Streamlit Global Header & Layout Tightening */
    header[data-testid="stHeader"] {
        background: rgba(10, 13, 20, 0.90) !important;
        backdrop-filter: blur(12px) !important;
        border-bottom: 1px solid #1E2638 !important;
        z-index: 99999 !important;
        visibility: visible !important;
        display: flex !important;
    }

    /* Ensure Streamlit Toolbar and Deploy button remain prominently visible */
    [data-testid="stToolbar"],
    [data-testid="stDeployButton"],
    [data-testid="stToolbarActions"] {
        visibility: visible !important;
        display: flex !important;
    }

    .block-container {
        padding-top: 3.2rem !important;
        padding-bottom: 3rem !important;
        max-width: 1380px !important;
    }

    /* Sidebar Background & Border */
    [data-testid="stSidebar"] {
        background-color: #07090E !important;
        border-right: 1px solid #181F2E !important;
    }

    /* Top Navigation Toolbar */
    .top-toolbar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 12px 18px;
        background: #111622;
        border: 1px solid #1E2638;
        border-radius: 8px;
        margin-bottom: 20px;
    }

    .brand-title {
        font-size: 1.05rem;
        font-weight: 800;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        color: #F8FAFC;
    }

    .brand-sub {
        font-size: 0.68rem;
        font-weight: 600;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        color: #64748B;
    }

    /* Executive Metric Strip Cards */
    .metric-strip-card {
        background: #111622;
        border: 1px solid #1E2638;
        border-radius: 8px;
        padding: 16px 18px;
        transition: border-color 0.15s ease;
        height: 100%;
        min-height: 110px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }

    .metric-strip-card:hover {
        border-color: #2D374E;
    }

    .metric-hdr {
        display: flex;
        align-items: center;
        justify-content: space-between;
    }

    .metric-label-txt {
        font-size: 0.68rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: #64748B;
    }

    .metric-val-txt {
        font-size: 1.55rem;
        font-weight: 700;
        font-family: 'JetBrains Mono', monospace;
        letter-spacing: -0.03em;
        color: #F8FAFC;
        margin: 6px 0 2px 0;
    }

    .metric-sub-txt {
        font-size: 0.76rem;
        color: #8B95A5;
    }

    .txt-emerald { color: #16A34A !important; }
    .txt-rose    { color: #EF4444 !important; }
    .txt-sky     { color: #60A5FA !important; }

    /* Muted Institutional Status Badges */
    .badge {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 0.72rem;
        font-weight: 600;
        letter-spacing: 0.02em;
        line-height: 1.2;
    }
    .badge-green { background: rgba(34, 197, 94, 0.08); color: #22C55E; border: 1px solid rgba(34, 197, 94, 0.20); }
    .badge-red   { background: rgba(239, 68, 68, 0.08); color: #EF4444; border: 1px solid rgba(239, 68, 68, 0.20); }
    .badge-blue  { background: rgba(37, 99, 235, 0.08); color: #60A5FA; border: 1px solid rgba(37, 99, 235, 0.20); }
    .badge-gray  { background: rgba(148, 163, 184, 0.08); color: #94A3B8; border: 1px solid rgba(148, 163, 184, 0.16); }
    .badge-amber { background: rgba(245, 158, 11, 0.08); color: #F59E0B; border: 1px solid rgba(245, 158, 11, 0.20); }

    /* Clean Navigation Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 2px;
        background: #111622;
        padding: 3px;
        border-radius: 6px;
        border: 1px solid #1E2638;
        margin-bottom: 22px;
    }

    .stTabs [data-baseweb="tab"] {
        height: 34px;
        padding: 0 14px;
        background: transparent;
        border-radius: 4px;
        border: none;
        color: #8B95A5;
        font-weight: 600;
        font-size: 0.82rem;
        transition: all 0.12s ease;
    }

    .stTabs [data-baseweb="tab"]:hover {
        background: rgba(255, 255, 255, 0.03);
        color: #F8FAFC;
    }

    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background: #182030;
        color: #F8FAFC;
        border: 1px solid #283348;
        font-weight: 600;
    }

    .stTabs [data-baseweb="tab-highlight"],
    .stTabs [data-baseweb="tab-border"] {
        display: none !important;
    }

    /* Buttons: Restrained & Authoritative */
    div.stButton > button {
        border-radius: 6px !important;
        font-weight: 600 !important;
        font-size: 0.82rem !important;
        letter-spacing: -0.01em !important;
        transition: all 0.14s ease !important;
    }

    div.stButton > button[kind="primary"],
    div.stButton > button[data-testid="stBaseButton-primary"] {
        background: #2563EB !important;
        color: #FFFFFF !important;
        border: 1px solid #3B82F6 !important;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.3) !important;
    }

    div.stButton > button[kind="primary"]:hover,
    div.stButton > button[data-testid="stBaseButton-primary"]:hover {
        background: #1D4ED8 !important;
        border-color: #60A5FA !important;
    }

    div.stButton > button[kind="secondary"],
    div.stButton > button[data-testid="stBaseButton-secondary"] {
        background: #181E2B !important;
        border: 1px solid #283248 !important;
        color: #CBD5E1 !important;
    }

    div.stButton > button[kind="secondary"]:hover,
    div.stButton > button[data-testid="stBaseButton-secondary"]:hover {
        background: #1F2637 !important;
        border-color: #3B4764 !important;
        color: #FFFFFF !important;
    }

    /* Container Card Surfaces */
    [data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #111622 !important;
        border-color: #1E2638 !important;
        border-radius: 8px !important;
    }

    /* Streamlit Progress Bar */
    div[data-testid="stProgress"] > div > div > div > div {
        background: #2563EB !important;
        border-radius: 3px !important;
    }
    div[data-testid="stProgress"] > div > div {
        background: #1B2232 !important;
        border-radius: 3px !important;
    }

    /* Forms, Inputs & Selectboxes */
    div[data-baseweb="select"] > div,
    div[data-baseweb="input"] > div,
    div[data-baseweb="base-input"] > div,
    .stTextInput input,
    .stNumberInput input,
    .stDateInput input,
    .stSelectbox div[data-baseweb="select"] > div {
        background-color: #151B28 !important;
        border: 1px solid #232C3D !important;
        color: #E2E8F0 !important;
        border-radius: 6px !important;
    }

    div[data-baseweb="select"]:focus-within > div,
    div[data-baseweb="input"]:focus-within > div {
        border-color: #2563EB !important;
        box-shadow: 0 0 0 1px #2563EB !important;
    }

    /* Dataframe wrapper styling */
    div[data-testid="stDataFrame"] {
        border: 1px solid #1E2638 !important;
        border-radius: 6px !important;
        background: #111622 !important;
    }

    /* Streamlit Input instructions suppression */
    [data-testid="InputInstructions"],
    div[data-testid*="InputInstructions"] {
        display: none !important;
    }

    /* Streamlit default footer hide */
    footer {
        display: none !important;
    }
</style>
""", unsafe_allow_html=True)

# Helper to format money cleanly
def fmt(val):
    if val is None:
        return f"{CURR}0.00"
    try:
        return f"{CURR}{float(val):,.2f}"
    except (ValueError, TypeError):
        return f"{CURR}0.00"

# --- Data Loading ---
users = db.get_all_users()
groups = db.get_all_groups()

user_map = {u["user_id"]: u for u in users}
user_name_to_id = {f"{u['name']} (#{u['user_id']})": u["user_id"] for u in users}
group_map = {g["group_id"]: g for g in groups}
group_name_to_id = {f"{g['group_name']} (#{g['group_id']})": g["group_id"] for g in groups}

# --- Sidebar (Clean Institutional Navigation) ---
with st.sidebar:
    st.markdown("""
        <div style="padding: 4px 0 12px 0; border-bottom: 1px solid #1E2638; margin-bottom: 14px;">
            <div class="brand-title">Smart Budgeter</div>
            <div class="brand-sub">Financial Command • Enterprise</div>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("<div style='font-size:0.7rem; font-weight:700; color:#64748B; text-transform:uppercase; margin-bottom:4px;'>Profile Scope</div>", unsafe_allow_html=True)
    if users:
        user_options = list(user_name_to_id.keys())
        active_user_label = st.selectbox("Active Profile", options=user_options, index=0, label_visibility="collapsed")
        active_user_id = user_name_to_id[active_user_label]
        active_user = user_map[active_user_id]
        
        st.markdown(f"""
            <div style="background:#111622; border:1px solid #1E2638; border-radius:6px; padding:10px 12px; margin-top:6px; margin-bottom:14px; font-size:0.75rem;">
                <div style="color:#64748B;">Account: <span style="color:#CBD5E1; font-family:'JetBrains Mono',monospace;">{active_user.get('email') or 'No email'}</span></div>
                <div style="color:#64748B; margin-top:3px;">Monthly Cap: <span style="color:#60A5FA; font-family:'JetBrains Mono',monospace;">{fmt(active_user.get('monthly_budget', 0))}</span></div>
            </div>
        """, unsafe_allow_html=True)
    else:
        active_user_id = None
        active_user = None
        st.warning("No users available.")

    st.markdown("<div style='font-size:0.7rem; font-weight:700; color:#64748B; text-transform:uppercase; margin-bottom:4px;'>Circle Filter</div>", unsafe_allow_html=True)
    circle_options = ["All Circles"] + list(group_name_to_id.keys())
    active_circle_label = st.selectbox("Circle Scope", options=circle_options, label_visibility="collapsed")
    active_group_id = group_name_to_id[active_circle_label] if active_circle_label != "All Circles" else None

    st.divider()

    # Quick Create Actions
    with st.expander("Create Entity", expanded=False):
        c_tab_u, c_tab_g = st.tabs(["User", "Circle"])
        with c_tab_u:
            with st.form("sidebar_create_user", clear_on_submit=True):
                nu_name = st.text_input("Full Name", placeholder="e.g. Alex Morgan")
                nu_email = st.text_input("Email Address", placeholder="alex@example.com")
                nu_phone = st.text_input("Mobile Number (10 digits)", placeholder="9876543210", max_chars=10)
                nu_budget = st.number_input(f"Monthly Budget ({CURR})", min_value=0.0, value=1500.0, step=100.0)
                if st.form_submit_button("Add User", type="primary", width="stretch"):
                    valid, err, c_em, c_ph = logic.validate_user_data(nu_name, nu_email, nu_phone)
                    if not valid:
                        st.error(err)
                    else:
                        try:
                            db.create_user(nu_name.strip(), c_em, c_ph, float(nu_budget))
                            st.success(f"Added {nu_name.strip()}")
                            st.rerun()
                        except ValueError as ve:
                            st.error(str(ve))
                        except Exception as e:
                            st.error(f"Error: {e}")

        with c_tab_g:
            with st.form("sidebar_create_circle", clear_on_submit=True):
                ng_name = st.text_input("Circle Name", placeholder="e.g. Apartment 4B")
                if st.form_submit_button("Create Circle", type="primary", width="stretch"):
                    if ng_name.strip():
                        try:
                            gid = db.create_group(ng_name.strip())
                            if active_user_id:
                                db.add_member_to_group(gid, active_user_id)
                            st.success(f"Circle '{ng_name}' created")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")
                    else:
                        st.warning("Circle name required.")

    # Data Utilities
    with st.expander("System Utilities", expanded=False):
        c_seed, c_reset = st.columns(2)
        with c_seed:
            if st.button("Load Demo", width="stretch", help="Load comprehensive dataset"):
                db.seed_comprehensive_demo_data(reset=True)
                st.success("Demo dataset loaded.")
                st.rerun()
        with c_reset:
            if st.button("Reset DB", width="stretch", help="Reset all database tables"):
                conn = db.get_db_connection()
                for t in ["splits", "shared_expenses", "settlements", "group_members", "groups", "category_budgets", "incomes", "expenses", "users"]:
                    conn.execute(f"DROP TABLE IF EXISTS {t}")
                conn.commit()
                conn.close()
                db.init_db()
                st.success("Database reset clean.")
                st.rerun()

# --- Onboarding Empty State ---
if not users:
    st.markdown("""
        <div style="background:#111622; border:1px solid #1E2638; border-radius:8px; padding:48px 24px; text-align:center;">
            <div style="font-size:1.4rem; font-weight:800; color:#F8FAFC; margin-bottom:8px;">Smart Budgeter</div>
            <p style="color:#8B95A5; max-width:480px; margin:0 auto 20px auto; font-size:0.9rem; line-height:1.5;">
                Enterprise personal finance management, shared expense allocation, debt simplification, and automated payment statements.
            </p>
        </div>
    """, unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        if st.button("Initialize Sample Financial Dataset", type="primary", width="stretch"):
            db.seed_comprehensive_demo_data(reset=True)
            st.success("Sample data initialized.")
            st.rerun()
    st.stop()

# --- Active User Financial Telemetry ---
cur_month = datetime.now().strftime("%Y-%m")
cur_month_name = datetime.now().strftime("%B %Y")
bs = logic.get_budget_status(active_user_id, cur_month)
cf = logic.get_cash_flow_summary(active_user_id, cur_month)
user_balances = logic.compute_balances(active_group_id)
user_net_balance = user_balances.get(active_user_id, 0.0)

all_unpaid = logic.get_unpaid_splits(active_group_id)
active_unpaid_owed_by_me = [s for s in all_unpaid if s["user_id"] == active_user_id]
active_unpaid_owed_to_me = [s for s in all_unpaid if s["payer_id"] == active_user_id]

# --- Dialog: Quick Settlement Payment ---
@st.dialog("Record Settlement Payment")
def quick_settle_modal(from_uid, to_uid, amount, default_note="", group_id=None):
    from_name = user_map.get(from_uid, {}).get("name", f"User #{from_uid}")
    to_name = user_map.get(to_uid, {}).get("name", f"User #{to_uid}")
    st.markdown(f"""
        <div style="background:#161C2A; border:1px solid #232C3D; border-radius:6px; padding:12px 16px; margin-bottom:14px;">
            <div style="font-size:0.7rem; font-weight:700; text-transform:uppercase; letter-spacing:0.05em; color:#8B95A5; margin-bottom:4px;">Direction of Payment</div>
            <div style="display:flex; justify-content:space-between; align-items:center; font-weight:700;">
                <span style="color:#EF4444;">{from_name}</span>
                <span style="color:#64748B;">&rarr;</span>
                <span style="color:#16A34A;">{to_name}</span>
            </div>
        </div>
    """, unsafe_allow_html=True)
    with st.form("dlg_settle_form"):
        s_amt = st.number_input(f"Amount ({CURR})", min_value=0.01, value=float(amount), step=1.0)
        s_meth = st.selectbox("Settlement Method", ["UPI / Bank Transfer", "Cash", "Venmo", "Zelle", "Wire Transfer"])
        s_note = st.text_input("Reference Note", value=default_note)
        if st.form_submit_button("Confirm Payment & Clear Balance", type="primary", width="stretch"):
            db.add_settlement(from_uid, to_uid, float(s_amt), group_id, s_note, s_meth)
            st.session_state["settle_prefill"] = None
            st.success(f"Recorded payment of {fmt(s_amt)}")
            st.rerun()

# --- Dialog: Statement Email Preview ---
@st.dialog("Payment Statement Preview", width="large")
def preview_email_modal(split_item):
    debtor = split_item["debtor_name"]
    payer = split_item["payer_name"]
    desc = split_item["description"]
    amt = split_item["amount_owed"]
    dt = split_item["date"]
    tot = split_item["total"]
    grp = split_item.get("group_name", "")
    to_email = split_item.get("debtor_email", "user@example.com")

    subject = f"Payment Reminder: {fmt(amt)} for '{desc}'"
    html_content = reminders.build_email_html(debtor, payer, desc, amt, dt, tot, grp, curr=CURR)

    st.markdown(f"""
        <div style="background:#111622; border:1px solid #1E2638; border-radius:6px; padding:12px 14px; margin-bottom:12px; font-size:0.82rem;">
            <div><strong style="color:#64748B;">Recipient:</strong> <span style="font-family:'JetBrains Mono',monospace; color:#60A5FA;">{to_email}</span></div>
            <div style="margin-top:2px;"><strong style="color:#64748B;">Subject:</strong> <span style="color:#F8FAFC;">{subject}</span></div>
        </div>
    """, unsafe_allow_html=True)
    st.html(html_content)

# --- Top Navigation Bar ---
top_left, top_mid, top_right = st.columns([6, 3, 3], vertical_alignment="center")

with top_left:
    st.markdown(f"""
        <div style="display:flex; align-items:center; gap:8px;">
            <div style="width:8px; height:8px; background:#2563EB; border-radius:2px;"></div>
            <span class="brand-title">Smart Budgeter</span>
            <span class="badge badge-gray">Operations</span>
        </div>
    """, unsafe_allow_html=True)

with top_mid:
    st.markdown(f"""
        <div style="text-align:right; font-size:0.8rem; color:#64748B;">
            Scope: <strong style="color:#CBD5E1;">{active_circle_label}</strong>
        </div>
    """, unsafe_allow_html=True)

with top_right:
    c_btn1, c_btn2 = st.columns([1, 1], vertical_alignment="center")
    with c_btn1:
        if active_unpaid_owed_by_me:
            if st.button("Settle Balance", type="primary", width="stretch"):
                d = active_unpaid_owed_by_me[0]
                quick_settle_modal(active_user_id, d["payer_id"], d["amount_owed"], f"Payment for {d['description']}", active_group_id)
        else:
            st.markdown(f"<div style='text-align:center;'><span class='badge badge-green'>Settled Up</span></div>", unsafe_allow_html=True)
    with c_btn2:
        with st.popover("Preferences", width="stretch"):
            st.markdown("##### Preferences")
            curr_options = ["₹", "$", "€", "£", "¥"]
            curr_idx = curr_options.index(st.session_state["currency"]) if st.session_state["currency"] in curr_options else 0
            new_curr = st.selectbox("Base Currency", options=curr_options, index=curr_idx)
            if new_curr != st.session_state["currency"]:
                st.session_state["currency"] = new_curr
                st.rerun()

            st.divider()
            st.markdown("##### Edit Account")
            with st.form("popover_edit_profile"):
                ep_name = st.text_input("Name", value=active_user["name"])
                ep_email = st.text_input("Email", value=active_user.get("email") or "")
                ep_phone = st.text_input("Mobile Number", value=active_user.get("phone") or "", max_chars=10)
                ep_budget = st.number_input(f"Monthly Budget ({CURR})", min_value=0.0, value=float(active_user.get("monthly_budget") or 1000.0), step=100.0)
                if st.form_submit_button("Save Changes", type="primary", width="stretch"):
                    valid, err, c_em, c_ph = logic.validate_user_data(ep_name, ep_email, ep_phone, exclude_user_id=active_user_id)
                    if not valid:
                        st.error(err)
                    else:
                        db.update_user(active_user_id, name=ep_name, email=c_em, phone=c_ph, monthly_budget=float(ep_budget))
                        st.success("Account profile updated.")
                        st.rerun()

# --- Clean Navigation Tabs ---
tabs = st.tabs([
    "Overview",
    "Transactions",
    "Shared Expenses",
    "Settlements",
    "Analytics",
    "Email Reminders",
    "Data & Export"
])

# =========================================================================
# TAB 1: OVERVIEW (EXECUTIVE DASHBOARD)
# =========================================================================
with tabs[0]:
    # Header strip for Overview
    bal_sign = "+" if user_net_balance > 0 else ""
    bal_badge = "badge-green" if user_net_balance >= 0 else "badge-red"
    bal_text = f"Net Position: {bal_sign}{fmt(user_net_balance)}" if user_net_balance >= 0 else f"Net Position: {fmt(user_net_balance)}"

    st.markdown(f"""
        <div style="display:flex; justify-content:space-between; align-items:center; padding:8px 0 14px 0; border-bottom:1px solid #1E2638; margin-bottom:16px;">
            <div>
                <div style="font-size:1.1rem; font-weight:700; color:#F8FAFC;">Executive Dashboard &bull; {active_user['name']}</div>
                <div style="font-size:0.78rem; color:#64748B; margin-top:2px;">Reporting Period: {cur_month_name} &bull; Circle: {active_circle_label}</div>
            </div>
            <div style="display:flex; gap:8px;">
                <span class="badge {bal_badge}">{bal_text}</span>
                <span class="badge badge-blue">{len(active_unpaid_owed_by_me)} pending obligation(s)</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # 4 Key Minimalist Metrics
    k1, k2, k3, k4 = st.columns(4)

    with k1:
        pct_used = bs["pct_used"]
        spend_color = "txt-emerald" if pct_used < 75 else ("txt-sky" if pct_used <= 90 else "txt-rose")
        st.markdown(f"""
            <div class="metric-strip-card">
                <div>
                    <div class="metric-label-txt">Monthly Spend</div>
                    <div class="metric-val-txt {spend_color}">{fmt(bs['spent'])}</div>
                </div>
                <div class="metric-sub-txt">Budget: {fmt(bs['budget'])} ({pct_used}% utilized)</div>
            </div>
        """, unsafe_allow_html=True)

    with k2:
        net_cf = cf["net_cashflow"]
        cf_color = "txt-emerald" if net_cf >= 0 else "txt-rose"
        cf_sign = "+" if net_cf >= 0 else ""
        st.markdown(f"""
            <div class="metric-strip-card">
                <div>
                    <div class="metric-label-txt">Net Cash Flow</div>
                    <div class="metric-val-txt {cf_color}">{cf_sign}{fmt(net_cf)}</div>
                </div>
                <div class="metric-sub-txt">Income: {fmt(cf['total_income'])} &bull; Savings: {cf['savings_rate']}%</div>
            </div>
        """, unsafe_allow_html=True)

    with k3:
        safe_daily = bs["safe_daily_spend"]
        pacing_status = "On Track" if not bs["is_pacing_fast"] else "Pacing Fast"
        st.markdown(f"""
            <div class="metric-strip-card">
                <div>
                    <div class="metric-label-txt">Safe Daily Spend</div>
                    <div class="metric-val-txt txt-sky">{fmt(safe_daily)}</div>
                </div>
                <div class="metric-sub-txt">{bs['days_remaining']} days remaining &bull; {pacing_status}</div>
            </div>
        """, unsafe_allow_html=True)

    with k4:
        bal_color = "txt-emerald" if user_net_balance > 0 else ("txt-rose" if user_net_balance < 0 else "txt-sky")
        bal_desc = "Owed to you" if user_net_balance > 0 else ("You owe others" if user_net_balance < 0 else "Settled")
        bal_sign_k = "+" if user_net_balance > 0 else ""
        st.markdown(f"""
            <div class="metric-strip-card">
                <div>
                    <div class="metric-label-txt">Circle Balance</div>
                    <div class="metric-val-txt {bal_color}">{bal_sign_k}{fmt(user_net_balance)}</div>
                </div>
                <div class="metric-sub-txt">{bal_desc}</div>
            </div>
        """, unsafe_allow_html=True)

    st.write("")

    # Visual Analytics Row
    col_pacing, col_donut = st.columns([3, 2])

    with col_pacing:
        with st.container(border=True):
            st.markdown("##### Budget Health & Category Pacing")
            b_pct = min(1.0, max(0.0, bs["spent"] / bs["budget"])) if bs["budget"] > 0 else 0.0
            st.progress(b_pct)
            
            p1, p2, p3 = st.columns(3)
            with p1: st.caption(f"Expenditure: **{fmt(bs['spent'])}**")
            with p2: st.caption(f"Remaining: **{fmt(bs['remaining'])}**")
            with p3: st.caption(f"Projected Total: **{fmt(bs['projected_spend'])}**")

            cat_statuses = logic.get_category_budget_status(active_user_id, cur_month)
            budgeted_cats = [c for c in cat_statuses if c["has_budget"]]
            if budgeted_cats:
                st.markdown("<div style='font-size:0.7rem; font-weight:700; color:#64748B; text-transform:uppercase; margin-top:12px; margin-bottom:6px;'>Allocated Category Limits</div>", unsafe_allow_html=True)
                for cb in budgeted_cats[:4]:
                    cb_pct = min(1.0, cb["spent"] / cb["budget"]) if cb["budget"] > 0 else 0.0
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        st.caption(f"{cb['category']}: {fmt(cb['spent'])} / {fmt(cb['budget'])}")
                        st.progress(cb_pct)
                    with c2:
                        rem_label = f"{fmt(cb['remaining'])} left" if cb['remaining'] >= 0 else f"{fmt(abs(cb['remaining']))} over"
                        c_color = "#16A34A" if cb['remaining'] >= 0 else "#EF4444"
                        st.markdown(f"<div style='color:{c_color}; font-size:0.75rem; font-weight:600; text-align:right; font-family:monospace; padding-top:4px;'>{rem_label}</div>", unsafe_allow_html=True)

    with col_donut:
        with st.container(border=True):
            st.markdown("##### Expenditure by Category")
            cat_data = db.get_spending_by_category(active_user_id, cur_month)
            if cat_data:
                df_cat = pd.DataFrame(cat_data)
                # Institutional corporate blue/teal/slate palette
                fin_palette = ["#2563EB", "#3B82F6", "#60A5FA", "#0D9488", "#14B8A6", "#475569", "#64748B", "#94A3B8"]
                fig_cat = px.pie(
                    df_cat,
                    names="category",
                    values="total",
                    hole=0.64,
                    color_discrete_sequence=fin_palette,
                    template="plotly_dark"
                )
                fig_cat.update_traces(textposition='outside', textinfo='percent+label', marker=dict(line=dict(color='#111622', width=1.5)))
                fig_cat.update_layout(
                    margin=dict(t=10, b=10, l=10, r=10),
                    showlegend=False,
                    height=260,
                    font=dict(family="Plus Jakarta Sans, sans-serif", size=11),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)"
                )
                st.plotly_chart(fig_cat, width="stretch")
            else:
                st.caption(f"No expenditure records found for {cur_month_name}.")

    # Recent Transactions Ledger
    st.markdown("##### Recent Transactions")
    user_recent_exp = db.get_expenses_filtered(user_id=active_user_id, limit=8)
    if user_recent_exp:
        recent_df = pd.DataFrame(user_recent_exp)
        recent_display = recent_df[["date", "category", "description", "payment_method", "amount"]].copy()
        recent_display["amount"] = recent_display["amount"].apply(lambda x: fmt(x))
        recent_display.rename(columns={
            "date": "Date", "category": "Category", "description": "Description",
            "payment_method": "Method", "amount": "Amount"
        }, inplace=True)
        st.dataframe(recent_display, width="stretch", hide_index=True)
    else:
        st.caption("No transactions logged.")

# =========================================================================
# TAB 2: TRANSACTIONS (LOG & MANAGE)
# =========================================================================
with tabs[1]:
    st.markdown("### Transaction Management")

    log_type = st.segmented_control(
        "Transaction Classification",
        options=["Personal Expense", "Income Stream", "Shared Group Bill"],
        default="Personal Expense"
    )

    if log_type == "Personal Expense":
        with st.container(border=True):
            st.markdown("##### Record Personal Expenditure")
            with st.form("form_personal_expense", clear_on_submit=True):
                col_e1, col_e2, col_e3 = st.columns(3)
                with col_e1:
                    user_opts = list(user_name_to_id.keys())
                    u_idx = list(user_name_to_id.values()).index(active_user_id) if active_user_id in user_name_to_id.values() else 0
                    exp_user_name = st.selectbox("Account", options=user_opts, index=u_idx)
                    exp_amt = st.number_input(f"Amount ({CURR})", min_value=0.01, value=25.0, step=1.0)
                with col_e2:
                    exp_cat = st.selectbox("Category", [
                        "Food & Dining", "Housing & Rent", "Groceries", "Utilities",
                        "Transportation", "Entertainment", "Health & Medical",
                        "Shopping", "Travel", "Education", "Other"
                    ])
                    exp_date = st.date_input("Date Incurred", value=date.today())
                with col_e3:
                    exp_pmethod = st.selectbox("Payment Instrument", ["UPI / Bank Transfer", "Credit Card", "Debit Card", "Cash", "Corporate Card"])
                    exp_desc = st.text_input("Description", placeholder="e.g. Lunch with Client")

                exp_notes = st.text_input("Reference Notes (Optional)", placeholder="e.g. #reimbursable, tax-deductible")

                if st.form_submit_button("Record Expense", width="stretch", type="primary"):
                    uid = user_name_to_id[exp_user_name]
                    db.add_expense(uid, float(exp_amt), exp_cat, exp_date.isoformat(), exp_desc, exp_pmethod, exp_notes)
                    st.success(f"Recorded expense of {fmt(exp_amt)}")
                    st.rerun()

    elif log_type == "Income Stream":
        with st.container(border=True):
            st.markdown("##### Record Inflow / Income Stream")
            with st.form("form_income", clear_on_submit=True):
                col_i1, col_i2, col_i3 = st.columns(3)
                with col_i1:
                    u_idx_inc = list(user_name_to_id.values()).index(active_user_id) if active_user_id in user_name_to_id.values() else 0
                    inc_user_name = st.selectbox("Recipient Account", options=list(user_name_to_id.keys()), index=u_idx_inc)
                    inc_amt = st.number_input(f"Amount ({CURR})", min_value=0.01, value=1000.0, step=50.0)
                with col_i2:
                    inc_source = st.selectbox("Source Category", ["Salary", "Freelance & Consulting", "Investments & Dividends", "Reimbursements", "Gifts", "Other"])
                    inc_date = st.date_input("Date Received", value=date.today())
                with col_i3:
                    inc_desc = st.text_input("Source Description", placeholder="e.g. Monthly Payroll")

                if st.form_submit_button("Record Inflow", width="stretch", type="primary"):
                    uid = user_name_to_id[inc_user_name]
                    db.add_income(uid, float(inc_amt), inc_source, inc_date.isoformat(), inc_desc)
                    st.success(f"Recorded income of {fmt(inc_amt)}")
                    st.rerun()

    elif log_type == "Shared Group Bill":
        if not groups:
            st.warning("Please create a Circle first to split bills.")
        else:
            with st.container(border=True):
                st.markdown("##### Create Shared Bill & Allocate Splits")
                col_s1, col_s2, col_s3 = st.columns(3)
                with col_s1:
                    sel_grp_name = st.selectbox("Circle", options=list(group_name_to_id.keys()), index=0)
                    chosen_gid = group_name_to_id[sel_grp_name]
                    grp_members = db.get_group_members(chosen_gid)
                    if not grp_members:
                        st.warning("This circle has no active members.")
                        grp_member_map = {}
                        grp_member_names = []
                    else:
                        grp_member_map = {m["user_id"]: m["name"] for m in grp_members}
                        grp_member_names = [f"{m['name']} (#{m['user_id']})" for m in grp_members]

                if grp_members:
                    with col_s2:
                        payer_label = st.selectbox("Paid Originally By", options=grp_member_names)
                        payer_uid = int(payer_label.split("#")[1].rstrip(")"))
                        bill_total = st.number_input(f"Total Amount ({CURR})", min_value=0.01, value=60.0, step=5.0)
                    with col_s3:
                        bill_desc = st.text_input("Description", placeholder="e.g. Office Supplies, Travel Expense")
                        bill_date = st.date_input("Expense Date", value=date.today())

                    bill_category = st.selectbox("Expense Category", ["General", "Groceries", "Food & Dining", "Rent & Housing", "Utilities", "Travel", "Entertainment"])

                    st.markdown("<div style='font-size:0.7rem; font-weight:700; color:#64748B; text-transform:uppercase; margin-top:10px; margin-bottom:4px;'>Allocation Method</div>", unsafe_allow_html=True)
                    split_mode = st.radio(
                        "Split Strategy",
                        options=["Equal Split (=)", "Exact Amounts ($)", "Percentage (%)", "Weighted Shares (x)"],
                        horizontal=True
                    )

                    participating_members = st.multiselect(
                        "Participants Included in Allocation",
                        options=grp_member_names,
                        default=grp_member_names
                    )

                    custom_splits_to_save = None
                    can_submit = True

                    if not participating_members:
                        st.warning("Please select at least one participant.")
                        can_submit = False
                    else:
                        part_uids = [int(n.split("#")[1].rstrip(")")) for n in participating_members]
                        n_parts = len(part_uids)

                        if split_mode == "Equal Split (=)":
                            per_head = round(bill_total / n_parts, 2)
                            st.caption(f"Equal share: **{fmt(per_head)}** per participant.")
                            custom_splits_to_save = None
                        elif split_mode == "Exact Amounts ($)":
                            cols = st.columns(min(4, n_parts))
                            exact_dict = {}
                            default_part = round(bill_total / n_parts, 2)
                            for idx, p_label in enumerate(participating_members):
                                u_id = int(p_label.split("#")[1].rstrip(")"))
                                col_idx = idx % min(4, n_parts)
                                with cols[col_idx]:
                                    exact_val = st.number_input(f"{grp_member_map[u_id]} ({CURR})", min_value=0.0, value=default_part, step=1.0, key=f"ex_{u_id}")
                                    exact_dict[u_id] = exact_val
                            sum_exact = round(sum(exact_dict.values()), 2)
                            if abs(round(bill_total - sum_exact, 2)) > 0.01:
                                st.error(f"Sum of allocations ({fmt(sum_exact)}) does not equal total ({fmt(bill_total)}).")
                                can_submit = False
                            else:
                                custom_splits_to_save = exact_dict
                        elif split_mode == "Percentage (%)":
                            cols = st.columns(min(4, n_parts))
                            pct_dict = {}
                            default_pct = round(100.0 / n_parts, 1)
                            for idx, p_label in enumerate(participating_members):
                                u_id = int(p_label.split("#")[1].rstrip(")"))
                                col_idx = idx % min(4, n_parts)
                                with cols[col_idx]:
                                    pct_val = st.number_input(f"{grp_member_map[u_id]} (%)", min_value=0.0, max_value=100.0, value=default_pct, step=1.0, key=f"pct_{u_id}")
                                    pct_dict[u_id] = pct_val
                            if abs(round(sum(pct_dict.values()), 1) - 100.0) > 0.5:
                                st.error("Percentages must sum to 100%.")
                                can_submit = False
                            else:
                                custom_splits_to_save = {uid: round((p / 100.0) * bill_total, 2) for uid, p in pct_dict.items()}
                        elif split_mode == "Weighted Shares (x)":
                            cols = st.columns(min(4, n_parts))
                            shares_dict = {}
                            for idx, p_label in enumerate(participating_members):
                                u_id = int(p_label.split("#")[1].rstrip(")"))
                                col_idx = idx % min(4, n_parts)
                                with cols[col_idx]:
                                    sh_val = st.number_input(f"{grp_member_map[u_id]} (parts)", min_value=1, value=1, step=1, key=f"sh_{u_id}")
                                    shares_dict[u_id] = sh_val
                            tot_sh = sum(shares_dict.values())
                            custom_splits_to_save = {uid: round((sh / tot_sh) * bill_total, 2) for uid, sh in shares_dict.items()}

                    if st.button("Commit Shared Expense", type="primary", disabled=not can_submit, width="stretch"):
                        try:
                            if custom_splits_to_save:
                                db.add_shared_expense(chosen_gid, payer_uid, float(bill_total), bill_desc or "Shared Bill", bill_date.isoformat(), custom_splits=custom_splits_to_save, category=bill_category)
                            else:
                                db.add_shared_expense(chosen_gid, payer_uid, float(bill_total), bill_desc or "Shared Bill", bill_date.isoformat(), split_among=part_uids, category=bill_category)
                            st.success("Shared bill recorded and balances updated.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")

    # Ledger Filter & Records
    st.divider()
    st.markdown("##### Filterable Transaction Ledger")
    tf_c1, tf_c2, tf_c3 = st.columns([2, 1, 1])
    with tf_c1:
        search_kw = st.text_input("Keyword Search", placeholder="Filter by description or notes...")
    with tf_c2:
        cat_filter = st.selectbox("Category", options=["All"] + db.get_distinct_categories())
    with tf_c3:
        user_filter_opt = st.selectbox("Account Filter", options=["All Accounts"] + list(user_name_to_id.keys()))
        selected_uid_filter = user_name_to_id[user_filter_opt] if user_filter_opt != "All Accounts" else None

    filtered_expenses = db.get_expenses_filtered(
        user_id=selected_uid_filter,
        category=cat_filter,
        search=search_kw.strip() if search_kw else None,
        limit=50
    )

    if filtered_expenses:
        f_df = pd.DataFrame(filtered_expenses)
        display_cols = ["exp_id", "date", "user_name", "category", "amount", "payment_method", "description", "notes"]
        f_display = f_df[[c for c in display_cols if c in f_df.columns]].copy()
        f_display["amount"] = f_display["amount"].apply(lambda x: fmt(x))
        f_display.rename(columns={
            "exp_id": "ID", "date": "Date", "user_name": "Account", "category": "Category",
            "amount": "Amount", "payment_method": "Instrument", "description": "Description", "notes": "Notes"
        }, inplace=True)
        st.dataframe(f_display, width="stretch", hide_index=True)

        with st.expander("Record Management (Delete Entry)", expanded=False):
            del_options = [f"#{e['exp_id']} • {e['date']} • {e['user_name']} • {fmt(e['amount'])} ({e['description']})" for e in filtered_expenses]
            sel_del = st.selectbox("Select Entry", options=del_options)
            if st.button("Delete Selected Entry", type="secondary"):
                del_id = int(sel_del.split("•")[0].replace("#", "").strip())
                db.delete_expense(del_id)
                st.success(f"Entry #{del_id} deleted.")
                st.rerun()
    else:
        st.caption("No matching ledger records found.")

# =========================================================================
# TAB 3: SHARED EXPENSES (CIRCLES & BILL ALLOCATIONS)
# =========================================================================
with tabs[2]:
    st.markdown("### Shared Expense Circles & Ledgers")
    
    if not groups:
        st.caption("No circles registered. Create a circle using the sidebar.")
    else:
        for g in groups:
            gid = g["group_id"]
            members = db.get_group_members(gid)
            member_ids = [m["user_id"] for m in members]
            shared_bills = db.get_group_shared_expenses(gid)
            total_shared_vol = sum(sb["amount"] for sb in shared_bills)

            with st.expander(f"{g['group_name']} &bull; {len(members)} Members &bull; Volume: {fmt(total_shared_vol)}", expanded=(active_group_id == gid or len(groups) == 1)):
                c_m1, c_m2 = st.columns([3, 1])
                with c_m1:
                    if members:
                        chips_html = "".join([f"<span class='badge badge-gray' style='margin-right:6px;'>{m['name']}</span>" for m in members])
                        st.markdown(f"**Circle Roster:** {chips_html}", unsafe_allow_html=True)
                    else:
                        st.caption("No members assigned to circle.")

                    col_add, col_rm = st.columns(2)
                    with col_add:
                        eligible_to_add = [u for u in users if u["user_id"] not in member_ids]
                        if eligible_to_add:
                            add_options = [f"{u['name']} (#{u['user_id']})" for u in eligible_to_add]
                            sel_to_add = st.selectbox("Add Member", options=["-- Select --"] + add_options, key=f"add_mem_{gid}")
                            if st.button("Add Member", key=f"btn_add_{gid}") and sel_to_add != "-- Select --":
                                to_add_id = int(sel_to_add.split("#")[1].rstrip(")"))
                                db.add_member_to_group(gid, to_add_id)
                                st.success("Member added.")
                                st.rerun()
                    with col_rm:
                        if members:
                            rm_options = [f"{m['name']} (#{m['user_id']})" for m in members]
                            sel_to_rm = st.selectbox("Remove Member", options=["-- Select --"] + rm_options, key=f"rm_mem_{gid}")
                            if st.button("Remove Member", key=f"btn_rm_{gid}") and sel_to_rm != "-- Select --":
                                to_rm_id = int(sel_to_rm.split("#")[1].rstrip(")"))
                                db.remove_member_from_group(gid, to_rm_id)
                                st.success("Member removed.")
                                st.rerun()

                with c_m2:
                    if st.button("Delete Circle", key=f"del_circle_{gid}"):
                        db.delete_group(gid)
                        st.success(f"Circle '{g['group_name']}' deleted.")
                        st.rerun()

                st.write("")
                st.markdown(f"##### Group Bill Records ({len(shared_bills)})")
                if shared_bills:
                    for sb in shared_bills:
                        with st.container(border=True):
                            s_head1, s_head2, s_head3 = st.columns([3, 1, 1], vertical_alignment="center")
                            with s_head1:
                                st.markdown(f"**{sb['description']}** &bull; <span style='font-family:monospace; font-weight:700;'>{fmt(sb['amount'])}</span>", unsafe_allow_html=True)
                                st.caption(f"Paid by {sb['payer_name']} on {sb['date']} &bull; Category: {sb.get('category', 'General')}")
                            with s_head2:
                                splits = db.get_splits_for_expense(sb["shared_id"])
                                paid_count = sum(1 for s in splits if s["is_paid"])
                                st.caption(f"Settlement: **{paid_count}/{len(splits)} paid**")
                            with s_head3:
                                if st.button("Delete Bill", key=f"del_sb_{sb['shared_id']}"):
                                    db.delete_shared_expense(sb["shared_id"])
                                    st.success("Record deleted.")
                                    st.rerun()

                            for s in splits:
                                sp1, sp2, sp3 = st.columns([3, 1, 1], vertical_alignment="center")
                                is_payer = s["user_id"] == sb["payer_id"]
                                payer_note = " (Payer share)" if is_payer else ""
                                with sp1:
                                    st.caption(f"&bull; {s['user_name']}: {fmt(s['amount_owed'])}{payer_note}")
                                with sp2:
                                    if s["is_paid"]:
                                        st.markdown("<span class='badge badge-green'>Paid</span>", unsafe_allow_html=True)
                                    else:
                                        st.markdown("<span class='badge badge-red'>Unpaid</span>", unsafe_allow_html=True)
                                with sp3:
                                    if not s["is_paid"]:
                                        if st.button("Mark Paid", key=f"mk_paid_{s['split_id']}"):
                                            db.mark_split_paid(s["split_id"], True)
                                            st.rerun()
                                    else:
                                        if st.button("Mark Unpaid", key=f"mk_unpaid_{s['split_id']}"):
                                            db.mark_split_paid(s["split_id"], False)
                                            st.rerun()
                else:
                    st.caption("No shared expenses recorded in this circle.")

# =========================================================================
# TAB 4: SETTLEMENTS (DEBT SIMPLIFICATION ENGINE)
# =========================================================================
with tabs[3]:
    st.markdown("### Debt Simplification & Settlement Operations")
    st.caption("Greedy minimum cash-flow optimization resolves multi-party debts into the minimal direct transfer instructions.")

    bal_details = logic.compute_balances_detailed(active_group_id)
    if not bal_details:
        st.caption("No outstanding balances in selected scope.")
    else:
        col_bal_t, col_bal_c = st.columns([1, 1])
        with col_bal_t:
            st.markdown("##### Net Balances Ledger")
            df_b = pd.DataFrame(bal_details)
            df_b_display = df_b[["name", "balance", "status"]].copy()
            df_b_display["balance"] = df_b_display["balance"].apply(lambda x: fmt(x))
            df_b_display.rename(columns={"name": "Member", "balance": "Net Balance", "status": "Position"}, inplace=True)
            st.dataframe(df_b_display, width="stretch", hide_index=True)

        with col_bal_c:
            st.markdown("##### Net Position Visualization")
            bar_colors = ["#16A34A" if b["balance"] > 0 else ("#DC2626" if b["balance"] < 0 else "#475569") for b in bal_details]
            fig_bar = go.Figure(go.Bar(
                x=[b["name"] for b in bal_details],
                y=[b["balance"] for b in bal_details],
                marker_color=bar_colors,
                text=[fmt(b["balance"]) for b in bal_details],
                textposition="outside"
            ))
            fig_bar.update_layout(
                template="plotly_dark",
                margin=dict(t=25, b=10, l=10, r=10),
                height=220,
                font=dict(family="Plus Jakarta Sans, sans-serif", size=11),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                yaxis=dict(title=f"Net Balance ({CURR})", gridcolor="rgba(255,255,255,0.05)")
            )
            st.plotly_chart(fig_bar, width="stretch")

        st.divider()

        debts = logic.get_who_owes_whom(active_group_id)
        st.markdown(f"##### Optimized Settlement Plan ({len(debts)} Direct Transfers Required)")

        if debts:
            for idx, d in enumerate(debts):
                with st.container(border=True):
                    dc1, dc2, dc3 = st.columns([3, 2, 1], vertical_alignment="center")
                    with dc1:
                        st.markdown(f"""
                            <div style="font-weight:700;">
                                <span style="color:#EF4444;">{d['from_name']}</span>
                                <span style="color:#64748B; margin: 0 6px;">&rarr;</span>
                                <span style="color:#16A34A;">{d['to_name']}</span>
                                <span style="font-family:'JetBrains Mono',monospace; color:#F8FAFC; margin-left:10px;">{fmt(d['amount'])}</span>
                            </div>
                        """, unsafe_allow_html=True)
                    with dc2:
                        st.caption(f"Clears balance obligation between parties")
                    with dc3:
                        if st.button("Settle Transfer", key=f"btn_quick_settle_{idx}", width="stretch", type="primary"):
                            quick_settle_modal(
                                d["from_user"],
                                d["to_user"],
                                d["amount"],
                                f"Settlement payment ({d['from_name']} -> {d['to_name']})",
                                active_group_id
                            )

            try:
                sankey_data = logic.get_sankey_debt_data(active_group_id, curr=CURR)
            except Exception:
                try:
                    sankey_data = logic.get_sankey_debt_data(active_group_id)
                except Exception:
                    sankey_data = None

            if sankey_data:
                with st.expander("Directional Debt Flow Graph (Sankey)", expanded=False):
                    fig_sankey = go.Figure(data=[go.Sankey(
                        node=dict(pad=15, thickness=18, line=dict(color="#0A0D14", width=0.5), label=sankey_data["nodes"], color="#2563EB"),
                        link=dict(source=sankey_data["sources"], target=sankey_data["targets"], value=sankey_data["values"], label=sankey_data["labels"], color="rgba(37, 99, 235, 0.18)")
                    )])
                    fig_sankey.update_layout(template="plotly_dark", height=260, margin=dict(t=20, b=10, l=10, r=10), paper_bgcolor="rgba(0,0,0,0)")
                    st.plotly_chart(fig_sankey, width="stretch")
        else:
            st.markdown("<span class='badge badge-green'>All accounts balanced & settled</span>", unsafe_allow_html=True)

        # Past Settlement Audit Log
        past_settlements = db.get_settlements(active_group_id)
        if past_settlements:
            with st.expander(f"Settlement Transaction Audit Trail ({len(past_settlements)} records)", expanded=False):
                df_st = pd.DataFrame(past_settlements)
                df_st_disp = df_st[["settlement_id", "date", "from_name", "to_name", "amount", "payment_method", "note"]].copy()
                df_st_disp["amount"] = df_st_disp["amount"].apply(lambda x: fmt(x))
                df_st_disp.rename(columns={"settlement_id": "ID", "date": "Date", "from_name": "Payer", "to_name": "Receiver", "amount": "Amount", "payment_method": "Instrument", "note": "Reference"}, inplace=True)
                st.dataframe(df_st_disp, width="stretch", hide_index=True)

# =========================================================================
# TAB 5: ANALYTICS (TRENDS & PACING TELEMETRY)
# =========================================================================
with tabs[4]:
    st.markdown("### Analytics & Multi-Month Telemetry")

    mom = logic.get_month_over_month_metrics(active_user_id)
    mom_c1, mom_c2, mom_c3 = st.columns(3)
    with mom_c1:
        exp_delta = f"{'+' if mom['expense_diff'] >= 0 else ''}{fmt(mom['expense_diff'])} ({mom['expense_change_pct']}%)"
        st.metric("Expenses vs Previous Month", fmt(mom["current_expense"]), delta=exp_delta, delta_color="inverse")
    with mom_c2:
        inc_delta = f"{'+' if mom['income_diff'] >= 0 else ''}{fmt(mom['income_diff'])} ({mom['income_change_pct']}%)"
        st.metric("Inflows vs Previous Month", fmt(mom["current_income"]), delta=inc_delta, delta_color="normal")
    with mom_c3:
        st.metric("Established Monthly Cap", fmt(active_user.get("monthly_budget", 0)))

    st.divider()

    st.markdown("##### Category Budget Allocator")
    cat_budgets = logic.get_category_budget_status(active_user_id, cur_month)
    cb_col_left, cb_col_right = st.columns([1, 1])
    with cb_col_left:
        with st.form("form_set_cat_budget"):
            st.markdown("**Establish Spending Cap**")
            set_cat = st.selectbox("Category", [
                "Food & Dining", "Housing & Rent", "Groceries", "Utilities",
                "Transportation", "Entertainment", "Health & Medical", "Shopping", "Travel", "Other"
            ])
            set_limit = st.number_input(f"Monthly Cap ({CURR})", min_value=10.0, value=300.0, step=25.0)
            if st.form_submit_button("Save Cap", width="stretch"):
                db.set_category_budget(active_user_id, set_cat, float(set_limit))
                st.success(f"Cap of {fmt(set_limit)} set for {set_cat}")
                st.rerun()

    with cb_col_right:
        st.markdown("**Active Category Caps**")
        if cat_budgets:
            df_cb = pd.DataFrame(cat_budgets)
            df_cb_disp = df_cb[["category", "budget", "spent", "remaining", "pct_used"]].copy()
            df_cb_disp["budget"] = df_cb_disp["budget"].apply(lambda x: fmt(x) if x > 0 else "None")
            df_cb_disp["spent"] = df_cb_disp["spent"].apply(lambda x: fmt(x))
            df_cb_disp["remaining"] = df_cb_disp["remaining"].apply(lambda x: fmt(x) if x is not None else "N/A")
            df_cb_disp["pct_used"] = df_cb_disp["pct_used"].apply(lambda x: f"{x}%" if x is not None else "N/A")
            df_cb_disp.rename(columns={"category": "Category", "budget": "Limit", "spent": "Spent", "remaining": "Remaining", "pct_used": "Utilized"}, inplace=True)
            st.dataframe(df_cb_disp, width="stretch", hide_index=True)
        else:
            st.caption("No category allocations active.")

    st.divider()

    st.markdown("##### Multi-Month Revenue & Expenditure Pacing")
    m_spend = db.get_monthly_spending(active_user_id)
    m_income = db.get_monthly_income(active_user_id)

    if m_spend or m_income:
        df_ms = pd.DataFrame(m_spend) if m_spend else pd.DataFrame(columns=["month", "total"])
        df_mi = pd.DataFrame(m_income) if m_income else pd.DataFrame(columns=["month", "total"])
        df_ms.rename(columns={"total": "Expenses"}, inplace=True)
        df_mi.rename(columns={"total": "Income"}, inplace=True)
        merged_trends = pd.merge(df_ms, df_mi, on="month", how="outer").fillna(0).sort_values("month")

        fig_trend = go.Figure()
        fig_trend.add_trace(go.Bar(x=merged_trends["month"], y=merged_trends["Expenses"], name="Expenditure", marker_color="#DC2626"))
        fig_trend.add_trace(go.Bar(x=merged_trends["month"], y=merged_trends["Income"], name="Inflow", marker_color="#16A34A"))
        fig_trend.update_layout(
            template="plotly_dark",
            barmode="group",
            height=280,
            margin=dict(t=20, b=20, l=10, r=10),
            yaxis_title=f"Amount ({CURR})",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            yaxis=dict(gridcolor="rgba(255,255,255,0.05)")
        )
        st.plotly_chart(fig_trend, width="stretch")
    else:
        st.caption("Multi-month data will appear as records accumulate across dates.")

# =========================================================================
# TAB 6: EMAIL REMINDERS (ACCOUNTS RECEIVABLE ENGINE)
# =========================================================================
with tabs[5]:
    st.markdown("### Accounts Receivable & Email Statements")
    st.caption("Automated generation and dispatch of formal debt settlement statements via SMTP mail.")

    unpaid_splits_all = logic.get_unpaid_splits(active_group_id)

    ctrl1, ctrl2, ctrl3 = st.columns([2, 2, 2], vertical_alignment="center")
    with ctrl1:
        overdue_days_setting = st.slider("Overdue Threshold (Days)", min_value=1, max_value=30, value=3)
    with ctrl2:
        is_dry_run_mode = st.toggle("Simulation Mode (Dry-Run)", value=True, help="Simulate email dispatch safely without transmitting live emails.")
    with ctrl3:
        mode_badge = "<span class='badge badge-amber'>Simulation Mode</span>" if is_dry_run_mode else "<span class='badge badge-green'>Live SMTP Mode</span>"
        st.markdown(f"<div style='text-align:right;'>{mode_badge}</div>", unsafe_allow_html=True)

    cutoff_date = (datetime.now() - timedelta(days=overdue_days_setting)).strftime("%Y-%m-%d")
    overdue_splits = [s for s in unpaid_splits_all if s["date"] <= cutoff_date]
    total_overdue_amt = sum(s["amount_owed"] for s in overdue_splits)
    ready_email_count = sum(1 for s in overdue_splits if s.get("debtor_email"))

    # Reminder KPIs Bar
    rk1, rk2, rk3, rk4 = st.columns(4)
    with rk1:
        st.markdown(f"""
            <div class="metric-strip-card">
                <div class="metric-label-txt">Overdue Items</div>
                <div class="metric-val-txt">{len(overdue_splits)}</div>
                <div class="metric-sub-txt">&gt; {overdue_days_setting} days outstanding</div>
            </div>
        """, unsafe_allow_html=True)
    with rk2:
        st.markdown(f"""
            <div class="metric-strip-card">
                <div class="metric-label-txt">Outstanding Balance</div>
                <div class="metric-val-txt txt-rose">{fmt(total_overdue_amt)}</div>
                <div class="metric-sub-txt">Receivable volume</div>
            </div>
        """, unsafe_allow_html=True)
    with rk3:
        st.markdown(f"""
            <div class="metric-strip-card">
                <div class="metric-label-txt">Deliverable Contacts</div>
                <div class="metric-val-txt txt-sky">{ready_email_count} / {len(overdue_splits)}</div>
                <div class="metric-sub-txt">Valid email addresses</div>
            </div>
        """, unsafe_allow_html=True)
    with rk4:
        st.markdown(f"""
            <div class="metric-strip-card">
                <div class="metric-label-txt">Transmission Protocol</div>
                <div class="metric-val-txt">SMTP / TLS</div>
                <div class="metric-sub-txt">Multipart HTML + Plain text</div>
            </div>
        """, unsafe_allow_html=True)

    st.write("")

    st.markdown(f"##### Outstanding Receivables Awaiting Settlement ({len(overdue_splits)})")

    if overdue_splits:
        for idx, s in enumerate(overdue_splits):
            with st.container(border=True):
                r_c1, r_c2, r_c3, r_c4 = st.columns([4, 2, 2, 2], vertical_alignment="center")
                
                with r_c1:
                    debtor_mail = s.get("debtor_email")
                    mail_badge = f"<span class='badge badge-blue' style='font-family:monospace;'>{debtor_mail}</span>" if debtor_mail else "<span class='badge badge-amber'>Missing Email</span>"
                    st.markdown(f"""
                        <div style="font-weight:700; color:#F8FAFC;">
                            {s['debtor_name']} owes <span style="font-family:'JetBrains Mono',monospace; color:#EF4444;">{fmt(s['amount_owed'])}</span> to {s['payer_name']}
                            &bull; {mail_badge}
                        </div>
                    """, unsafe_allow_html=True)
                    st.caption(f"Bill: '{s['description']}' ({s['date']}) &bull; Circle: {s.get('group_name', 'General')}")

                with r_c2:
                    if st.button("Preview Statement", key=f"btn_preview_mail_{s['split_id']}", width="stretch"):
                        preview_email_modal(s)

                with r_c3:
                    if st.button("Send Reminder", key=f"btn_send_mail_{s['split_id']}", width="stretch", type="primary", disabled=not s.get("debtor_email")):
                        res = reminders.send_single_split_reminder(
                            s,
                            is_dry_run=is_dry_run_mode,
                            smtp_config=st.session_state["smtp_config"],
                            curr=CURR
                        )
                        if res["success"]:
                            st.toast(res['msg'])
                            st.success(res['msg'])
                        else:
                            st.error(res['msg'])

                with r_c4:
                    if st.button("Mark Paid", key=f"nudge_mark_paid_{s['split_id']}", width="stretch"):
                        db.mark_split_paid(s["split_id"], True)
                        st.success("Split marked paid.")
                        st.rerun()

        st.divider()
        st.markdown("##### Batch Automated Dispatcher")
        
        col_disp1, col_disp2 = st.columns([3, 1], vertical_alignment="center")
        with col_disp1:
            st.caption(f"Trigger payment statement dispatch to all {ready_email_count} contactable debtors.")
        with col_disp2:
            if st.button("Dispatch All Reminders", type="primary", width="stretch"):
                results = reminders.send_gentle_reminders(
                    group_id=active_group_id,
                    overdue_days=overdue_days_setting,
                    is_dry_run=is_dry_run_mode,
                    smtp_config=st.session_state["smtp_config"],
                    curr=CURR
                )
                st.session_state["last_reminder_results"] = results
                st.success(results["message"])

        if st.session_state.get("last_reminder_results"):
            last_res = st.session_state["last_reminder_results"]
            with st.container(border=True):
                st.markdown("###### Dispatch Audit Log")
                for sent_item in last_res.get("sent", []):
                    icon = "Delivered" if sent_item["success"] else "Failed"
                    st.caption(f"[{icon}] To {sent_item['debtor']} ({sent_item['to']}): {sent_item['msg']}")

    else:
        st.markdown("<span class='badge badge-green'>No overdue splits beyond threshold.</span>", unsafe_allow_html=True)

    # SMTP Configuration
    st.divider()
    with st.expander("SMTP Delivery Settings & Connection Verification", expanded=False):
        st.caption("Configure standard SMTP credentials (TLS / SSL) for outbound financial notification delivery.")

        with st.form("form_smtp_config"):
            c_smtp1, c_smtp2, c_smtp3 = st.columns(3)
            with c_smtp1:
                cfg_host = st.text_input("SMTP Host", value=st.session_state["smtp_config"]["host"])
                cfg_port = st.number_input("SMTP Port", value=int(st.session_state["smtp_config"]["port"]), min_value=1, max_value=65535)
            with c_smtp2:
                cfg_user = st.text_input("SMTP Username / Email", value=st.session_state["smtp_config"]["user"], placeholder="user@domain.com")
                cfg_pass = st.text_input("SMTP App Password", value=st.session_state["smtp_config"]["pass"], type="password", placeholder="Password / Token")
            with c_smtp3:
                cfg_from = st.text_input("Sender Address", value=st.session_state["smtp_config"]["from_email"], placeholder="noreply@domain.com")
                test_recipient = st.text_input("Test Recipient", value=active_user.get("email") or "", placeholder="recipient@domain.com")

            c_btn_save, c_btn_test = st.columns([1, 1])
            with c_btn_save:
                save_smtp = st.form_submit_button("Save Credentials", type="secondary", width="stretch")
            with c_btn_test:
                test_smtp = st.form_submit_button("Test SMTP Authentication", type="primary", width="stretch")

            if save_smtp:
                st.session_state["smtp_config"] = {
                    "host": cfg_host.strip(),
                    "port": int(cfg_port),
                    "user": cfg_user.strip(),
                    "pass": cfg_pass.strip(),
                    "from_email": cfg_from.strip() or cfg_user.strip()
                }
                st.success("SMTP configuration saved into active session.")

            if test_smtp:
                temp_cfg = {
                    "host": cfg_host.strip(),
                    "port": int(cfg_port),
                    "user": cfg_user.strip(),
                    "pass": cfg_pass.strip(),
                    "from_email": cfg_from.strip() or cfg_user.strip()
                }
                st.session_state["smtp_config"] = temp_cfg
                ok, msg = reminders.test_smtp_connection(temp_cfg, test_to_email=test_recipient.strip() if test_recipient.strip() else None)
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)

    # Background Daily Automation (Cron)
    with st.expander("Headless Cron Automation Specification", expanded=False):
        st.markdown(f"""
            Execute daily headless reminder sweeps via server cron:
            ```bash
            # Daily execution at 09:00 UTC
            0 9 * * * cd /home/tanishagrawal/BudgetApp && /home/tanishagrawal/.local/bin/python3.11 reminders.py --live >> reminders.log 2>&1
            ```
            **Required Environment Variables:**
            ```bash
            export SMTP_HOST="smtp.gmail.com"
            export SMTP_PORT="587"
            export SMTP_USER="your-email@gmail.com"
            export SMTP_PASS="your-app-password"
            export FROM_EMAIL="your-email@gmail.com"
            ```
        """)

# =========================================================================
# TAB 7: DATA & EXPORT
# =========================================================================
with tabs[6]:
    st.markdown("### Ledger Data Records & CSV Export")
    st.caption("Generate immutable CSV snapshots of expenditure, revenue, and settlement ledgers.")

    exp_c1, exp_c2, exp_c3 = st.columns(3)
    
    with exp_c1:
        with st.container(border=True):
            st.markdown("##### Expenditures Ledger")
            all_e = db.get_all_expenses()
            st.caption(f"Volume: **{len(all_e)} records**")
            if all_e:
                csv_exp = pd.DataFrame(all_e).to_csv(index=False).encode('utf-8')
                st.download_button("Export CSV", data=csv_exp, file_name=f"expenditures_{cur_month}.csv", mime="text/csv", width="stretch")
            else:
                st.caption("No records available.")

    with exp_c2:
        with st.container(border=True):
            st.markdown("##### Inflow Revenue Ledger")
            all_inc = db.get_user_incomes()
            st.caption(f"Volume: **{len(all_inc)} records**")
            if all_inc:
                csv_inc = pd.DataFrame(all_inc).to_csv(index=False).encode('utf-8')
                st.download_button("Export CSV", data=csv_inc, file_name=f"inflows_{cur_month}.csv", mime="text/csv", width="stretch")
            else:
                st.caption("No records available.")

    with exp_c3:
        with st.container(border=True):
            st.markdown("##### Settlement Audit Ledger")
            all_settle = db.get_settlements()
            st.caption(f"Volume: **{len(all_settle)} records**")
            if all_settle:
                csv_stl = pd.DataFrame(all_settle).to_csv(index=False).encode('utf-8')
                st.download_button("Export CSV", data=csv_stl, file_name=f"settlements_{cur_month}.csv", mime="text/csv", width="stretch")
            else:
                st.caption("No records available.")

# Institutional Footer
st.divider()
st.markdown("""
    <div style="display:flex; justify-content:space-between; align-items:center; color:#64748B; font-size:0.74rem; padding:6px 0;">
        <div>Smart Budgeter &bull; Institutional Financial Command</div>
        <div>Python &bull; SQLite &bull; Plotly &bull; Streamlit</div>
    </div>
""", unsafe_allow_html=True)
