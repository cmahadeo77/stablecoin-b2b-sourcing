"""
pages/2_🔐_Test_Harness.py — Escrow scenario runner with configurable inputs
"""

import os, sys, time
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import streamlit as st
from stellar_utils import (
    BRAND_CSS, EXPLORER_TX, EXPLORER_ACC, WIRE_FLAT, WIRE_PCT, STELLAR_PCT,
    load_wallets, fetch_account, get_xlm_balance, render_sidebar, short,
)

st.set_page_config(page_title="Test Harness — Arikina Escrow",
                   page_icon="🔐", layout="wide")
st.markdown(BRAND_CSS, unsafe_allow_html=True)

wallets = load_wallets()
with st.sidebar:
    render_sidebar(wallets)

st.markdown("## Escrow Test Harness")
st.markdown(
    "Configure a purchase order and run any escrow scenario end-to-end on Stellar testnet. "
    "All transactions are live — verifiable at [stellar.expert](https://stellar.expert/explorer/testnet)."
)

# ── Stdout capture ────────────────────────────────────────────────────────────

class StdoutCapture:
    def __init__(self, container):
        self._c    = container
        self._buf  = []
        self._orig = sys.stdout
    def __enter__(self):
        sys.stdout = self; return self
    def __exit__(self, *_):
        sys.stdout = self._orig
    def write(self, text):
        self._orig.write(text)
        self._buf.append(text)
        self._c.code("".join(self._buf), language=None)
    def flush(self): pass
    def getvalue(self): return "".join(self._buf)

# ── Scenario definitions ──────────────────────────────────────────────────────

SCENARIOS = {
    "happy":       ("✅  Happy Path",       "Full delivery — supplier receives 100% payment",         "green"),
    "deadline":    ("⏱  Deadline Expiry",   "Supplier ghosts — oracle auto-refunds buyer",            "blue"),
    "cancel":      ("✗   Pre-Ship Cancel",  "Mutual cancellation before goods dispatched",            "blue"),
    "quality":     ("⚖  Quality Dispute",  "Short weight / wrong grade — oracle splits payment",     "orange"),
    "nondelivery": ("🚫  Non-Delivery",     "Tracking shows delivered; buyer disputes — oracle rules","red"),
}

EXIT_STATE = {
    "happy":"RELEASED", "deadline":"REFUNDED", "cancel":"CANCELLED",
    "quality":"DISPUTE_RESOLVED", "nondelivery":"REFUNDED / RELEASED",
}

COLOR_MAP = {"green":("#155724","#d4edda"), "blue":("#0c5460","#d1ecf1"),
             "orange":("#856404","#ffeeba"), "red":("#721c24","#f8d7da")}

tabs = st.tabs([v[0] for v in SCENARIOS.values()])

for tab, (sk, (tab_label, description, color)) in zip(tabs, SCENARIOS.items()):
    with tab:
        fc, bc = COLOR_MAP[color]
        st.markdown(f"""
        <div class='scenario-card'>
          <b>{description}</b><br>
          <span style='background:{bc};color:{fc};padding:2px 8px;
            border-radius:10px;font-size:.78rem;font-weight:600'>
            Exit → {EXIT_STATE[sk]}
          </span>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("---")

        col1, col2 = st.columns(2)

        # ── Left: PO fields ───────────────────────────────────────────────────
        with col1:
            st.markdown("**Purchase Order**")
            po_number  = st.text_input("PO Number",
                value=f"PO-ARIKINA-2026-{sk.upper()[:3]}", key=f"{sk}_po")
            ingredient = st.text_input("Ingredient",
                value="Shea Butter 200kg - Ghana", key=f"{sk}_ing")
            amount_xlm = st.number_input("Amount (XLM)",
                min_value=10.0, max_value=5000.0, value=500.0, step=50.0,
                key=f"{sk}_amt",
                help="1 XLM ≈ $1 USD in this demo")

            if sk in ("happy","quality","nondelivery"):
                tracking_id = st.text_input("Tracking ID",
                    value="DHL-GH-2026-0088", key=f"{sk}_track")
            else:
                tracking_id = None

        # ── Right: Scenario params ────────────────────────────────────────────
        with col2:
            st.markdown("**Scenario Parameters**")

            delivery_window = st.number_input(
                "Delivery Window (seconds)",
                min_value=10, max_value=300, value=30, step=5,
                key=f"{sk}_win",
                help="Demo: 30s | Production: 2592000s (30 days)")

            if sk == "quality":
                dispute_reason = st.text_area("Dispute Reason",
                    value="Delivered 140kg, PO specified 200kg — 30% short weight",
                    height=75, key=f"{sk}_reason")
                supplier_pct = st.slider("Supplier Settlement %",
                    0, 100, 70, 5, key=f"{sk}_pct",
                    help="Remainder refunded to buyer")
                buyer_pct = 100 - supplier_pct
                st.caption(
                    f"Supplier: {supplier_pct}% ({amount_xlm*supplier_pct/100:,.0f} XLM)  ·  "
                    f"Buyer back: {buyer_pct}% ({amount_xlm*buyer_pct/100:,.0f} XLM)"
                )

            elif sk == "nondelivery":
                oracle_verdict = st.radio("Oracle Verdict",
                    ["BUYER_WINS","SUPPLIER_WINS"], index=0, key=f"{sk}_verdict")
                verdicts = {
                    "BUYER_WINS":    "Full refund to buyer — carrier/supplier liable",
                    "SUPPLIER_WINS": "Full release to supplier — buyer claim rejected",
                }
                st.caption(verdicts[oracle_verdict])

            elif sk == "deadline":
                st.info(f"Oracle auto-approves refund after **{delivery_window}s** with no delivery confirmed.")

            elif sk == "cancel":
                st.info("Guard rejects if a tracking ID is already on-chain.")

        # ── Run ───────────────────────────────────────────────────────────────
        st.markdown("---")
        run_col, fee_col = st.columns([1, 3])
        with run_col:
            run = st.button(f"▶  Run", key=f"run_{sk}", type="primary",
                            use_container_width=True)
        with fee_col:
            wf = WIRE_FLAT + amount_xlm * WIRE_PCT
            sf = amount_xlm * STELLAR_PCT
            st.markdown(
                f"<small style='color:#555'>Wire: <b>${wf:.2f}</b> &nbsp;·&nbsp; "
                f"Stellar: <b>${sf:.4f}</b> &nbsp;·&nbsp; "
                f"Save: <b>${wf-sf:.2f}</b></small>",
                unsafe_allow_html=True,
            )

        if run:
            import importlib
            import escrow as e
            importlib.reload(e)

            e.DELIVERY_WINDOW_SECS = int(delivery_window)

            wallets = load_wallets()
            ctx = e.EscrowContext(
                po_number   = po_number,
                ingredient  = ingredient,
                amount_xlm  = float(amount_xlm),
                buyer_kp    = e.kp(wallets["buyer"]["secret_key"]),
                supplier_kp = e.kp(wallets["supplier"]["secret_key"]),
                oracle_kp   = e.kp(wallets["oracle"]["secret_key"]),
            )

            out_container = st.empty()
            err_container = st.empty()

            try:
                with st.spinner(f"Running {sk} on Stellar testnet..."):
                    with StdoutCapture(out_container) as cap:
                        if sk == "happy":
                            e.create_escrow(ctx);                    time.sleep(2)
                            e.fund_escrow(ctx);                      time.sleep(2)
                            e.confirm_shipment(ctx, tracking_id);    time.sleep(2)
                            e.confirm_delivery(ctx)
                        elif sk == "deadline":
                            e.create_escrow(ctx); time.sleep(2)
                            e.fund_escrow(ctx)
                            e.refund_deadline_expired(ctx)
                        elif sk == "cancel":
                            e.create_escrow(ctx); time.sleep(2)
                            e.fund_escrow(ctx);   time.sleep(2)
                            e.refund_cancelled(ctx)
                        elif sk == "quality":
                            e.create_escrow(ctx);  time.sleep(2)
                            e.fund_escrow(ctx);    time.sleep(2)
                            e.confirm_shipment(ctx, tracking_id); time.sleep(2)
                            e.dispute_quality(ctx, dispute_reason, supplier_pct / 100.0)
                        elif sk == "nondelivery":
                            e.create_escrow(ctx);  time.sleep(2)
                            e.fund_escrow(ctx);    time.sleep(2)
                            e.confirm_shipment(ctx, tracking_id); time.sleep(2)
                            e.dispute_nondelivery(ctx, oracle_verdict)

                wallets["escrow"] = {
                    "label": f"Escrow ({sk})",
                    "public_key": ctx.escrow_kp.public_key,
                    "secret_key": ctx.escrow_kp.secret,
                }
                e.save_wallets(wallets)

            except Exception as ex:
                err_container.error(f"**Error:** {ex}")
                st.stop()

            # ── Results ───────────────────────────────────────────────────────
            st.success(f"Complete — State: **{ctx.state.value}**")
            rc1, rc2 = st.columns(2)

            with rc1:
                st.markdown("**Transactions**")
                for step, tx_hash in ctx.tx_hashes.items():
                    url = EXPLORER_TX.format(tx_hash)
                    st.markdown(
                        f"<div class='tx-row'><code>{step:<20}</code>"
                        f"<a href='{url}' target='_blank' style='color:#1A7A72'>"
                        f"{tx_hash[:22]}…</a></div>",
                        unsafe_allow_html=True,
                    )

            with rc2:
                st.markdown("**Final Balances**")
                for role in ["buyer","supplier"]:
                    w   = wallets.get(role,{})
                    pk  = w.get("public_key","")
                    bal = get_xlm_balance(fetch_account(pk))
                    st.markdown(f"**{w.get('label',role)}**: {bal:,.2f} XLM")
                ep  = ctx.escrow_kp.public_key
                ebl = get_xlm_balance(fetch_account(ep))
                st.markdown(
                    f"**Escrow**: {ebl:,.2f} XLM "
                    f"[↗]({EXPLORER_ACC.format(ep)})"
                )

            wf = WIRE_FLAT + float(amount_xlm) * WIRE_PCT
            sf = float(amount_xlm) * STELLAR_PCT
            st.markdown(
                f"<div style='background:#e8f8f5;border-radius:8px;"
                f"padding:.6rem 1rem;font-size:.88rem'>"
                f"💸 Wire fee: <b>${wf:.2f}</b> → Stellar: <b>${sf:.4f}</b> "
                f"· Saved: <b>${wf-sf:.2f}</b> ({(wf-sf)/wf*100:.0f}%)</div>",
                unsafe_allow_html=True,
            )
