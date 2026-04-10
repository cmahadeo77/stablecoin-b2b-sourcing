"""
stellar_utils.py — Shared Horizon API helpers used by all pages.
"""

import os, json, base64
from datetime import datetime, timezone

import requests
import streamlit as st

HORIZON      = "https://horizon-testnet.stellar.org"
EXPLORER_TX  = "https://stellar.expert/explorer/testnet/tx/{}"
EXPLORER_ACC = "https://stellar.expert/explorer/testnet/account/{}"
WIRE_FLAT    = 45.0
WIRE_PCT     = 0.03
STELLAR_PCT  = 0.00001

STATE_BADGE = {
    "RELEASED":         ("b-green",  "#d4edda", "#155724"),
    "FUNDED":           ("b-orange", "#ffeeba", "#856404"),
    "SHIPPED":          ("b-blue",   "#d1ecf1", "#0c5460"),
    "AWAITING_DEPOSIT": ("b-grey",   "#e9ecef", "#495057"),
    "REFUNDED":         ("b-blue",   "#d1ecf1", "#0c5460"),
    "CANCELLED":        ("b-grey",   "#e9ecef", "#495057"),
    "DISPUTED":         ("b-red",    "#f8d7da", "#721c24"),
    "DISPUTE_RESOLVED": ("b-orange", "#ffeeba", "#856404"),
}

BRAND_CSS = """
<style>
  :root { --navy:#0D1B2A; --teal:#1A7A72; --gold:#C9A84C; }
  .main .block-container { padding-top:1.2rem; }
  h1,h2 { color:var(--navy) !important; }
  h3    { color:var(--teal) !important; }
  .live-dot { display:inline-block; width:8px; height:8px; border-radius:50%;
    background:#22c55e; margin-right:5px; animation:pulse 2s infinite; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.4} }
  .badge { display:inline-block; padding:2px 8px; border-radius:10px;
    font-size:.75rem; font-weight:600; }
  .tx-row { font-size:.82rem; font-family:monospace; margin-bottom:3px; }
  .scenario-card { background:#F5F5F0; border-left:4px solid var(--teal);
    padding:.7rem 1rem; border-radius:0 6px 6px 0; margin-bottom:.5rem; }
  .wallet-box { margin-bottom:10px; padding:8px; background:#F5F5F0; border-radius:6px; }
</style>
"""

def project_root() -> str:
    return os.path.dirname(os.path.abspath(__file__))

def load_wallets() -> dict:
    path = os.path.join(project_root(), "wallets.json")
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}

@st.cache_data(ttl=15)
def fetch_account(pk: str) -> dict:
    try:
        r = requests.get(f"{HORIZON}/accounts/{pk}", timeout=8)
        return r.json() if r.status_code == 200 else {}
    except Exception:
        return {}

@st.cache_data(ttl=15)
def fetch_transactions(pk: str, limit: int = 50) -> list:
    try:
        r = requests.get(f"{HORIZON}/accounts/{pk}/transactions",
                         params={"limit": limit, "order": "desc"}, timeout=10)
        return r.json().get("_embedded", {}).get("records", []) if r.status_code == 200 else []
    except Exception:
        return []

@st.cache_data(ttl=15)
def fetch_operations(pk: str, limit: int = 100) -> list:
    try:
        r = requests.get(f"{HORIZON}/accounts/{pk}/operations",
                         params={"limit": limit, "order": "desc"}, timeout=10)
        return r.json().get("_embedded", {}).get("records", []) if r.status_code == 200 else []
    except Exception:
        return []

def get_xlm_balance(acc: dict) -> float:
    for b in acc.get("balances", []):
        if b["asset_type"] == "native":
            return float(b["balance"])
    return 0.0

def decode_data(acc: dict) -> dict:
    result = {}
    for k, v in acc.get("data", {}).items():
        try:
            result[k] = base64.b64decode(v).decode("utf-8", errors="replace")
        except Exception:
            result[k] = v
    return result

def short(pk: str) -> str:
    return f"{pk[:6]}…{pk[-4:]}" if pk else "—"

def render_sidebar(wallets: dict):
    """Renders the shared wallet sidebar used by all pages."""
    st.image("https://cmahadeo77.github.io/Arikina%20logo.jpg", width=150)
    st.markdown("### B2B Stablecoin Escrow")
    st.markdown('<span class="live-dot"></span><small>Live · Stellar Testnet</small>',
                unsafe_allow_html=True)
    st.divider()

    if st.button("↻  Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.markdown("**Accounts**")
    for role in ["buyer", "supplier", "oracle"]:
        w  = wallets.get(role, {})
        pk = w.get("public_key", "")
        if not pk:
            continue
        acc = fetch_account(pk)
        bal = get_xlm_balance(acc)
        st.markdown(f"""
        <div class='wallet-box'>
          <b style='font-size:.82rem'>{w.get('label', role)}</b><br>
          <span style='font-size:.75rem;color:#555;font-family:monospace'>{short(pk)}</span>
          <a href='{EXPLORER_ACC.format(pk)}' target='_blank'
             style='font-size:.72rem;color:#1A7A72'> ↗</a><br>
          <span style='font-size:1.05rem;font-weight:700;color:#0D1B2A'>{bal:,.2f} XLM</span>
        </div>""", unsafe_allow_html=True)

    if "escrow" in wallets:
        pk  = wallets["escrow"].get("public_key", "")
        acc = fetch_account(pk)
        if acc:
            bal   = get_xlm_balance(acc)
            data  = decode_data(acc)
            state = data.get("state", "?")
            _, bg, fg = STATE_BADGE.get(state, ("", "#eee", "#333"))
            st.markdown(f"""
            <div style='margin-bottom:10px;padding:8px;background:#fff8e1;
                        border-radius:6px;border-left:3px solid #C9A84C'>
              <b style='font-size:.82rem'>Escrow (last run)</b><br>
              <span style='font-size:.75rem;color:#555;font-family:monospace'>{short(pk)}</span>
              <a href='{EXPLORER_ACC.format(pk)}' target='_blank'
                 style='font-size:.72rem;color:#1A7A72'> ↗</a><br>
              <span style='font-size:1.05rem;font-weight:700'>{bal:,.2f} XLM</span>
              &nbsp;<span style='background:{bg};color:{fg};padding:2px 7px;
                border-radius:9px;font-size:.72rem;font-weight:600'>{state}</span>
            </div>""", unsafe_allow_html=True)
    st.divider()
