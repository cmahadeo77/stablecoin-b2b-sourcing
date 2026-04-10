"""
main.py — Arikina B2B Stablecoin Escrow · Single entry point
Streamlit multi-page app: Home → Dashboard → Test Harness

Run:  streamlit run main.py
"""

import os, sys
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
from stellar_utils import BRAND_CSS, load_wallets, fetch_account, get_xlm_balance, render_sidebar

st.set_page_config(
    page_title="Arikina — B2B Escrow Platform",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(BRAND_CSS, unsafe_allow_html=True)

wallets = load_wallets()
with st.sidebar:
    render_sidebar(wallets)

# ── Home page ─────────────────────────────────────────────────────────────────

st.markdown("## Arikina B2B Stablecoin Escrow Platform")
st.markdown(
    "Programmable escrow for international ingredient sourcing payments — "
    "built on Stellar testnet. Navigate using the sidebar."
)
st.divider()

col1, col2 = st.columns(2)

with col1:
    st.markdown("""
    <div style='background:#F5F5F0;border-radius:10px;padding:1.4rem;
                border-top:4px solid #1A7A72;margin-bottom:1rem'>
      <h3 style='color:#1A7A72;margin:0 0 .5rem'>📊 Dashboard</h3>
      <p style='font-size:.9rem;color:#333;margin:0'>
        Live wallet balances, escrow state, transaction history,
        and payment economics — all pulled directly from Stellar Horizon API.
      </p>
    </div>
    """, unsafe_allow_html=True)
    st.page_link("pages/1_📊_Dashboard.py", label="Open Dashboard →", icon="📊")

with col2:
    st.markdown("""
    <div style='background:#F5F5F0;border-radius:10px;padding:1.4rem;
                border-top:4px solid #C9A84C;margin-bottom:1rem'>
      <h3 style='color:#C9A84C;margin:0 0 .5rem'>🔐 Test Harness</h3>
      <p style='font-size:.9rem;color:#333;margin:0'>
        Configure and run all 5 escrow scenarios end-to-end on Stellar testnet.
        Enter PO details, tracking IDs, dispute reasons, and settlement percentages.
      </p>
    </div>
    """, unsafe_allow_html=True)
    st.page_link("pages/2_🔐_Test_Harness.py", label="Open Test Harness →", icon="🔐")

st.divider()

# ── Scenarios overview ────────────────────────────────────────────────────────

st.markdown("### Escrow Scenarios")

scenarios = [
    ("✅", "Happy Path",          "Full delivery → supplier receives 100% in ~3 seconds",           "#1A7A72", "RELEASED"),
    ("⏱", "Deadline Expiry",     "Supplier fails to deliver → oracle auto-refunds buyer",           "#1A5276", "REFUNDED"),
    ("✗",  "Pre-Ship Cancel",    "Mutual cancellation before shipment → immediate full refund",      "#6E2F7C", "CANCELLED"),
    ("⚖", "Quality Dispute",    "Short weight / wrong grade → oracle splits payment atomically",    "#CA6F1E", "DISPUTE_RESOLVED"),
    ("🚫", "Non-Delivery",       "Tracking shows delivered, buyer disputes → oracle issues verdict", "#B03A2E", "REFUNDED/RELEASED"),
]

cols = st.columns(5)
for col, (icon, name, desc, color, exit_state) in zip(cols, scenarios):
    with col:
        st.markdown(f"""
        <div style='background:#F5F5F0;border-radius:8px;padding:.9rem;
                    border-top:3px solid {color};height:170px'>
          <div style='font-size:1.3rem'>{icon}</div>
          <b style='font-size:.85rem;color:#0D1B2A'>{name}</b>
          <p style='font-size:.78rem;color:#555;margin:.4rem 0'>{desc}</p>
          <span style='font-size:.72rem;font-weight:600;color:{color}'>→ {exit_state}</span>
        </div>
        """, unsafe_allow_html=True)

st.divider()

# ── Economics summary ─────────────────────────────────────────────────────────

st.markdown("### Why Stablecoins for B2B Sourcing")
e1, e2, e3, e4 = st.columns(4)
e1.metric("Wire fee (avg $1,700 PO)", "$96.00",  delta="$45 flat + 3% FX")
e2.metric("Stellar fee",              "$0.017",  delta="99.98% cheaper")
e3.metric("Wire settlement",          "3–5 days", delta=None)
e4.metric("Stellar settlement",       "~3 sec",  delta="Instant")

st.caption(
    "CLI: `python -X utf8 escrow.py [happy|deadline|cancel|quality|nondelivery]`  ·  "
    "PDF: `Arikina_B2B_Escrow_Use_Cases.pdf`  ·  "
    "Repo: [cmahadeo77/stablecoin-b2b-sourcing](https://github.com/cmahadeo77/stablecoin-b2b-sourcing)"
)
