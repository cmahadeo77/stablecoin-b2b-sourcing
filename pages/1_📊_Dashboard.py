"""
pages/1_📊_Dashboard.py — Live Stellar Horizon dashboard
"""

import os, sys
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from datetime import datetime, timezone
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

from stellar_utils import (
    BRAND_CSS, EXPLORER_TX, EXPLORER_ACC, WIRE_FLAT, WIRE_PCT, STELLAR_PCT,
    STATE_BADGE, load_wallets, fetch_account, fetch_transactions,
    fetch_operations, get_xlm_balance, decode_data, short, render_sidebar,
)

st.set_page_config(page_title="Dashboard — Arikina Escrow",
                   page_icon="📊", layout="wide")
st.markdown(BRAND_CSS, unsafe_allow_html=True)

wallets = load_wallets()
with st.sidebar:
    render_sidebar(wallets)

# ── Header ────────────────────────────────────────────────────────────────────

st.markdown("## Payment Dashboard")
st.caption(f"Live · Stellar Testnet · {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")

# ── Pull live account data ────────────────────────────────────────────────────

buyer_pk    = wallets.get("buyer",    {}).get("public_key", "")
supplier_pk = wallets.get("supplier", {}).get("public_key", "")
escrow_pk   = wallets.get("escrow",   {}).get("public_key", "")

buyer_acc    = fetch_account(buyer_pk)    if buyer_pk    else {}
supplier_acc = fetch_account(supplier_pk) if supplier_pk else {}
escrow_acc   = fetch_account(escrow_pk)   if escrow_pk   else {}
escrow_data  = decode_data(escrow_acc)

buyer_bal    = get_xlm_balance(buyer_acc)
supplier_bal = get_xlm_balance(supplier_acc)
escrow_bal   = get_xlm_balance(escrow_acc)
escrow_state = escrow_data.get("state", "—")

# payments from buyer (outbound) and to supplier (inbound)
buyer_ops    = fetch_operations(buyer_pk)    if buyer_pk    else []
supplier_ops = fetch_operations(supplier_pk) if supplier_pk else []

outbound = [op for op in buyer_ops    if op.get("type") == "payment" and op.get("from") == buyer_pk]
inbound  = [op for op in supplier_ops if op.get("type") == "payment" and op.get("to") == supplier_pk]

total_out  = sum(float(op.get("amount", 0)) for op in outbound)
total_in   = sum(float(op.get("amount", 0)) for op in inbound)
wire_equiv = WIRE_FLAT * len(outbound) + total_out * WIRE_PCT
savings    = wire_equiv - total_out * STELLAR_PCT

# ── KPIs ──────────────────────────────────────────────────────────────────────

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Buyer Balance",     f"{buyer_bal:,.2f} XLM")
k2.metric("Supplier Balance",  f"{supplier_bal:,.2f} XLM")
k3.metric("Escrow Balance",    f"{escrow_bal:,.2f} XLM")
k4.metric("Wire Savings (est.)",f"${savings:,.2f}",
          delta=f"${wire_equiv:,.2f} wire avoided")
k5.metric("Escrow State",      escrow_state)

st.divider()

# ── Tabs ──────────────────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4 = st.tabs([
    "🔐  Escrow Detail",
    "📋  Transaction History",
    "💸  Payment Economics",
    "🔎  Raw Horizon",
])

# ── Escrow detail ─────────────────────────────────────────────────────────────

with tab1:
    if not escrow_acc:
        st.info("No escrow account found. Run a scenario from the Test Harness first.")
    else:
        c1, c2 = st.columns(2)

        with c1:
            st.markdown("#### On-Chain Data")
            key_order = ["po_number","ingredient","state","deadline",
                         "tracking_id","shipped_at","delivered_at",
                         "cancelled_at","refunded_at","refund_reason",
                         "dispute_reason","supplier_pct","oracle_verdict","resolved_at"]
            rows, seen = [], set()
            for k in key_order:
                if k in escrow_data:
                    v = escrow_data[k]
                    if k.endswith("_at") or k == "deadline":
                        try:
                            dt = datetime.fromtimestamp(int(v), tz=timezone.utc)
                            v = f"{v}  ({dt.strftime('%Y-%m-%d %H:%M UTC')})"
                        except Exception:
                            pass
                    rows.append({"Field": k, "Value": v}); seen.add(k)
            for k, v in escrow_data.items():
                if k not in seen:
                    rows.append({"Field": k, "Value": v})
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        with c2:
            st.markdown("#### Multisig & Reserve")
            thresh = escrow_acc.get("thresholds", {})
            st.markdown(f"""
            | Threshold | Value |
            |-----------|-------|
            | Low  | {thresh.get('low_threshold','—')} — oracle writes data |
            | Med  | {thresh.get('med_threshold','—')} — buyer+oracle for payments |
            | High | {thresh.get('high_threshold','—')} — buyer+oracle for account changes |
            """)

            st.markdown("**Signers**")
            for s in escrow_acc.get("signers", []):
                key = s.get("key",""); wt = s.get("weight", 0)
                role_lbl = next(
                    (f" · {wallets[r]['label']}" for r in ["buyer","supplier","oracle"]
                     if wallets.get(r,{}).get("public_key") == key), ""
                )
                st.markdown(
                    f"`{short(key)}` weight={wt}{role_lbl} "
                    f"[↗]({EXPLORER_ACC.format(key)})",
                    unsafe_allow_html=False
                )

            st.markdown("**Reserve**")
            sub = escrow_acc.get("subentry_count", 0)
            min_bal  = (2 + sub) * 0.5
            spendable = max(0, escrow_bal - min_bal)
            st.markdown(f"""
            | | XLM |
            |-|-----|
            | Base (2 × 0.5) | 1.00 |
            | Subentries ({sub} × 0.5) | {sub*0.5:.2f} |
            | **Min balance** | **{min_bal:.2f}** |
            | Current | {escrow_bal:.4f} |
            | **Spendable** | **{spendable:.4f}** |
            """)

# ── Transaction history ───────────────────────────────────────────────────────

with tab2:
    st.markdown("#### Buyer — Recent Transactions")
    txs = fetch_transactions(buyer_pk) if buyer_pk else []
    if not txs:
        st.info("No transactions found.")
    for tx in txs[:20]:
        created = tx.get("created_at","")
        try:
            dt = datetime.fromisoformat(created.replace("Z","+00:00"))
            ts = dt.strftime("%m-%d %H:%M")
        except Exception:
            ts = created[:16]
        h = tx.get("hash","")
        st.markdown(
            f"<div class='tx-row'><span style='color:#888'>{ts}</span>&nbsp;&nbsp;"
            f"<a href='{EXPLORER_TX.format(h)}' target='_blank' style='color:#1A7A72'>"
            f"{h[:20]}…</a>&nbsp;&nbsp;"
            f"<span style='color:#555'>ops={tx.get('operation_count',0)}</span></div>",
            unsafe_allow_html=True,
        )

    st.markdown("---")
    st.markdown("#### Supplier — Received Payments")
    rcv = [op for op in supplier_ops if op.get("type")=="payment" and op.get("to")==supplier_pk]
    if not rcv:
        st.info("No inbound payments found.")
    for op in rcv[:15]:
        created = op.get("created_at","")
        try:
            dt = datetime.fromisoformat(created.replace("Z","+00:00"))
            ts = dt.strftime("%Y-%m-%d %H:%M UTC")
        except Exception:
            ts = created
        amt = float(op.get("amount",0))
        h   = op.get("transaction_hash","")
        st.markdown(
            f"<div class='tx-row'><span style='color:#888'>{ts}</span>&nbsp;&nbsp;"
            f"<b style='color:#1A7A72'>{amt:,.4f} XLM</b>&nbsp;&nbsp;"
            f"from {short(op.get('from',''))}&nbsp;&nbsp;"
            f"<a href='{EXPLORER_TX.format(h)}' target='_blank' style='color:#1A7A72'>"
            f"{h[:20]}…</a></div>",
            unsafe_allow_html=True,
        )

# ── Economics ─────────────────────────────────────────────────────────────────

with tab3:
    st.markdown("#### Wire vs Stellar")
    col_a, col_b = st.columns(2)

    with col_a:
        amt = st.number_input("PO Amount (XLM)", 100.0, 100000.0, 1700.0, 100.0, key="ec_amt")
        w_fee = WIRE_FLAT + amt * WIRE_PCT
        s_fee = amt * STELLAR_PCT
        fig = go.Figure(go.Bar(
            x=["Wire", "Letter of Credit", "Stellar"],
            y=[w_fee, w_fee * 3, s_fee],
            marker_color=["#ef4444","#f97316","#1A7A72"],
            text=[f"${w_fee:.2f}", f"${w_fee*3:.2f}", f"${s_fee:.4f}"],
            textposition="outside",
        ))
        fig.update_layout(title="Per-Transaction Cost", yaxis_title="Fee ($)",
                          height=300, showlegend=False, plot_bgcolor="#F5F5F0")
        st.plotly_chart(fig, use_container_width=True)

    with col_b:
        pos   = st.slider("Monthly POs", 1, 100, 12)
        avg   = st.slider("Avg PO ($)", 500, 50000, 2000, 500)
        avol  = pos * avg * 12
        awire = pos * 12 * WIRE_FLAT + avol * WIRE_PCT
        astbl = avol * STELLAR_PCT
        asave = awire - astbl
        fig2 = go.Figure(go.Waterfall(
            measure=["absolute","relative","total"],
            x=["Wire Fees","Savings","Net Cost"],
            y=[awire, -asave, None],
            text=[f"${awire:,.0f}", f"-${asave:,.0f}", f"${astbl:,.0f}"],
            textposition="outside",
            decreasing={"marker":{"color":"#1A7A72"}},
            increasing={"marker":{"color":"#ef4444"}},
            totals={"marker":{"color":"#0D1B2A"}},
        ))
        fig2.update_layout(title="Annual Cost Waterfall", height=300,
                           plot_bgcolor="#F5F5F0")
        st.plotly_chart(fig2, use_container_width=True)
        st.metric("Annual Savings", f"${asave:,.0f}", delta=f"${asave/12:,.0f}/mo")

# ── Raw Horizon ───────────────────────────────────────────────────────────────

with tab4:
    target = st.selectbox("Account", ["buyer","supplier","oracle","escrow"])
    pk = wallets.get(target, {}).get("public_key","")
    if pk:
        st.caption(f"GET {EXPLORER_ACC.format(pk)}")
        st.json(fetch_account(pk))
    else:
        st.info(f"No {target} account in wallets.json")
