"""
dashboard/app.py — Arikina Supplier Payment Dashboard
Live data from Stellar Horizon testnet API — no mock data.

Run: streamlit run dashboard/app.py
"""

import os, sys, json, time
from datetime import datetime, timezone

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests

st.set_page_config(
    page_title="Arikina — Payment Dashboard",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
  :root { --navy:#0D1B2A; --teal:#1A7A72; --gold:#C9A84C; }
  .main .block-container { padding-top: 1.2rem; }
  h1,h2 { color: var(--navy) !important; }
  h3 { color: var(--teal) !important; }
  .kpi-card {
    background: #F5F5F0;
    border-radius: 10px;
    padding: 1rem 1.2rem;
    border-top: 3px solid var(--teal);
    text-align: center;
  }
  .kpi-val  { font-size: 1.6rem; font-weight: 700; color: var(--navy); }
  .kpi-lbl  { font-size: 0.78rem; color: #666; margin-top: 2px; }
  .tx-row   { font-size: 0.82rem; font-family: monospace; }
  .badge    { display:inline-block; padding:2px 8px; border-radius:10px;
              font-size:0.75rem; font-weight:600; }
  .b-green  { background:#d4edda; color:#155724; }
  .b-blue   { background:#d1ecf1; color:#0c5460; }
  .b-orange { background:#ffeeba; color:#856404; }
  .b-red    { background:#f8d7da; color:#721c24; }
  .b-grey   { background:#e9ecef; color:#495057; }
  .live-dot { display:inline-block; width:8px; height:8px; border-radius:50%;
              background:#22c55e; margin-right:6px; animation: pulse 2s infinite; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }
</style>
""", unsafe_allow_html=True)

# ── Constants ─────────────────────────────────────────────────────────────────
HORIZON      = "https://horizon-testnet.stellar.org"
EXPLORER_TX  = "https://stellar.expert/explorer/testnet/tx/{}"
EXPLORER_ACC = "https://stellar.expert/explorer/testnet/account/{}"
STATE_COLORS = {
    "RELEASED":         "b-green",
    "FUNDED":           "b-orange",
    "SHIPPED":          "b-blue",
    "AWAITING_DEPOSIT": "b-grey",
    "REFUNDED":         "b-blue",
    "CANCELLED":        "b-grey",
    "DISPUTED":         "b-red",
    "DISPUTE_RESOLVED": "b-orange",
}
WIRE_FLAT    = 45.0
WIRE_PCT     = 0.03
STELLAR_PCT  = 0.00001

# ── Horizon helpers ───────────────────────────────────────────────────────────

@st.cache_data(ttl=15)
def fetch_account(public_key: str) -> dict:
    try:
        r = requests.get(f"{HORIZON}/accounts/{public_key}", timeout=8)
        return r.json() if r.status_code == 200 else {}
    except Exception:
        return {}

@st.cache_data(ttl=15)
def fetch_transactions(public_key: str, limit: int = 50) -> list:
    try:
        r = requests.get(
            f"{HORIZON}/accounts/{public_key}/transactions",
            params={"limit": limit, "order": "desc"},
            timeout=10,
        )
        return r.json().get("_embedded", {}).get("records", []) if r.status_code == 200 else []
    except Exception:
        return []

@st.cache_data(ttl=15)
def fetch_operations(public_key: str, limit: int = 100) -> list:
    try:
        r = requests.get(
            f"{HORIZON}/accounts/{public_key}/operations",
            params={"limit": limit, "order": "desc"},
            timeout=10,
        )
        return r.json().get("_embedded", {}).get("records", []) if r.status_code == 200 else []
    except Exception:
        return []

def get_xlm_balance(acc_data: dict) -> float:
    for b in acc_data.get("balances", []):
        if b["asset_type"] == "native":
            return float(b["balance"])
    return 0.0

def decode_data(acc_data: dict) -> dict:
    import base64
    result = {}
    for k, v in acc_data.get("data", {}).items():
        try:
            result[k] = base64.b64decode(v).decode("utf-8", errors="replace")
        except Exception:
            result[k] = v
    return result

def short(pk: str) -> str:
    return f"{pk[:6]}…{pk[-4:]}" if pk else "—"


# ── Load wallets ──────────────────────────────────────────────────────────────

def load_wallets():
    try:
        with open("wallets.json") as f:
            return json.load(f)
    except Exception:
        return {}

wallets = load_wallets()

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.image("https://cmahadeo77.github.io/Arikina%20logo.jpg", width=150)
    st.markdown("### Payment Dashboard")
    st.markdown('<span class="live-dot"></span><small>Live · Stellar Testnet</small>',
                unsafe_allow_html=True)
    st.divider()

    if st.button("↻  Refresh", use_container_width=True):
        st.cache_data.clear()

    st.markdown("**Accounts**")
    for role in ["buyer", "supplier", "oracle"]:
        w = wallets.get(role, {})
        pk = w.get("public_key", "")
        if not pk:
            continue
        acc = fetch_account(pk)
        bal = get_xlm_balance(acc)
        subentries = acc.get("subentry_count", 0)
        label = w.get("label", role.title())
        st.markdown(f"""
        <div style='margin-bottom:10px;padding:8px;background:#F5F5F0;border-radius:6px'>
          <b style='font-size:0.82rem'>{label}</b><br>
          <span style='font-size:0.75rem;color:#555;font-family:monospace'>{short(pk)}</span>
          &nbsp;<a href='{EXPLORER_ACC.format(pk)}' target='_blank'
               style='font-size:0.72rem;color:#1A7A72'>↗</a><br>
          <span style='font-size:1.05rem;font-weight:700;color:#0D1B2A'>{bal:,.2f} XLM</span>
          <span style='font-size:0.72rem;color:#888'>&nbsp;· {subentries} subentries</span>
        </div>
        """, unsafe_allow_html=True)

    if "escrow" in wallets:
        w = wallets["escrow"]
        pk = w.get("public_key", "")
        acc = fetch_account(pk)
        if acc:
            bal  = get_xlm_balance(acc)
            data = decode_data(acc)
            state = data.get("state", "?")
            badge_cls = STATE_COLORS.get(state, "b-grey")
            st.markdown(f"""
            <div style='margin-bottom:10px;padding:8px;background:#fff8e1;
                        border-radius:6px;border-left:3px solid #C9A84C'>
              <b style='font-size:0.82rem'>Escrow (last run)</b><br>
              <span style='font-size:0.75rem;color:#555;font-family:monospace'>{short(pk)}</span>
              &nbsp;<a href='{EXPLORER_ACC.format(pk)}' target='_blank'
                   style='font-size:0.72rem;color:#1A7A72'>↗</a><br>
              <span style='font-size:1.05rem;font-weight:700;color:#0D1B2A'>{bal:,.2f} XLM</span>
              &nbsp;<span class='badge {badge_cls}'>{state}</span>
            </div>
            """, unsafe_allow_html=True)

    st.divider()
    st.caption("Test harness → `http://localhost:8501`")
    st.caption("CLI → `python -X utf8 escrow.py [scenario]`")


# ── Main header ───────────────────────────────────────────────────────────────

st.markdown("## Arikina — Supplier Payment Dashboard")
st.caption(f"Last refreshed: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')} · Stellar Testnet")

# ── Pull live data ────────────────────────────────────────────────────────────

buyer_pk    = wallets.get("buyer", {}).get("public_key", "")
supplier_pk = wallets.get("supplier", {}).get("public_key", "")
escrow_pk   = wallets.get("escrow", {}).get("public_key", "")

buyer_acc    = fetch_account(buyer_pk)    if buyer_pk    else {}
supplier_acc = fetch_account(supplier_pk) if supplier_pk else {}
escrow_acc   = fetch_account(escrow_pk)   if escrow_pk   else {}
escrow_data  = decode_data(escrow_acc)

buyer_bal    = get_xlm_balance(buyer_acc)
supplier_bal = get_xlm_balance(supplier_acc)
escrow_bal   = get_xlm_balance(escrow_acc)
escrow_state = escrow_data.get("state", "—")

# ── KPI row ───────────────────────────────────────────────────────────────────

kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)

def kpi(col, val, label, delta=None, delta_color="normal"):
    with col:
        col.metric(label, val, delta=delta, delta_color=delta_color)

buyer_txs    = fetch_transactions(buyer_pk)    if buyer_pk    else []
supplier_txs = fetch_transactions(supplier_pk) if supplier_pk else []

# Count ops involving buyer account that are payments
buyer_ops = fetch_operations(buyer_pk) if buyer_pk else []
payments_out = [op for op in buyer_ops if op.get("type") == "payment"
                and op.get("from") == buyer_pk]
payments_in  = [op for op in supplier_ops_list := fetch_operations(supplier_pk) if supplier_pk else []
                if op.get("type") == "payment" and op.get("to") == supplier_pk]

total_paid_out = sum(float(op.get("amount", 0)) for op in payments_out)
total_received = sum(float(op.get("amount", 0)) for op in payments_in)

wire_equiv    = WIRE_FLAT + total_paid_out * WIRE_PCT
stellar_fees  = total_paid_out * STELLAR_PCT
total_savings = wire_equiv - stellar_fees

kpi(kpi1, f"{buyer_bal:,.2f} XLM",    "Buyer Balance")
kpi(kpi2, f"{supplier_bal:,.2f} XLM", "Supplier Balance")
kpi(kpi3, f"{escrow_bal:,.2f} XLM",   "Escrow Balance")
kpi(kpi4, f"${total_savings:,.2f}",   "Wire Savings (est.)",
    delta=f"${wire_equiv:,.2f} wire avoided", delta_color="normal")
kpi(kpi5, escrow_state, "Escrow State")

st.divider()

# ── Tabs ──────────────────────────────────────────────────────────────────────

tab_escrow, tab_txns, tab_economics, tab_raw = st.tabs([
    "🔐  Escrow Detail",
    "📋  Transaction History",
    "💸  Payment Economics",
    "🔎  Raw Horizon Data",
])

# ── Tab 1: Escrow Detail ──────────────────────────────────────────────────────
with tab_escrow:
    if not escrow_acc:
        st.info("No escrow account found. Run a scenario from the test harness first.")
    else:
        col_a, col_b = st.columns([1, 1])

        with col_a:
            st.markdown("#### On-Chain Escrow Data")
            if escrow_data:
                rows = []
                key_order = ["po_number", "ingredient", "state", "deadline",
                             "tracking_id", "shipped_at", "delivered_at",
                             "cancelled_at", "refunded_at", "refund_reason",
                             "dispute_reason", "supplier_pct", "oracle_verdict",
                             "resolved_at"]
                seen = set()
                for k in key_order:
                    if k in escrow_data:
                        v = escrow_data[k]
                        # Format timestamps
                        if k.endswith("_at") or k == "deadline":
                            try:
                                dt = datetime.fromtimestamp(int(v), tz=timezone.utc)
                                v = f"{v}  ({dt.strftime('%Y-%m-%d %H:%M UTC')})"
                            except Exception:
                                pass
                        rows.append({"Field": k, "Value": v})
                        seen.add(k)
                for k, v in escrow_data.items():
                    if k not in seen:
                        rows.append({"Field": k, "Value": v})

                df_data = pd.DataFrame(rows)
                st.dataframe(df_data, use_container_width=True, hide_index=True)
            else:
                st.caption("No ManageData entries on this account.")

        with col_b:
            st.markdown("#### Multisig Configuration")
            thresholds = escrow_acc.get("thresholds", {})
            signers    = escrow_acc.get("signers", [])

            st.markdown(f"""
            | Threshold | Value |
            |-----------|-------|
            | Low       | {thresholds.get('low_threshold', '—')} |
            | Medium    | {thresholds.get('med_threshold', '—')} |
            | High      | {thresholds.get('high_threshold', '—')} |
            """)

            st.markdown("**Signers**")
            for s in signers:
                wt  = s.get("weight", 0)
                key = s.get("key", "")
                role_label = ""
                for role in ["buyer", "supplier", "oracle"]:
                    if wallets.get(role, {}).get("public_key") == key:
                        role_label = f" · **{wallets[role]['label']}**"
                st.markdown(
                    f"<span style='font-family:monospace;font-size:0.8rem'>{short(key)}</span>"
                    f"  weight={wt}{role_label}"
                    f"  <a href='{EXPLORER_ACC.format(key)}' target='_blank' "
                    f"style='font-size:0.75rem;color:#1A7A72'>↗</a>",
                    unsafe_allow_html=True
                )

            st.markdown("---")
            st.markdown("**Reserve Breakdown**")
            sub = escrow_acc.get("subentry_count", 0)
            min_bal = (2 + sub) * 0.5
            spendable = max(0, escrow_bal - min_bal)
            st.markdown(f"""
            | Item | XLM |
            |------|-----|
            | Base reserve (2 × 0.5) | 1.00 |
            | Subentries ({sub} × 0.5) | {sub * 0.5:.2f} |
            | **Min balance** | **{min_bal:.2f}** |
            | Current balance | {escrow_bal:.4f} |
            | **Spendable** | **{spendable:.4f}** |
            """)

# ── Tab 2: Transaction History ────────────────────────────────────────────────
with tab_txns:
    st.markdown("#### Buyer Account — Recent Transactions")

    if not buyer_txs:
        st.info("No transactions found for buyer account.")
    else:
        rows = []
        for tx in buyer_txs[:25]:
            created = tx.get("created_at", "")
            try:
                dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                created_fmt = dt.strftime("%m-%d %H:%M")
            except Exception:
                created_fmt = created[:16]

            tx_hash = tx.get("hash", "")
            memo    = tx.get("memo", "")
            ops     = tx.get("operation_count", 0)
            fee     = int(tx.get("fee_charged", 0))
            rows.append({
                "Date":       created_fmt,
                "Hash":       tx_hash[:16] + "…",
                "Ops":        ops,
                "Fee (str)":  fee,
                "Memo":       memo or "—",
                "_url":       EXPLORER_TX.format(tx_hash),
            })

        df_tx = pd.DataFrame(rows)

        # Show as clickable table
        for _, row in df_tx.iterrows():
            st.markdown(
                f"<div class='tx-row'>"
                f"<span style='color:#888'>{row['Date']}</span>&nbsp;&nbsp;"
                f"<a href='{row['_url']}' target='_blank' style='color:#1A7A72'>"
                f"{row['Hash']}</a>&nbsp;&nbsp;"
                f"<span style='color:#555'>ops={row['Ops']} fee={row['Fee (str)']}str</span>"
                + (f"&nbsp;&nbsp;<i style='color:#888'>{row['Memo']}</i>" if row['Memo'] != '—' else "")
                + "</div>",
                unsafe_allow_html=True
            )

    st.markdown("---")
    st.markdown("#### Supplier Account — Received Payments")

    supplier_ops = fetch_operations(supplier_pk) if supplier_pk else []
    recv = [op for op in supplier_ops if op.get("type") == "payment"
            and op.get("to") == supplier_pk]

    if not recv:
        st.info("No inbound payments found for supplier account.")
    else:
        rows = []
        for op in recv[:20]:
            created = op.get("created_at", "")
            try:
                dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                created_fmt = dt.strftime("%Y-%m-%d %H:%M UTC")
            except Exception:
                created_fmt = created
            amount  = float(op.get("amount", 0))
            frm     = short(op.get("from", ""))
            tx_hash = op.get("transaction_hash", "")
            rows.append({
                "Date":   created_fmt,
                "Amount": f"{amount:,.4f} XLM",
                "From":   frm,
                "Tx":     tx_hash[:20] + "…",
                "_url":   EXPLORER_TX.format(tx_hash),
            })

        df_recv = pd.DataFrame(rows)
        for _, row in df_recv.iterrows():
            st.markdown(
                f"<div class='tx-row'>"
                f"<span style='color:#888'>{row['Date']}</span>&nbsp;&nbsp;"
                f"<b style='color:#1A7A72'>{row['Amount']}</b>&nbsp;&nbsp;"
                f"from {row['From']}&nbsp;&nbsp;"
                f"<a href='{row['_url']}' target='_blank' style='color:#1A7A72'>{row['Tx']}</a>"
                "</div>",
                unsafe_allow_html=True
            )

# ── Tab 3: Payment Economics ──────────────────────────────────────────────────
with tab_economics:
    st.markdown("#### Wire vs Stellar — Live Comparison")

    ec_col1, ec_col2 = st.columns([1, 1])

    with ec_col1:
        st.markdown("**Savings Calculator**")
        sim_amount = st.number_input("PO Amount (XLM / USD equiv.)",
                                     min_value=100.0, max_value=100000.0,
                                     value=1700.0, step=100.0,
                                     key="econ_amt")
        sim_wire    = WIRE_FLAT + sim_amount * WIRE_PCT
        sim_stellar = sim_amount * STELLAR_PCT
        sim_savings = sim_wire - sim_stellar

        fig = go.Figure(go.Bar(
            x=["Traditional Wire", "Letter of Credit", "Stellar Escrow"],
            y=[sim_wire, sim_wire * 3, sim_stellar],
            marker_color=["#ef4444", "#f97316", "#1A7A72"],
            text=[f"${sim_wire:.2f}", f"${sim_wire*3:.2f}", f"${sim_stellar:.4f}"],
            textposition="outside",
        ))
        fig.update_layout(
            title="Transaction Cost Comparison",
            yaxis_title="Fee ($)",
            height=320,
            showlegend=False,
            plot_bgcolor="#F5F5F0",
            paper_bgcolor="white",
        )
        st.plotly_chart(fig, use_container_width=True)

    with ec_col2:
        st.markdown("**Annual Projection**")
        monthly_pos = st.slider("Monthly POs", 1, 100, 12, key="econ_pos")
        avg_po      = st.slider("Avg PO Value ($)", 500, 50000, 2000, step=500, key="econ_avg")

        annual_vol    = monthly_pos * avg_po * 12
        annual_wire   = (monthly_pos * WIRE_FLAT + annual_vol * WIRE_PCT) * 12 / 12
        annual_wire   = monthly_pos * 12 * WIRE_FLAT + annual_vol * WIRE_PCT
        annual_stable = annual_vol * STELLAR_PCT
        annual_save   = annual_wire - annual_stable

        # Waterfall chart
        fig2 = go.Figure(go.Waterfall(
            name="Annual",
            orientation="v",
            measure=["absolute", "relative", "total"],
            x=["Wire Fees", "Stellar Savings", "Net Cost"],
            y=[annual_wire, -annual_save, None],
            connector={"line": {"color": "#CCC"}},
            decreasing={"marker": {"color": "#1A7A72"}},
            increasing={"marker": {"color": "#ef4444"}},
            totals={"marker": {"color": "#0D1B2A"}},
            text=[f"${annual_wire:,.0f}", f"-${annual_save:,.0f}", f"${annual_stable:,.0f}"],
            textposition="outside",
        ))
        fig2.update_layout(
            title="Annual Cost Waterfall",
            yaxis_title="$ USD",
            height=320,
            plot_bgcolor="#F5F5F0",
            paper_bgcolor="white",
        )
        st.plotly_chart(fig2, use_container_width=True)

        st.metric("Annual Volume",     f"${annual_vol:,.0f}")
        st.metric("Annual Wire Cost",  f"${annual_wire:,.0f}")
        st.metric("Annual Savings",    f"${annual_save:,.0f}",
                  delta=f"${annual_save/12:,.0f}/mo")

# ── Tab 4: Raw Horizon Data ───────────────────────────────────────────────────
with tab_raw:
    st.markdown("#### Raw Horizon API Response")
    target = st.selectbox("Account", ["buyer", "supplier", "oracle", "escrow"],
                          key="raw_target")
    pk = wallets.get(target, {}).get("public_key", "")
    if pk:
        st.caption(f"GET {HORIZON}/accounts/{pk}")
        acc_raw = fetch_account(pk)
        st.json(acc_raw)
        st.caption(f"Explorer: [{short(pk)}]({EXPLORER_ACC.format(pk)})")
    else:
        st.info(f"No {target} account in wallets.json")
