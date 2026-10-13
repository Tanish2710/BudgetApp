"""
app.py - Smart Budgeter & Debt-Splitter | Streamlit Financial Command Center
High-performance personal budgeting, Splitwise-style group bill splitting,
intelligent debt simplification, cash flow analytics, and multi-channel reminders.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date, timedelta
import os
import sys

# Ensure local imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import importlib
import database as db
import logic
import reminders
importlib.reload(db)
importlib.reload(logic)
importlib.reload(reminders)

# Initialize DB with migrations
db.init_db()

# --- Page Configuration ---
st.set_page_config(
    page_title="Smart Budgeter ✦ Debt-Splitter",
    page_icon="💸",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Session State Initialization ---
if "currency" not in st.session_state:
    st.session_state["currency"] = "₹"
if "settle_prefill" not in st.session_state:
    st.session_state["settle_prefill"] = None
if "selected_tab" not in st.session_state:
    st.session_state["selected_tab"] = "📊 Dashboard"

CURR = st.session_state["currency"]

# --- Custom Modern CSS Injection ---
st.markdown("""
<style>
    /* Global modern typography & base styles */
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200');
    
    html, body, .stApp {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        -webkit-font-smoothing: antialiased;
    }

    /* Apply typography to text elements while strictly exempting icons */
    p, h1, h2, h3, h4, h5, h6, label, input, select, textarea,
    [data-testid="stMarkdownContainer"] *:not([data-testid="stIconMaterial"]):not([class*="material-symbols"]):not([class*="MaterialSymbols"]) {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }

    /* Explicitly protect Material Icons so ligatures render as icons instead of raw text */
    [data-testid="stIconMaterial"],
    [data-testid="stIconCustom"],
    .material-symbols-rounded,
    .material-symbols-outlined,
    [class*="material-symbols"],
    [class*="MaterialSymbols"],
    span[data-testid="stIconMaterial"] {
        font-family: 'Material Symbols Rounded', 'Material Symbols Outlined' !important;
        font-weight: normal !important;
        font-style: normal !important;
        font-size: 1.25rem;
        line-height: 1 !important;
        letter-spacing: normal !important;
        text-transform: none !important;
        display: inline-block !important;
        white-space: nowrap !important;
        word-wrap: normal !important;
        direction: ltr !important;
        -webkit-font-feature-settings: 'liga' 1 !important;
        font-feature-settings: 'liga' 1 !important;
        -webkit-font-smoothing: antialiased !important;
    }

    header[data-testid="stHeader"] {
        background: rgba(15, 23, 42, 0.85) !important;
        backdrop-filter: blur(12px) !important;
        z-index: 99999 !important;
    }

    .block-container {
        padding-top: 4.2rem !important;
        padding-bottom: 2.5rem !important;
        max-width: 1400px !important;
    }

    /* Header hero styling */
    .hero-banner {
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.75) 0%, rgba(15, 23, 42, 0.95) 100%);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-top: 2px solid rgba(99, 102, 241, 0.6);
        border-radius: 16px;
        padding: 22px 26px;
        margin-bottom: 22px;
        backdrop-filter: blur(16px);
        box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.4);
    }
    
    .hero-title {
        font-size: 1.65rem;
        font-weight: 800;
        letter-spacing: -0.025em;
        margin: 0;
        background: linear-gradient(120deg, #38BDF8 0%, #818CF8 50%, #C084FC 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    .hero-subtitle {
        color: #94A3B8;
        font-size: 0.9rem;
        margin-top: 6px;
        margin-bottom: 0px;
    }

    /* Metric cards */
    .metric-card {
        background: linear-gradient(180deg, rgba(30, 41, 59, 0.55) 0%, rgba(15, 23, 42, 0.65) 100%);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 14px;
        padding: 18px 20px;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
        height: 100%;
        min-height: 124px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        position: relative;
        overflow: hidden;
    }
    .metric-card:hover {
        border-color: rgba(99, 102, 241, 0.5);
        transform: translateY(-2px);
        box-shadow: 0 8px 24px -4px rgba(99, 102, 241, 0.2);
    }
    .metric-card-positive { border-top: 3px solid #10B981 !important; }
    .metric-card-negative { border-top: 3px solid #F43F5E !important; }
    .metric-card-neutral  { border-top: 3px solid #38BDF8 !important; }
    .metric-card-purple   { border-top: 3px solid #A855F7 !important; }

    .metric-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 6px;
    }
    .metric-label {
        font-size: 0.76rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: #94A3B8;
    }
    .metric-icon {
        font-size: 1.15rem;
        opacity: 0.85;
    }
    .metric-val {
        font-size: 1.7rem;
        font-weight: 800;
        color: #F8FAFC;
        line-height: 1.15;
        letter-spacing: -0.02em;
    }
    .metric-sub {
        font-size: 0.82rem;
        color: #64748B;
        margin-top: 6px;
    }
    .val-positive { color: #34D399 !important; }
    .val-negative { color: #FB7185 !important; }
    .val-neutral  { color: #38BDF8 !important; }
    
    /* Status Pills */
    .pill {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        padding: 4px 11px;
        border-radius: 9999px;
        font-size: 0.76rem;
        font-weight: 600;
        margin-right: 6px;
        letter-spacing: 0.01em;
    }
    .pill-green { background: rgba(16, 185, 129, 0.15); color: #34D399; border: 1px solid rgba(16, 185, 129, 0.35); }
    .pill-red { background: rgba(244, 63, 94, 0.15); color: #FB7185; border: 1px solid rgba(244, 63, 94, 0.35); }
    .pill-blue { background: rgba(56, 189, 248, 0.15); color: #38BDF8; border: 1px solid rgba(56, 189, 248, 0.35); }
    .pill-purple { background: rgba(168, 85, 247, 0.15); color: #C084FC; border: 1px solid rgba(168, 85, 247, 0.35); }
    .pill-amber { background: rgba(245, 158, 11, 0.15); color: #FBBF24; border: 1px solid rgba(245, 158, 11, 0.35); }

    /* Modern Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 6px;
        background: rgba(15, 23, 42, 0.7);
        padding: 5px 6px;
        border-radius: 12px;
        border: 1px solid rgba(255, 255, 255, 0.08);
        margin-bottom: 24px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 40px;
        padding: 0 16px;
        background: transparent;
        border-radius: 8px;
        border: none;
        color: #94A3B8;
        font-weight: 600;
        font-size: 0.88rem;
        transition: all 0.18s ease;
    }
    .stTabs [data-baseweb="tab"]:hover {
        background: rgba(255, 255, 255, 0.05);
        color: #F8FAFC;
    }
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background: rgba(99, 102, 241, 0.22);
        color: #818CF8;
        border: 1px solid rgba(99, 102, 241, 0.45);
        font-weight: 700;
        box-shadow: 0 2px 10px rgba(99, 102, 241, 0.2);
    }
    .stTabs [data-baseweb="tab-highlight"],
    .stTabs [data-baseweb="tab-border"] {
        display: none !important;
    }

    /* Debt transfer cards */
    .debt-card {
        background: rgba(15, 23, 42, 0.75);
        border: 1px solid rgba(255, 255, 255, 0.09);
        border-radius: 12px;
        padding: 14px 18px;
        margin-bottom: 10px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        transition: all 0.2s ease;
    }
    .debt-card:hover {
        border-color: rgba(99, 102, 241, 0.35);
        background: rgba(30, 41, 59, 0.6);
    }
    
    /* Button tweaks */
    div.stButton > button {
        border-radius: 9px !important;
        font-weight: 600 !important;
        transition: all 0.2s ease !important;
    }
    div.stButton > button[kind="primary"],
    div.stButton > button[data-testid="stBaseButton-primary"] {
        background: linear-gradient(135deg, #6366F1 0%, #4F46E5 100%) !important;
        border: 1px solid rgba(255, 255, 255, 0.15) !important;
        box-shadow: 0 4px 12px rgba(79, 70, 229, 0.3) !important;
    }
    div.stButton > button[kind="primary"]:hover,
    div.stButton > button[data-testid="stBaseButton-primary"]:hover {
        background: linear-gradient(135deg, #818CF8 0%, #6366F1 100%) !important;
        box-shadow: 0 6px 16px rgba(79, 70, 229, 0.45) !important;
        transform: translateY(-1px);
    }

    /* Custom progress bar */
    div[data-testid="stProgress"] > div > div > div > div {
        background: linear-gradient(90deg, #6366F1 0%, #38BDF8 100%) !important;
        border-radius: 9999px !important;
    }

    /* Dataframe wrapper */
    div[data-testid="stDataFrame"] {
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 12px !important;
        overflow: hidden !important;
    }

    /* Three-dots menu button styling & alignment */
    .st-key-three_dots_menu {
        display: flex !important;
        justify-content: flex-end !important;
        align-items: center !important;
        margin-left: auto !important;
    }
    .st-key-three_dots_menu div[data-testid="stPopover"] {
        display: flex !important;
        justify-content: flex-end !important;
        width: 100% !important;
    }
    .st-key-three_dots_menu div[data-testid="stPopover"] button {
        background: rgba(30, 41, 59, 0.85) !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
        border-radius: 8px !important;
        font-size: 1.45rem !important;
        font-weight: 900 !important;
        color: #F8FAFC !important;
        height: 38px !important;
        min-height: 38px !important;
        width: 42px !important;
        min-width: 42px !important;
        padding: 0 !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25) !important;
        transition: all 0.2s ease !important;
    }
    .st-key-three_dots_menu div[data-testid="stPopover"] button:hover {
        background: rgba(99, 102, 241, 0.4) !important;
        border-color: rgba(99, 102, 241, 0.8) !important;
        color: #38BDF8 !important;
    }
    /* Hide the default down chevron from st.popover to render clean three-dots ⋮ */
    .st-key-three_dots_menu div[data-testid="stPopover"] button [data-testid="stIconMaterial"],
    .st-key-three_dots_menu div[data-testid="stPopover"] button svg {
        display: none !important;
    }

    /* Popover popup dropdown body styling */
    div[data-testid="stPopoverBody"] {
        max-height: 85vh !important;
        overflow-y: auto !important;
        box-shadow: 0 16px 36px rgba(0, 0, 0, 0.65) !important;
        border: 1px solid rgba(255, 255, 255, 0.16) !important;
        border-radius: 14px !important;
        background: #1E293B !important;
    }

    /* Hide intrusive "Press enter to submit form" / "Press Enter to apply" helper text */
    [data-testid="InputInstructions"],
    div[data-testid="InputInstructions"],
    .stTextInput [data-testid="InputInstructions"],
    .stNumberInput [data-testid="InputInstructions"],
    .stTextArea [data-testid="InputInstructions"],
    .stDateInput [data-testid="InputInstructions"],
    .stTimeInput [data-testid="InputInstructions"],
    div[data-testid*="InputInstructions"] {
        display: none !important;
        visibility: hidden !important;
        opacity: 0 !important;
        height: 0 !important;
        width: 0 !important;
        padding: 0 !important;
        margin: 0 !important;
        pointer-events: none !important;
    }

    /* Hide default footer */
    footer {
        visibility: hidden !important;
        display: none !important;
    }
</style>
""", unsafe_allow_html=True)

# Helper to format money
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

# --- Sidebar Controls ---
with st.sidebar:
    st.markdown("""
        <div style="display:flex; align-items:center; gap:10px; margin-bottom:12px;">
            <div style="font-size: 2rem;">💸</div>
            <div>
                <div style="font-weight: 800; font-size: 1.15rem; color: #F8FAFC;">Smart Budgeter</div>
                <div style="font-size: 0.72rem; color: #38BDF8; font-weight: 600; letter-spacing: 0.05em;">DEBT-SPLITTER PRO</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # Active Profile
    st.markdown("##### 👤 Active Profile")
    if users:
        user_options = list(user_name_to_id.keys())
        default_idx = 0
        active_user_label = st.selectbox("Select Profile", options=user_options, index=default_idx, label_visibility="collapsed")
        active_user_id = user_name_to_id[active_user_label]
        active_user = user_map[active_user_id]
    else:
        active_user_id = None
        active_user = None
        st.warning("No users available.")

    # Active Circle Filter
    st.markdown("##### 👥 Circle Filter")
    circle_options = ["🌐 All Circles"] + list(group_name_to_id.keys())
    active_circle_label = st.selectbox("Filter Circle", options=circle_options, label_visibility="collapsed")
    active_group_id = group_name_to_id[active_circle_label] if active_circle_label != "🌐 All Circles" else None

    st.divider()

    # Quick Add Section
    st.markdown("##### ⚡ Quick Create")
    with st.expander("➕ New User"):
        with st.form("sidebar_new_user"):
            nu_name = st.text_input("Full Name *", placeholder="e.g. Alex Morgan")
            nu_email = st.text_input("Email ID *", placeholder="alex@example.com")
            nu_phone = st.text_input("10-Digit Mobile Number *", placeholder="9876543210", max_chars=10)
            nu_budget = st.number_input(f"Monthly Budget ({CURR})", min_value=0.0, value=1500.0, step=50.0)
            if st.form_submit_button("Create User", width="stretch", type="primary"):
                is_valid, err_msg, clean_email, clean_phone = logic.validate_user_data(nu_name, nu_email, nu_phone)
                if not is_valid:
                    st.error(f"❌ {err_msg}")
                else:
                    try:
                        new_uid = db.create_user(nu_name.strip(), clean_email, clean_phone, float(nu_budget))
                        st.success(f"🎉 Added {nu_name.strip()} successfully!")
                        st.rerun()
                    except ValueError as e:
                        st.error(f"❌ {e}")
                    except Exception as e:
                        st.error(f"❌ Error creating user: {e}")

    with st.expander("🤝 New Circle / Group"):
        with st.form("sidebar_new_group"):
            ng_name = st.text_input("Circle Name", placeholder="e.g. Apartment 4B")
            if st.form_submit_button("Create Circle", width="stretch"):
                if ng_name.strip():
                    try:
                        new_gid = db.create_group(ng_name.strip())
                        if active_user_id:
                            db.add_member_to_group(new_gid, active_user_id)
                        st.success(f"Circle '{ng_name}' created!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
                else:
                    st.warning("Circle name required.")

    # Sidebar ends here cleanly (Demo and reset is exclusively in the three-dots menu)

# --- If No Users: Onboarding State ---
if not users:
    st.markdown("""
        <div class="hero-banner" style="text-align: center; padding: 40px 20px;">
            <div style="font-size: 3.5rem; margin-bottom: 12px;">💸</div>
            <div class="hero-title" style="font-size: 2.2rem;">Welcome to Smart Budgeter & Debt-Splitter</div>
            <p style="color: #94A3B8; max-width: 580px; margin: 12px auto 24px auto; font-size: 1.05rem;">
                Manage personal spending, split shared bills fairly across friend circles, minimize settlements with greedy debt simplification, and trigger automated reminders.
            </p>
        </div>
    """, unsafe_allow_html=True)
    c_btn1, c_btn2, c_btn3 = st.columns([1, 2, 1])
    with c_btn2:
        if st.button("🚀 Load Instant Demo Dataset (Recommended)", type="primary", width="stretch"):
            db.seed_comprehensive_demo_data(reset=True)
            st.success("Demo dataset initialized! Welcome aboard.")
            st.rerun()
    st.stop()

# --- Top Header & Executive KPI Summary ---
cur_month = datetime.now().strftime("%Y-%m")
cur_month_name = datetime.now().strftime("%B %Y")
bs = logic.get_budget_status(active_user_id, cur_month)
cf = logic.get_cash_flow_summary(active_user_id, cur_month)
user_balances = logic.compute_balances(active_group_id)
user_net_balance = user_balances.get(active_user_id, 0.0)

# Unpaid splits involving active user
all_unpaid = logic.get_unpaid_splits(active_group_id)
active_unpaid_owed_by_me = [s for s in all_unpaid if s["user_id"] == active_user_id]
active_unpaid_owed_to_me = [s for s in all_unpaid if s["payer_id"] == active_user_id]

# --- Top Navigation Bar (App Header on Left & Settings ⋮ on Far Top-Right) ---
top_left, top_right = st.columns([11, 1], vertical_alignment="center")

with top_left:
    st.markdown("""
        <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 2px;">
            <span style="font-size: 1.5rem;">💸</span>
            <span style="font-size: 1.35rem; font-weight: 800; color: #F8FAFC; letter-spacing: -0.015em;">Smart Budgeter</span>
            <span style="font-size: 0.72rem; font-weight: 700; color: #38BDF8; background: rgba(56, 189, 248, 0.12); padding: 2px 8px; border-radius: 6px; border: 1px solid rgba(56, 189, 248, 0.25); letter-spacing: 0.05em;">PRO</span>
        </div>
    """, unsafe_allow_html=True)

with top_right:
    with st.popover("⋮", help="Settings & Preferences", key="three_dots_menu", width="stretch"):
        st.markdown("### ⚙️ Settings")
        st.markdown("##### 💱 Currency")
        curr_options = ["₹", "$", "€", "£", "¥"]
        curr_idx = curr_options.index(st.session_state["currency"]) if st.session_state["currency"] in curr_options else 0
        new_curr = st.selectbox(
            "Default Currency",
            options=curr_options,
            index=curr_idx,
            help="Choose display currency for the dashboard (Default: ₹ Rupees)"
        )
        if new_curr != st.session_state["currency"]:
            st.session_state["currency"] = new_curr
            st.rerun()

        st.divider()
        st.markdown("##### 👤 Profile Settings")
        with st.form("popover_profile_form"):
            up_name = st.text_input("Full Name *", value=active_user["name"])
            up_email = st.text_input("Email ID *", value=active_user.get("email") or "")
            up_phone = st.text_input("10-Digit Mobile Number *", value=active_user.get("phone") or "", max_chars=10)
            up_budget = st.number_input(f"Monthly Budget ({CURR})", min_value=0.0, value=float(active_user.get("monthly_budget") or 1000.0), step=500.0)
            if st.form_submit_button("Save Profile", width="stretch", type="primary"):
                is_valid, err_msg, clean_email, clean_phone = logic.validate_user_data(up_name, up_email, up_phone, exclude_user_id=active_user_id)
                if not is_valid:
                    st.error(f"❌ {err_msg}")
                else:
                    try:
                        db.update_user(active_user_id, name=up_name, email=clean_email, phone=clean_phone, monthly_budget=float(up_budget))
                        st.success("🎉 Profile updated successfully!")
                        st.rerun()
                    except ValueError as e:
                        st.error(f"❌ {e}")
                    except Exception as e:
                        st.error(f"❌ Error updating profile: {e}")

        with st.expander("➕ Create New User"):
            with st.form("popover_create_user_form"):
                new_u_name = st.text_input("Full Name *", placeholder="e.g. Alex Morgan", key="pop_nu_name")
                new_u_email = st.text_input("Email ID *", placeholder="alex@example.com", key="pop_nu_email")
                new_u_phone = st.text_input("10-Digit Mobile Number *", placeholder="9876543210", max_chars=10, key="pop_nu_phone")
                new_u_budget = st.number_input(f"Monthly Budget ({CURR})", min_value=0.0, value=1500.0, step=100.0, key="pop_nu_budget")
                if st.form_submit_button("Create User", width="stretch", type="primary"):
                    is_valid, err_msg, clean_email, clean_phone = logic.validate_user_data(new_u_name, new_u_email, new_u_phone)
                    if not is_valid:
                        st.error(f"❌ {err_msg}")
                    else:
                        try:
                            db.create_user(new_u_name.strip(), clean_email, clean_phone, float(new_u_budget))
                            st.success(f"🎉 Added {new_u_name.strip()} successfully!")
                            st.rerun()
                        except ValueError as e:
                            st.error(f"❌ {e}")
                        except Exception as e:
                            st.error(f"❌ Error creating user: {e}")

        st.divider()
        st.markdown("##### 🛠️ Database & Demo")
        if st.button("🌱 Reload Demo Dataset", key="pop_seed_btn", width="stretch"):
            db.seed_comprehensive_demo_data(reset=True)
            st.success("Demo dataset reloaded!")
            st.rerun()
        if st.button("🧹 Clear All Data (Reset)", key="pop_clear_btn", width="stretch"):
            conn = db.get_db_connection()
            for t in ["splits", "shared_expenses", "settlements", "group_members", "groups", "category_budgets", "incomes", "expenses", "users"]:
                conn.execute(f"DROP TABLE IF EXISTS {t}")
            conn.commit()
            conn.close()
            db.init_db()
            st.rerun()

        st.divider()
        if st.button("🔄 Refresh Dashboard", key="pop_refresh_btn", width="stretch"):
            st.rerun()

# Full-width Hero Banner
st.markdown(f"""
    <div class="hero-banner">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 14px;">
            <div>
                <div class="hero-title">Financial Dashboard • {active_user['name']}</div>
                <div class="hero-subtitle">
                    Viewing <strong>{cur_month_name}</strong> • Circle: <strong>{active_circle_label}</strong>
                    {' • Email: ' + active_user['email'] if active_user.get('email') else ''}
                    {' • 📱 ' + active_user['phone'] if active_user.get('phone') else ''}
                </div>
            </div>
            <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">
                <span class="pill {'pill-green' if user_net_balance >= 0 else 'pill-red'}">
                    {'Net Credit: +' + fmt(user_net_balance) if user_net_balance >= 0 else 'Net Debt: ' + fmt(user_net_balance)}
                </span>
                <span class="pill pill-blue">
                    {len(active_unpaid_owed_by_me)} split(s) you owe
                </span>
            </div>
        </div>
    </div>
""", unsafe_allow_html=True)

st.write("")

# 4 Key Metrics Bar
kpi1, kpi2, kpi3, kpi4 = st.columns(4)

with kpi1:
    pct_used = bs["pct_used"]
    card_accent = "metric-card-positive" if pct_used < 75 else ("metric-card-neutral" if pct_used <= 90 else "metric-card-negative")
    status_class = "val-positive" if pct_used < 75 else ("val-neutral" if pct_used <= 90 else "val-negative")
    st.markdown(f"""
        <div class="metric-card {card_accent}">
            <div>
                <div class="metric-header">
                    <span class="metric-label">Monthly Spending</span>
                    <span class="metric-icon">💳</span>
                </div>
                <div class="metric-val {status_class}">{fmt(bs['spent'])}</div>
            </div>
            <div class="metric-sub">Budget: <strong>{fmt(bs['budget'])}</strong> ({pct_used}% used)</div>
        </div>
    """, unsafe_allow_html=True)

with kpi2:
    net_cf = cf["net_cashflow"]
    card_accent = "metric-card-positive" if net_cf >= 0 else "metric-card-negative"
    cf_class = "val-positive" if net_cf >= 0 else "val-negative"
    st.markdown(f"""
        <div class="metric-card {card_accent}">
            <div>
                <div class="metric-header">
                    <span class="metric-label">Net Cash Flow</span>
                    <span class="metric-icon">💹</span>
                </div>
                <div class="metric-val {cf_class}">{'+' if net_cf >= 0 else ''}{fmt(net_cf)}</div>
            </div>
            <div class="metric-sub">Income: <strong>{fmt(cf['total_income'])}</strong> • Savings: <strong>{cf['savings_rate']}%</strong></div>
        </div>
    """, unsafe_allow_html=True)

with kpi3:
    safe_daily = bs["safe_daily_spend"]
    pacing_tag = "On Track" if not bs["is_pacing_fast"] else "Fast Pacing ⚠️"
    card_accent = "metric-card-neutral" if not bs["is_pacing_fast"] else "metric-card-negative"
    st.markdown(f"""
        <div class="metric-card {card_accent}">
            <div>
                <div class="metric-header">
                    <span class="metric-label">Daily Safe Spend</span>
                    <span class="metric-icon">⏱️</span>
                </div>
                <div class="metric-val val-neutral">{fmt(safe_daily)} <span style="font-size:0.85rem; font-weight:500; color:#94A3B8;">/day</span></div>
            </div>
            <div class="metric-sub">{bs['days_remaining']} days left in month • {pacing_tag}</div>
        </div>
    """, unsafe_allow_html=True)

with kpi4:
    bal_class = "val-positive" if user_net_balance > 0 else ("val-negative" if user_net_balance < 0 else "val-neutral")
    bal_desc = "Owed to you (+)" if user_net_balance > 0 else ("You owe others (-)" if user_net_balance < 0 else "All Settled Up")
    card_accent = "metric-card-positive" if user_net_balance > 0 else ("metric-card-negative" if user_net_balance < 0 else "metric-card-neutral")
    st.markdown(f"""
        <div class="metric-card {card_accent}">
            <div>
                <div class="metric-header">
                    <span class="metric-label">Circle Split Balance</span>
                    <span class="metric-icon">🤝</span>
                </div>
                <div class="metric-val {bal_class}">{'+' if user_net_balance > 0 else ''}{fmt(user_net_balance)}</div>
            </div>
            <div class="metric-sub">{bal_desc}</div>
        </div>
    """, unsafe_allow_html=True)

st.write("")

# --- Dialogs ---
@st.dialog("⚡ Quick Settle Up")
def quick_settle_modal(from_uid, to_uid, amount, default_note="", group_id=None):
    from_name = user_map.get(from_uid, {}).get("name", f"User #{from_uid}")
    to_name = user_map.get(to_uid, {}).get("name", f"User #{to_uid}")
    st.markdown(f"""
        <div style="background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 12px; padding: 14px 18px; margin-bottom: 16px;">
            <div style="font-size: 0.8rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: #94A3B8; margin-bottom: 6px;">Settlement Transfer</div>
            <div style="display: flex; align-items: center; justify-content: space-between; font-size: 1.1rem; font-weight: 700;">
                <span style="color: #FB7185;">👤 {from_name}</span>
                <span style="color: #94A3B8; font-size: 1.2rem;">➔</span>
                <span style="color: #34D399;">👤 {to_name}</span>
            </div>
        </div>
    """, unsafe_allow_html=True)
    with st.form("dlg_settle_form"):
        s_amt = st.number_input(f"Amount ({CURR})", min_value=0.01, value=float(amount), step=1.0)
        s_meth = st.selectbox("Payment Method", ["UPI / GPay / PhonePe", "Cash", "Venmo", "Bank Transfer", "Zelle", "PayPal"])
        s_note = st.text_input("Note", value=default_note)
        if st.form_submit_button("✅ Record Settlement & Update Balances", type="primary", width="stretch"):
            db.add_settlement(from_uid, to_uid, float(s_amt), group_id, s_note, s_meth)
            st.session_state["settle_prefill"] = None
            st.success(f"Recorded settlement of {fmt(s_amt)}!")
            st.rerun()

# --- Main Navigation Tabs ---
tabs = st.tabs([
    "📊 Dashboard",
    "➕ Log & Manage",
    "👥 Circles & Bill Splits",
    "⚖️ Who Owes Whom",
    "📈 Trends & Insights",
    "🔔 Nudges & Automation",
    "📥 Data & Export"
])

# =========================================================================
# TAB 1: EXECUTIVE DASHBOARD
# =========================================================================
with tabs[0]:
    # Alert banner if user has urgent overdue splits
    if active_unpaid_owed_by_me:
        overdue_amt = sum(s["amount_owed"] for s in active_unpaid_owed_by_me)
        with st.container(border=True):
            col_al1, col_al2 = st.columns([3, 1])
            with col_al1:
                st.markdown(f"""
                    **⚠️ Pending Split Payments:** You have **{len(active_unpaid_owed_by_me)}** unpaid split(s) totaling **{fmt(overdue_amt)}**.
                """)
                unpaid_preview = ", ".join([f"{s['description']} ({fmt(s['amount_owed'])} to {s['payer_name']})" for s in active_unpaid_owed_by_me[:3]])
                st.caption(f"Items: {unpaid_preview}")
            with col_al2:
                if st.button("⚡ Settle Up Debts", key="dash_settle_btn", width="stretch", type="primary"):
                    first_d = active_unpaid_owed_by_me[0]
                    quick_settle_modal(
                        active_user_id,
                        first_d["payer_id"],
                        first_d["amount_owed"],
                        f"Payment for {first_d['description']}",
                        active_group_id
                    )

    # Row 1: Budget Pacing Meter & Category Distribution
    col_row1_left, col_row1_right = st.columns([3, 2])

    with col_row1_left:
        with st.container(border=True):
            st.markdown("#### 🎯 Monthly Budget Pacing & Health")
            
            # Progress bar for budget
            b_pct = min(1.0, max(0.0, bs["spent"] / bs["budget"])) if bs["budget"] > 0 else 0.0
            t_pct = min(1.0, max(0.0, bs["days_passed"] / bs["days_in_month"]))
            
            st.write(f"**Budget Utilization:** {bs['pct_used']}% of {fmt(bs['budget'])} spent")
            st.progress(b_pct)
            
            pcol1, pcol2, pcol3 = st.columns(3)
            with pcol1:
                st.caption(f"Spent: **{fmt(bs['spent'])}**")
            with pcol2:
                st.caption(f"Remaining: **{fmt(bs['remaining'])}**")
            with pcol3:
                st.caption(f"Projected Month-End: **{fmt(bs['projected_spend'])}**")

            # Pacing verdict
            if bs["remaining"] < 0:
                st.error(f"🚨 Over budget by {fmt(abs(bs['remaining']))}!")
            elif bs["is_pacing_fast"]:
                st.warning(f"⚠️ Pacing faster than month progress ({bs['pct_used']}% budget used vs {bs['time_elapsed_pct']}% of month passed).")
            else:
                st.success(f"✅ On track! Safe spending allowance is **{fmt(bs['safe_daily_spend'])}** per day.")

            # Category Budgets Progress Bars
            st.markdown("##### Category Budgets")
            cat_statuses = logic.get_category_budget_status(active_user_id, cur_month)
            budgeted_cats = [c for c in cat_statuses if c["has_budget"]]
            
            if budgeted_cats:
                for cb in budgeted_cats[:4]:
                    cb_pct = min(1.0, cb["spent"] / cb["budget"]) if cb["budget"] > 0 else 0.0
                    ccol1, ccol2 = st.columns([3, 1])
                    with ccol1:
                        st.write(f"**{cb['category']}**: {fmt(cb['spent'])} / {fmt(cb['budget'])}")
                        st.progress(cb_pct)
                    with ccol2:
                        rem_label = f"{fmt(cb['remaining'])} left" if cb['remaining'] >= 0 else f"{fmt(abs(cb['remaining']))} over"
                        color = "green" if cb['remaining'] >= 0 else "red"
                        st.markdown(f"<span style='color:{color}; font-size:0.85rem; font-weight:600;'>{rem_label}</span>", unsafe_allow_html=True)
            else:
                st.info("No category budgets set yet. Set spending limits per category in '📈 Trends & Insights' tab!")

    with col_row1_right:
        with st.container(border=True):
            st.markdown("#### 🍕 Spending by Category")
            cat_data = db.get_spending_by_category(active_user_id, cur_month)
            if cat_data:
                df_cat = pd.DataFrame(cat_data)
                fig_cat = px.pie(
                    df_cat,
                    names="category",
                    values="total",
                    hole=0.48,
                    color_discrete_sequence=px.colors.qualitative.Prism,
                    template="plotly_dark"
                )
                fig_cat.update_traces(textposition='inside', textinfo='percent+label', marker=dict(line=dict(color='#0F172A', width=2)))
                fig_cat.update_layout(
                    margin=dict(t=10, b=10, l=10, r=10),
                    showlegend=False,
                    height=280,
                    font=dict(family="Plus Jakarta Sans, sans-serif"),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)"
                )
                st.plotly_chart(fig_cat, width="stretch")
            else:
                st.info(f"No expenses logged for {cur_month_name} yet.")

    # Row 2: Recent Transactions & Activity Stream
    st.markdown("#### 🕒 Recent Transactions & Activity")
    user_recent_exp = db.get_expenses_filtered(user_id=active_user_id, limit=8)
    
    if user_recent_exp:
        recent_df = pd.DataFrame(user_recent_exp)
        recent_display = recent_df[["date", "category", "description", "payment_method", "amount"]].copy()
        recent_display["amount"] = recent_display["amount"].apply(lambda x: fmt(x))
        recent_display.rename(columns={
            "date": "Date",
            "category": "Category",
            "description": "Description",
            "payment_method": "Method",
            "amount": "Amount"
        }, inplace=True)
        st.dataframe(recent_display, width="stretch", hide_index=True)
    else:
        st.info("No transactions logged yet.")

# =========================================================================
# TAB 2: LOG & MANAGE TRANSACTIONS (Personal, Income, Shared Bill)
# =========================================================================
with tabs[1]:
    st.markdown("### ➕ Log Transaction & Cash Flow")

    log_type = st.segmented_control(
        "Transaction Type",
        options=["💸 Personal Expense", "💰 Income", "🤝 Shared Bill (Splitwise)"],
        default="💸 Personal Expense"
    )

    # 1. PERSONAL EXPENSE
    if log_type == "💸 Personal Expense":
        with st.container(border=True):
            st.markdown("##### Log Personal Expense")
            with st.form("form_personal_expense", clear_on_submit=True):
                col_e1, col_e2, col_e3 = st.columns(3)
                with col_e1:
                    user_opts = list(user_name_to_id.keys())
                    u_idx = list(user_name_to_id.values()).index(active_user_id) if active_user_id in user_name_to_id.values() else 0
                    exp_user_name = st.selectbox("User", options=user_opts, index=u_idx)
                    exp_amt = st.number_input(f"Amount ({CURR})", min_value=0.01, value=25.0, step=1.0)
                with col_e2:
                    exp_cat = st.selectbox("Category", [
                        "🍕 Food & Dining", "🏠 Housing & Rent", "🛒 Groceries", "⚡ Utilities",
                        "🚗 Transportation", "🎬 Entertainment", "💊 Health & Medical",
                        "🛍️ Shopping", "✈️ Travel", "📚 Education", "📦 Other"
                    ])
                    exp_date = st.date_input("Date", value=date.today())
                with col_e3:
                    exp_pmethod = st.selectbox("Payment Method", ["Card", "Credit Card", "Debit Card", "Cash", "UPI", "Bank Transfer", "Apple Pay / GPay"])
                    exp_desc = st.text_input("Description", placeholder="e.g. Lunch at Chipotle")

                exp_notes = st.text_input("Notes (Optional)", placeholder="e.g. #reimbursable, work lunch")

                if st.form_submit_button("➕ Save Expense", width="stretch", type="primary"):
                    uid = user_name_to_id[exp_user_name]
                    # clean category emoji
                    clean_cat = exp_cat.split(" ", 1)[1] if " " in exp_cat else exp_cat
                    eid = db.add_expense(uid, float(exp_amt), clean_cat, exp_date.isoformat(), exp_desc, exp_pmethod, exp_notes)
                    st.success(f"Expense of {fmt(exp_amt)} recorded successfully!")
                    st.rerun()

    # 2. INCOME
    elif log_type == "💰 Income":
        with st.container(border=True):
            st.markdown("##### Log Income Stream")
            with st.form("form_income", clear_on_submit=True):
                col_i1, col_i2, col_i3 = st.columns(3)
                with col_i1:
                    u_idx_inc = list(user_name_to_id.values()).index(active_user_id) if active_user_id in user_name_to_id.values() else 0
                    inc_user_name = st.selectbox("Recipient User", options=list(user_name_to_id.keys()), index=u_idx_inc)
                    inc_amt = st.number_input(f"Amount ({CURR})", min_value=0.01, value=1000.0, step=50.0)
                with col_i2:
                    inc_source = st.selectbox("Source", ["💼 Salary", "💻 Freelance / Contract", "📈 Investment / Dividends", "🎁 Gift", "💰 Reimbursement", "📦 Other"])
                    inc_date = st.date_input("Date Received", value=date.today())
                with col_i3:
                    inc_desc = st.text_input("Description", placeholder="e.g. Bi-weekly paycheck")

                if st.form_submit_button("➕ Record Income", width="stretch", type="primary"):
                    uid = user_name_to_id[inc_user_name]
                    clean_src = inc_source.split(" ", 1)[1] if " " in inc_source else inc_source
                    db.add_income(uid, float(inc_amt), clean_src, inc_date.isoformat(), inc_desc)
                    st.success(f"Income of {fmt(inc_amt)} added!")
                    st.rerun()

    # 3. SHARED BILL (SPLITWISE)
    elif log_type == "🤝 Shared Bill (Splitwise)":
        if not groups:
            st.warning("Please create a Circle / Group first using the sidebar to split bills!")
        else:
            with st.container(border=True):
                st.markdown("##### Split a Group Bill")
                
                # Shared bill header inputs
                col_s1, col_s2, col_s3 = st.columns(3)
                with col_s1:
                    sel_grp_name = st.selectbox("Circle", options=list(group_name_to_id.keys()), index=0)
                    chosen_gid = group_name_to_id[sel_grp_name]
                    grp_members = db.get_group_members(chosen_gid)
                    if not grp_members:
                        st.warning("⚠️ This circle has no members! Add members in the 'Circles & Bill Splits' tab before creating a shared bill.")
                        grp_member_map = {}
                        grp_member_names = []
                    else:
                        grp_member_map = {m["user_id"]: m["name"] for m in grp_members}
                        grp_member_names = [f"{m['name']} (#{m['user_id']})" for m in grp_members]

                if grp_members:
                    with col_s2:
                        payer_label = st.selectbox("Paid By", options=grp_member_names)
                        payer_uid = int(payer_label.split("#")[1].rstrip(")"))
                        bill_total = st.number_input(f"Total Amount ({CURR})", min_value=0.01, value=60.0, step=5.0)

                    with col_s3:
                        bill_desc = st.text_input("Description", placeholder="e.g. Costco groceries, Dinner")
                        bill_date = st.date_input("Expense Date", value=date.today())

                    bill_category = st.selectbox("Shared Category", ["General", "Groceries", "Food & Dining", "Rent & Housing", "Utilities", "Travel", "Entertainment"])

                    st.markdown("##### Split Mode")
                    split_mode = st.radio(
                        "How to divide?",
                        options=["Equal Split (=)", "Exact Dollar Amounts ($)", "Percentage Split (%)", "Shares / Parts (x)"],
                        horizontal=True
                    )

                    # Member multi-select
                    participating_members = st.multiselect(
                        "Include Group Members in Split",
                        options=grp_member_names,
                        default=grp_member_names
                    )

                    custom_splits_to_save = None
                    can_submit = True

                    if not participating_members:
                        st.warning("Please select at least 1 member to split among.")
                        can_submit = False
                    else:
                        part_uids = [int(n.split("#")[1].rstrip(")")) for n in participating_members]
                        n_parts = len(part_uids)

                        # Equal split
                        if split_mode == "Equal Split (=)":
                            per_head = round(bill_total / n_parts, 2)
                            st.info(f"Each of the {n_parts} selected members will owe **{fmt(per_head)}** (with penny remainder adjusted for first member).")
                            custom_splits_to_save = None

                        # Exact amounts
                        elif split_mode == "Exact Dollar Amounts ($)":
                            st.write("Specify exact dollar amount owed by each participant:")
                            cols = st.columns(min(4, n_parts))
                            exact_dict = {}
                            default_part = round(bill_total / n_parts, 2)
                            for idx, p_label in enumerate(participating_members):
                                u_id = int(p_label.split("#")[1].rstrip(")"))
                                col_idx = idx % min(4, n_parts)
                                with cols[col_idx]:
                                    exact_val = st.number_input(f"{grp_member_map[u_id]} ({CURR})", min_value=0.0, value=default_part, step=1.0, key=f"exact_{u_id}")
                                    exact_dict[u_id] = exact_val
                            
                            sum_exact = round(sum(exact_dict.values()), 2)
                            diff = round(bill_total - sum_exact, 2)
                            if abs(diff) > 0.01:
                                st.error(f"⚠️ Sum of splits ({fmt(sum_exact)}) does not equal total bill ({fmt(bill_total)}). Difference: {fmt(diff)}")
                                can_submit = False
                            else:
                                st.success(f"✅ Exact amounts perfectly balance to {fmt(bill_total)}.")
                                custom_splits_to_save = exact_dict

                        # Percentage
                        elif split_mode == "Percentage Split (%)":
                            st.write("Specify percentage share for each participant:")
                            cols = st.columns(min(4, n_parts))
                            pct_dict = {}
                            default_pct = round(100.0 / n_parts, 1)
                            for idx, p_label in enumerate(participating_members):
                                u_id = int(p_label.split("#")[1].rstrip(")"))
                                col_idx = idx % min(4, n_parts)
                                with cols[col_idx]:
                                    pct_val = st.number_input(f"{grp_member_map[u_id]} (%)", min_value=0.0, max_value=100.0, value=default_pct, step=1.0, key=f"pct_{u_id}")
                                    pct_dict[u_id] = pct_val
                            
                            sum_pct = round(sum(pct_dict.values()), 1)
                            if abs(sum_pct - 100.0) > 0.5:
                                st.error(f"⚠️ Total percentage is {sum_pct}%. It must sum to 100%.")
                                can_submit = False
                            else:
                                custom_splits_to_save = {uid: round((p / 100.0) * bill_total, 2) for uid, p in pct_dict.items()}
                                st.success(f"✅ Percentages sum to 100%. Computed shares: " + ", ".join([f"{grp_member_map[u]}: {fmt(a)}" for u, a in custom_splits_to_save.items()]))

                        # Shares
                        elif split_mode == "Shares / Parts (x)":
                            st.write("Specify relative shares (e.g. 1 share, 2 shares):")
                            cols = st.columns(min(4, n_parts))
                            shares_dict = {}
                            for idx, p_label in enumerate(participating_members):
                                u_id = int(p_label.split("#")[1].rstrip(")"))
                                col_idx = idx % min(4, n_parts)
                                with cols[col_idx]:
                                    sh_val = st.number_input(f"{grp_member_map[u_id]} (shares)", min_value=1, value=1, step=1, key=f"sh_{u_id}")
                                    shares_dict[u_id] = sh_val
                            
                            total_shares = sum(shares_dict.values())
                            custom_splits_to_save = {uid: round((sh / total_shares) * bill_total, 2) for uid, sh in shares_dict.items()}
                            st.success(f"Computed shares ({total_shares} total): " + ", ".join([f"{grp_member_map[u]}: {fmt(a)}" for u, a in custom_splits_to_save.items()]))

                    if st.button("🤝 Create Shared Bill & Split", type="primary", disabled=not can_submit, width="stretch"):
                        try:
                            if custom_splits_to_save:
                                sid = db.add_shared_expense(
                                    chosen_gid, payer_uid, float(bill_total), bill_desc or "Shared Bill",
                                    bill_date.isoformat(), custom_splits=custom_splits_to_save, category=bill_category
                                )
                            else:
                                sid = db.add_shared_expense(
                                    chosen_gid, payer_uid, float(bill_total), bill_desc or "Shared Bill",
                                    bill_date.isoformat(), split_among=part_uids, category=bill_category
                                )
                            st.success(f"Shared expense '{bill_desc}' created! Splits assigned.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error creating shared bill: {e}")

    # TRANSACTION SEARCH, FILTER & DELETE TABLE
    st.divider()
    st.markdown("### 📋 Transaction Ledger & Filter")

    tf_c1, tf_c2, tf_c3 = st.columns([2, 1, 1])
    with tf_c1:
        search_kw = st.text_input("🔍 Search description / category / notes", placeholder="Type to filter...")
    with tf_c2:
        cat_filter = st.selectbox("Filter Category", options=["All"] + sorted(list({e["category"] for e in db.get_all_expenses() if e.get("category")})))
    with tf_c3:
        user_filter_opt = st.selectbox("Filter User", options=["All Users"] + list(user_name_to_id.keys()))
        selected_uid_filter = user_name_to_id[user_filter_opt] if user_filter_opt != "All Users" else None

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
            "exp_id": "ID", "date": "Date", "user_name": "User", "category": "Category",
            "amount": "Amount", "payment_method": "Method", "description": "Description", "notes": "Notes"
        }, inplace=True)
        st.dataframe(f_display, width="stretch", hide_index=True)

        # Delete expense section
        with st.expander("🗑️ Delete an Expense"):
            del_options = [f"#{e['exp_id']} • {e['date']} • {e['user_name']} • {fmt(e['amount'])} ({e['description']})" for e in filtered_expenses]
            sel_del = st.selectbox("Select Expense to Remove", options=del_options)
            if st.button("Confirm Delete Expense", type="secondary"):
                del_id = int(sel_del.split("•")[0].replace("#", "").strip())
                db.delete_expense(del_id)
                st.success(f"Expense #{del_id} deleted.")
                st.rerun()
    else:
        st.info("No matching expenses found.")

# =========================================================================
# TAB 3: CIRCLES & BILL SPLITS (Group Management)
# =========================================================================
with tabs[2]:
    st.markdown("### 👥 Circles & Bill Splits")
    
    if not groups:
        st.info("No Circles created yet. Use the sidebar to create your first circle (e.g. Roommates, Trip Squad)!")
    else:
        for g in groups:
            gid = g["group_id"]
            members = db.get_group_members(gid)
            member_ids = [m["user_id"] for m in members]
            shared_bills = db.get_group_shared_expenses(gid)
            total_shared_vol = sum(sb["amount"] for sb in shared_bills)

            with st.expander(f"🏢 {g['group_name']} • {len(members)} Members • Total Shared: {fmt(total_shared_vol)}", expanded=(active_group_id == gid or len(groups) == 1)):
                c_m1, c_m2 = st.columns([3, 1])
                
                with c_m1:
                    # Member chips
                    if members:
                        chips_html = "".join([f"<span class='pill pill-blue'>👤 {m['name']}</span>" for m in members])
                        st.markdown(f"**Members:** {chips_html}", unsafe_allow_html=True)
                    else:
                        st.caption("No members in this circle yet.")

                    # Add / Remove members
                    col_add, col_rm = st.columns(2)
                    with col_add:
                        eligible_to_add = [u for u in users if u["user_id"] not in member_ids]
                        if eligible_to_add:
                            add_options = [f"{u['name']} (#{u['user_id']})" for u in eligible_to_add]
                            sel_to_add = st.selectbox("Add Member", options=["-- Select --"] + add_options, key=f"add_mem_{gid}")
                            if st.button("Add to Circle", key=f"btn_add_{gid}") and sel_to_add != "-- Select --":
                                to_add_id = int(sel_to_add.split("#")[1].rstrip(")"))
                                db.add_member_to_group(gid, to_add_id)
                                st.success("Member added!")
                                st.rerun()
                    with col_rm:
                        if members:
                            rm_options = [f"{m['name']} (#{m['user_id']})" for m in members]
                            sel_to_rm = st.selectbox("Remove Member", options=["-- Select --"] + rm_options, key=f"rm_mem_{gid}")
                            if st.button("Remove from Circle", key=f"btn_rm_{gid}") and sel_to_rm != "-- Select --":
                                to_rm_id = int(sel_to_rm.split("#")[1].rstrip(")"))
                                db.remove_member_from_group(gid, to_rm_id)
                                st.success("Member removed.")
                                st.rerun()

                with c_m2:
                    if st.button("🗑️ Delete Circle", key=f"del_circle_{gid}", help="Deletes group and its shared expenses"):
                        db.delete_group(gid)
                        st.success(f"Circle '{g['group_name']}' deleted.")
                        st.rerun()

                st.write("")
                st.markdown(f"##### 🧾 Shared Bills in {g['group_name']} ({len(shared_bills)})")
                
                if shared_bills:
                    for sb in shared_bills:
                        with st.container(border=True):
                            s_head1, s_head2, s_head3 = st.columns([3, 1, 1])
                            with s_head1:
                                st.markdown(f"**{sb['description']}** • **{fmt(sb['amount'])}**")
                                st.caption(f"Paid by **{sb['payer_name']}** on {sb['date']} • Category: {sb.get('category', 'General')}")
                            with s_head2:
                                splits = db.get_splits_for_expense(sb["shared_id"])
                                paid_count = sum(1 for s in splits if s["is_paid"])
                                st.write(f"Status: **{paid_count}/{len(splits)} paid**")
                            with s_head3:
                                if st.button("🗑️ Delete Bill", key=f"del_sb_{sb['shared_id']}"):
                                    db.delete_shared_expense(sb["shared_id"])
                                    st.success("Shared bill deleted.")
                                    st.rerun()

                            # Breakdown of participants
                            st.markdown("<div style='font-size:0.85rem; font-weight:600; color:#94A3B8; margin-top:6px;'>Participant Splits:</div>", unsafe_allow_html=True)
                            
                            for s in splits:
                                sp_col1, sp_col2, sp_col3 = st.columns([2, 1, 1])
                                is_payer = s["user_id"] == sb["payer_id"]
                                payer_note = " (Payer share)" if is_payer else ""

                                with sp_col1:
                                    st.write(f"• **{s['user_name']}**: {fmt(s['amount_owed'])}{payer_note}")
                                with sp_col2:
                                    if s["is_paid"]:
                                        st.markdown("<span class='pill pill-green'>✅ Paid</span>", unsafe_allow_html=True)
                                    else:
                                        st.markdown("<span class='pill pill-red'>⏳ Unpaid</span>", unsafe_allow_html=True)
                                with sp_col3:
                                    if not s["is_paid"]:
                                        if st.button("Mark Paid", key=f"mk_paid_{s['split_id']}"):
                                            db.mark_split_paid(s["split_id"], True)
                                            st.rerun()
                                    else:
                                        if st.button("Mark Unpaid", key=f"mk_unpaid_{s['split_id']}"):
                                            db.mark_split_paid(s["split_id"], False)
                                            st.rerun()
                else:
                    st.caption("No shared expenses recorded in this circle yet.")

# =========================================================================
# TAB 4: WHO OWES WHOM & 1-CLICK SETTLEMENT
# =========================================================================
with tabs[3]:
    st.markdown("### ⚖️ Who Owes Whom & Debt Simplification")
    st.caption("Greedy minimum cash-flow debt simplification optimizes multi-party debts into the fewest possible payments.")

    # 1. Net Balances Table and Bar Chart
    bal_details = logic.compute_balances_detailed(active_group_id)

    if not bal_details:
        st.info("No group balances yet. Split shared bills in '➕ Log & Manage' to track balances.")
    else:
        col_bal_t, col_bal_c = st.columns([1, 1])
        
        with col_bal_t:
            st.markdown("##### Net Balances Summary")
            df_b = pd.DataFrame(bal_details)
            df_b_display = df_b[["name", "balance", "status"]].copy()
            df_b_display["balance"] = df_b_display["balance"].apply(lambda x: fmt(x))
            df_b_display.rename(columns={"name": "Member", "balance": "Net Balance", "status": "Position"}, inplace=True)
            st.dataframe(df_b_display, width="stretch", hide_index=True)

        with col_bal_c:
            st.markdown("##### Balance Visualization")
            bar_colors = ["#10B981" if b["balance"] > 0 else ("#F43F5E" if b["balance"] < 0 else "#64748B") for b in bal_details]
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
                height=240,
                font=dict(family="Plus Jakarta Sans, sans-serif"),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                yaxis=dict(title=f"Net Balance ({CURR})", gridcolor="rgba(255,255,255,0.06)")
            )
            st.plotly_chart(fig_bar, width="stretch")

        st.divider()

        # 2. Simplified Settlement Plan (Greedy Algorithm Results)
        debts = logic.get_who_owes_whom(active_group_id)
        st.markdown(f"#### ⚡ Optimized Settlement Plan ({len(debts)} Transactions Needed)")

        if debts:
            for idx, d in enumerate(debts):
                with st.container(border=True):
                    dc1, dc2, dc3 = st.columns([3, 2, 1])
                    with dc1:
                        st.markdown(f"""
                            <div style="font-size:1.05rem; font-weight:700;">
                                👤 <span style="color:#F43F5E;">{d['from_name']}</span> pays 
                                👤 <span style="color:#10B981;">{d['to_name']}</span>: 
                                <span style="color:#38BDF8;">{fmt(d['amount'])}</span>
                            </div>
                        """, unsafe_allow_html=True)
                    with dc2:
                        st.caption(f"Clears balance between {d['from_name']} and {d['to_name']}")
                    with dc3:
                        if st.button("⚡ Settle Up", key=f"btn_quick_settle_{idx}", width="stretch", type="primary"):
                            quick_settle_modal(
                                d["from_user"],
                                d["to_user"],
                                d["amount"],
                                f"Settlement payment ({d['from_name']} -> {d['to_name']})",
                                active_group_id
                            )

            # Sankey Flow Diagram
            try:
                sankey_data = logic.get_sankey_debt_data(active_group_id, curr=CURR)
            except TypeError:
                try:
                    sankey_data = logic.get_sankey_debt_data(active_group_id)
                except Exception:
                    sankey_data = None
            except Exception:
                sankey_data = None
            if sankey_data:
                with st.expander("🌊 View Debt Flow Diagram (Sankey)", expanded=False):
                    fig_sankey = go.Figure(data=[go.Sankey(
                        node=dict(
                            pad=15,
                            thickness=20,
                            line=dict(color="#0F172A", width=0.5),
                            label=sankey_data["nodes"],
                            color="#6366F1"
                        ),
                        link=dict(
                            source=sankey_data["sources"],
                            target=sankey_data["targets"],
                            value=sankey_data["values"],
                            label=sankey_data["labels"],
                            color="rgba(99, 102, 241, 0.4)"
                        )
                    )])
                    fig_sankey.update_layout(
                        template="plotly_dark",
                        title_text="Directional Debt Flow Graph",
                        height=280,
                        margin=dict(t=35, b=10, l=10, r=10),
                        font=dict(family="Plus Jakarta Sans, sans-serif", color="#CBD5E1"),
                        paper_bgcolor="rgba(0,0,0,0)"
                    )
                    st.plotly_chart(fig_sankey, width="stretch")
        else:
            st.success("🎉 All settled up! No outstanding debts in this circle.")

        # 3. Settlement Form (Pre-filled if Settle Up was clicked)
        st.write("")
        st.markdown("#### 📝 Record a Settlement Payment")
        
        prefill = st.session_state.get("settle_prefill", {}) or {}
        default_from_uid = prefill.get("from_user", users[0]["user_id"])
        default_to_uid = prefill.get("to_user", users[1]["user_id"] if len(users) > 1 else users[0]["user_id"])
        default_amt = float(prefill.get("amount", 20.0))
        default_note = prefill.get("note", "")

        user_names_list = list(user_name_to_id.keys())
        from_idx = 0
        to_idx = 1 if len(user_names_list) > 1 else 0

        for i, (name, uid) in enumerate(user_name_to_id.items()):
            if uid == default_from_uid: from_idx = i
            if uid == default_to_uid: to_idx = i

        with st.form("form_record_settlement"):
            sc1, sc2, sc3 = st.columns(3)
            with sc1:
                settle_from = st.selectbox("From (Payer)", options=user_names_list, index=from_idx)
            with sc2:
                settle_to = st.selectbox("To (Receiver)", options=user_names_list, index=to_idx)
            with sc3:
                settle_amount = st.number_input(f"Amount ({CURR})", min_value=0.01, value=default_amt, step=1.0)

            sc4, sc5 = st.columns(2)
            with sc4:
                settle_method = st.selectbox("Payment Method", ["Cash", "Venmo", "UPI / GPay / PhonePe", "Bank Transfer", "Zelle", "PayPal"])
            with sc5:
                settle_note = st.text_input("Note", value=default_note, placeholder="e.g. Paid via Venmo")

            if st.form_submit_button("✅ Record Settlement & Update Balances", type="primary", width="stretch"):
                f_uid = user_name_to_id[settle_from]
                t_uid = user_name_to_id[settle_to]
                if f_uid == t_uid:
                    st.error("Payer and receiver cannot be the same person.")
                else:
                    db.add_settlement(f_uid, t_uid, float(settle_amount), active_group_id, settle_note, settle_method)
                    st.session_state["settle_prefill"] = None
                    st.success(f"Settlement of {fmt(settle_amount)} recorded between {settle_from} and {settle_to}!")
                    st.rerun()

        # 4. Past Settlements Audit Log
        past_settlements = db.get_settlements(active_group_id)
        if past_settlements:
            with st.expander(f"📜 Past Settlement Audit Log ({len(past_settlements)} records)"):
                df_st = pd.DataFrame(past_settlements)
                df_st_disp = df_st[["settlement_id", "date", "from_name", "to_name", "amount", "payment_method", "note"]].copy()
                df_st_disp["amount"] = df_st_disp["amount"].apply(lambda x: fmt(x))
                df_st_disp.rename(columns={
                    "settlement_id": "ID", "date": "Date", "from_name": "Payer",
                    "to_name": "Receiver", "amount": "Amount", "payment_method": "Method", "note": "Note"
                }, inplace=True)
                st.dataframe(df_st_disp, width="stretch", hide_index=True)

# =========================================================================
# TAB 5: TRENDS & CATEGORY BUDGETS
# =========================================================================
with tabs[4]:
    st.markdown("### 📈 Trends & Category Budgets")

    # 1. Month-over-Month Telemetry
    mom = logic.get_month_over_month_metrics(active_user_id)
    st.markdown("##### 📅 Month-over-Month Comparison")
    
    mom_c1, mom_c2, mom_c3 = st.columns(3)
    with mom_c1:
        exp_delta = f"{'+' if mom['expense_diff'] >= 0 else ''}{fmt(mom['expense_diff'])} ({mom['expense_change_pct']}%)"
        st.metric("Expenses vs Last Month", fmt(mom["current_expense"]), delta=exp_delta, delta_color="inverse")
    with mom_c2:
        inc_delta = f"{'+' if mom['income_diff'] >= 0 else ''}{fmt(mom['income_diff'])} ({mom['income_change_pct']}%)"
        st.metric("Income vs Last Month", fmt(mom["current_income"]), delta=inc_delta, delta_color="normal")
    with mom_c3:
        st.metric("Active Monthly Budget", fmt(active_user.get("monthly_budget", 0)))

    st.divider()

    # 2. Category Budget Allocator
    st.markdown("##### 🎯 Manage Category Spending Caps")
    st.caption("Set strict monthly limits per category to automatically track budget pacing and prevent overspending.")

    cat_budgets = logic.get_category_budget_status(active_user_id, cur_month)
    
    cb_col_left, cb_col_right = st.columns([1, 1])
    with cb_col_left:
        with st.form("form_set_cat_budget"):
            st.markdown("**Set / Update Category Budget**")
            set_cat = st.selectbox("Category", [
                "Food & Dining", "Housing & Rent", "Groceries", "Utilities",
                "Transportation", "Entertainment", "Health & Medical", "Shopping", "Travel", "Other"
            ])
            set_limit = st.number_input(f"Monthly Limit ({CURR})", min_value=10.0, value=300.0, step=25.0)
            if st.form_submit_button("Save Category Budget", width="stretch"):
                db.set_category_budget(active_user_id, set_cat, float(set_limit))
                st.success(f"Budget of {fmt(set_limit)} set for {set_cat}!")
                st.rerun()

    with cb_col_right:
        st.markdown("**Category Budget Breakdown**")
        if cat_budgets:
            df_cb = pd.DataFrame(cat_budgets)
            df_cb_disp = df_cb[["category", "budget", "spent", "remaining", "pct_used"]].copy()
            df_cb_disp["budget"] = df_cb_disp["budget"].apply(lambda x: fmt(x) if x > 0 else "None")
            df_cb_disp["spent"] = df_cb_disp["spent"].apply(lambda x: fmt(x))
            df_cb_disp["remaining"] = df_cb_disp["remaining"].apply(lambda x: fmt(x) if x is not None else "N/A")
            df_cb_disp["pct_used"] = df_cb_disp["pct_used"].apply(lambda x: f"{x}%" if x is not None else "N/A")
            st.dataframe(df_cb_disp, width="stretch", hide_index=True)
        else:
            st.info("No categories active yet.")

    st.divider()

    # 3. Monthly Trends Chart (Income vs Expenses)
    st.markdown("##### 📊 Multi-Month Spending & Income Trends")
    m_spend = db.get_monthly_spending(active_user_id)
    m_income = db.get_monthly_income(active_user_id)

    if m_spend or m_income:
        df_ms = pd.DataFrame(m_spend) if m_spend else pd.DataFrame(columns=["month", "total"])
        df_mi = pd.DataFrame(m_income) if m_income else pd.DataFrame(columns=["month", "total"])

        df_ms.rename(columns={"total": "Expenses"}, inplace=True)
        df_mi.rename(columns={"total": "Income"}, inplace=True)

        merged_trends = pd.merge(df_ms, df_mi, on="month", how="outer").fillna(0).sort_values("month")

        fig_trend = go.Figure()
        fig_trend.add_trace(go.Bar(x=merged_trends["month"], y=merged_trends["Expenses"], name="Expenses", marker_color="#F43F5E"))
        fig_trend.add_trace(go.Bar(x=merged_trends["month"], y=merged_trends["Income"], name="Income", marker_color="#10B981"))

        fig_trend.update_layout(
            template="plotly_dark",
            barmode="group",
            height=320,
            margin=dict(t=20, b=20, l=10, r=10),
            font=dict(family="Plus Jakarta Sans, sans-serif"),
            yaxis_title=f"Amount ({CURR})",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            yaxis=dict(gridcolor="rgba(255,255,255,0.06)")
        )
        st.plotly_chart(fig_trend, width="stretch")
    else:
        st.info("Log expenses across multiple months to reveal spending trend analysis.")

# =========================================================================
# TAB 6: NUDGES & AUTOMATION (Reminders Engine)
# =========================================================================
with tabs[5]:
    st.markdown("### 🔔 Automated Debt Nudges & Reminders")
    st.caption("Generate friendly reminder links for WhatsApp or dispatch automated emails and Discord alerts for overdue splits.")

    overdue_days_setting = st.slider("Overdue Threshold (Days)", min_value=1, max_value=30, value=3)
    unpaid_splits_all = logic.get_unpaid_splits(active_group_id)

    cutoff_date = (datetime.now() - timedelta(days=overdue_days_setting)).strftime("%Y-%m-%d")
    overdue_splits = [s for s in unpaid_splits_all if s["date"] <= cutoff_date]

    st.markdown(f"##### ⚠️ Overdue Splits Tracker ({len(overdue_splits)} items older than {overdue_days_setting} days)")

    if overdue_splits:
        for idx, s in enumerate(overdue_splits):
            with st.container(border=True):
                r_c1, r_c2, r_c3 = st.columns([3, 2, 2])
                with r_c1:
                    st.markdown(f"""
                        **{s['debtor_name']}** owes **{fmt(s['amount_owed'])}** to **{s['payer_name']}**
                    """)
                    st.caption(f"Bill: '{s['description']}' ({s['date']}) • Circle: {s.get('group_name', 'General')}")
                with r_c2:
                    wa_link = reminders.generate_whatsapp_link(s["debtor_name"], s["payer_name"], s["description"], s["amount_owed"], s["date"], phone=s.get("debtor_phone", ""), curr=CURR)
                    st.link_button("📲 Send via WhatsApp", wa_link, width="stretch")
                with r_c3:
                    if st.button("Mark as Paid", key=f"nudge_mark_paid_{s['split_id']}", width="stretch"):
                        db.mark_split_paid(s["split_id"], True)
                        st.success("Split marked paid!")
                        st.rerun()

        # Mass automated trigger
        st.divider()
        st.markdown("##### 🚀 Multi-Channel Automated Dispatcher")
        
        col_disp1, col_disp2 = st.columns([2, 1])
        with col_disp1:
            dry_run_toggle = st.toggle("Dry-Run Simulation Mode", value=True, help="Simulates dispatching emails and Discord webhooks without sending live messages")
            channel_choices = st.multiselect("Channels", options=["email", "discord"], default=["email", "discord"])
        with col_disp2:
            st.write("")
            st.write("")
            if st.button("📢 Trigger Overdue Nudges Now", type="primary", width="stretch"):
                results = reminders.send_gentle_reminders(
                    group_id=active_group_id,
                    overdue_days=overdue_days_setting,
                    channels=channel_choices,
                    is_dry_run=dry_run_toggle,
                    curr=CURR
                )
                st.success(results["message"])
                for sent_item in results.get("sent", []):
                    if sent_item.get("channel") == "email":
                        st.write(f"• **Email to {sent_item['debtor']}** ({sent_item['to']}): {sent_item['msg']}")
                    elif sent_item.get("channel") == "discord":
                        st.write(f"• **Discord notification**: {sent_item['msg']}")
    else:
        st.success(f"🎉 No unpaid splits older than {overdue_days_setting} days! All friend debts are either settled or fresh.")

    # CLI / Cron setup guide
    with st.expander("⏱️ Automate via Cron (Daily at 9:00 AM)"):
        st.markdown(f"""
            To automatically send reminders daily without opening the browser, schedule `reminders.py` via cron:
            ```bash
            # Run daily at 9:00 AM
            0 9 * * * cd /home/tanishagrawal/BudgetApp && /home/tanishagrawal/.local/bin/python3.11 reminders.py --live >> reminders.log 2>&1
            ```
            **Required Environment Variables for Live Dispatch:**
            ```bash
            export SMTP_HOST="smtp.gmail.com"
            export SMTP_PORT="587"
            export SMTP_USER="your-email@gmail.com"
            export SMTP_PASS="your-app-password"
            export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
            ```
        """)

# =========================================================================
# TAB 7: DATA & EXPORT
# =========================================================================
with tabs[6]:
    st.markdown("### 📥 Data & Export")
    st.caption("Export your ledgers, incomes, and settlement history to CSV for external records, spreadsheets, or offline backups.")

    exp_c1, exp_c2, exp_c3 = st.columns(3)
    
    with exp_c1:
        all_e = db.get_all_expenses()
        if all_e:
            csv_exp = pd.DataFrame(all_e).to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Expenses CSV", data=csv_exp, file_name=f"expenses_{cur_month}.csv", mime="text/csv", width="stretch")
        else:
            st.caption("No expenses recorded.")
    with exp_c2:
        all_inc = db.get_user_incomes()
        if all_inc:
            csv_inc = pd.DataFrame(all_inc).to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Incomes CSV", data=csv_inc, file_name=f"incomes_{cur_month}.csv", mime="text/csv", width="stretch")
        else:
            st.caption("No incomes recorded.")
    with exp_c3:
        all_settle = db.get_settlements()
        if all_settle:
            csv_stl = pd.DataFrame(all_settle).to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Settlements CSV", data=csv_stl, file_name=f"settlements_{cur_month}.csv", mime="text/csv", width="stretch")
        else:
            st.caption("No settlements recorded.")

# Footer
st.divider()
st.markdown("""
    <div style="text-align: center; color: #64748B; font-size: 0.8rem; padding: 12px 0;">
        Smart Budgeter & Debt-Splitter • Engineered with Python, SQLite, Streamlit & Plotly
    </div>
""", unsafe_allow_html=True)
