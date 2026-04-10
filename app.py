"""
app.py — Arikina B2B Stablecoin Escrow Test Harness
Streamlit UI for running all 5 escrow scenarios with configurable inputs.

Run: streamlit run app.py
"""

import os
import sys
import io
import time
import json

# Ensure we run from the project directory so wallets.json is found
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
import requests as _requests

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Arikina Escrow — Test Harness",
    page_icon="🔐",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Brand CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  :root {
    --navy:  #0D1B2A;
    --teal:  #1A7A72;
    --gold:  #C9A84C;
    --light: #F5F5F0;
  }
  .main .block-container { padding-top: 1.5rem; }
  h1 { color: var(--navy) !important; }
  h2, h3 { color: var(--teal) !important; }
  .scenario-card {
    background: var(--light);
    border-left: 4px solid var(--teal);
    padding: 0.75rem 1rem;
    border-radius: 0 6px 6px 0;
    margin-bottom: 0.5rem;
  }
  .outcome-badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 0.78rem;
    font-weight: 600;
    margin-top: 4px;
  }
  .badge-green  { background: #d4edda; color: #155724; }
  .badge-red    { background: #f8d7da; color: #721c24; }
  .badge-orange { background: #ffeeba; color: #856404; }
  .badge-blue   { background: #d1ecf1; color: #0c5460; }
  .tx-link a { color: var(--teal) !important; font-size: 0.82rem; }
  .stTabs [data-baseweb="tab"] { font-size: 0.85rem; }
  .wallet-row { font-size: 0.8rem; color: #444; font-family: monospace; }
  .balance-val { font-size: 1.1rem; font-weight: 700; color: var(--navy); }
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

HORIZON = "https://horizon-testnet.stellar.org"
EXPLORER_TX  = "https://stellar.expert/explorer/testnet/tx/{}"
EXPLORER_ACC = "https://stellar.expert/explorer/testnet/account/{}"

def load_wallets():
    with open("wallets.json") as f:
        return json.load(f)

def get_xlm_balance(public_key: str) -> str:
    try:
        r = _requests.get(f"{HORIZON}/accounts/{public_key}", timeout=8)
        if r.status_code == 200:
            for b in r.json()["balances"]:
                if b["asset_type"] == "native":
                    return f"{float(b['balance']):,.2f} XLM"
        return "—"
    except Exception:
        return "—"

def short(pk: str) -> str:
    return f"{pk[:6]}…{pk[-4:]}"

def tx_md(label: str, tx_hash: str) -> str:
    return f"[{label}]({EXPLORER_TX.format(tx_hash)})"


class StdoutCapture:
    """Redirects print() to a list of lines, updating a Streamlit container live."""
    def __init__(self, container):
        self._container = container
        self._lines = []
        self._orig = sys.stdout

    def __enter__(self):
        sys.stdout = self
        return self

    def __exit__(self, *_):
        sys.stdout = self._orig
        self.flush()

    def write(self, text):
        self._orig.write(text)
        self._lines.append(text)
        joined = "".join(self._lines)
        self._container.code(joined, language=None)

    def flush(self):
        pass

    def getvalue(self) -> str:
        return "".join(self._lines)


# ── Sidebar — Wallets & Balances ──────────────────────────────────────────────

with st.sidebar:
    st.image("https://cmahadeo77.github.io/Arikina%20logo.jpg",
             width=160, use_container_width=False)
    st.markdown("### B2B Stablecoin Escrow")
    st.caption("Stellar Testnet · Live Demo")
    st.divider()

    if st.button("↻  Refresh Balances", use_container_width=True):
        st.cache_data.clear()

    wallets = load_wallets()

    st.markdown("**Wallets**")
    for role in ["buyer", "supplier", "oracle"]:
        w = wallets.get(role, {})
        pk = w.get("public_key", "")
        bal = get_xlm_balance(pk) if pk else "—"
        label = w.get("label", role.title())
        st.markdown(f"""
        <div style='margin-bottom:10px'>
          <b>{label}</b><br>
          <span class='wallet-row'>{short(pk)}</span>
          &nbsp;&nbsp;
          <a href='{EXPLORER_ACC.format(pk)}' target='_blank' style='font-size:0.75rem'>explorer ↗</a><br>
          <span class='balance-val'>{bal}</span>
        </div>
        """, unsafe_allow_html=True)

    st.divider()
    st.markdown("**Escrow Multisig Rules**")
    st.markdown("""
    <small>
    • <b>Low (1)</b>: Oracle alone → write data<br>
    • <b>Med (2)</b>: Buyer + Oracle → payments<br>
    • <b>High (2)</b>: Buyer + Oracle → account changes
    </small>
    """, unsafe_allow_html=True)

    st.divider()
    st.caption("PDF: `Arikina_B2B_Escrow_Use_Cases.pdf`")
    st.caption("CLI: `python -X utf8 escrow.py [scenario]`")


# ── Main ──────────────────────────────────────────────────────────────────────

st.markdown("## Escrow Test Harness")
st.markdown(
    "Select a scenario, configure the PO parameters, and run end-to-end on Stellar testnet. "
    "All transactions are live — viewable on [stellar.expert](https://stellar.expert/explorer/testnet)."
)

# ── Scenario tabs ─────────────────────────────────────────────────────────────
SCENARIOS = {
    "happy":       ("✅  Happy Path",         "Full delivery — supplier receives 100% payment",          "badge-green"),
    "deadline":    ("⏱  Deadline Expiry",     "Supplier ghosts — oracle auto-refunds buyer",             "badge-blue"),
    "cancel":      ("✗   Pre-Ship Cancel",    "Mutual cancellation before goods dispatched",             "badge-blue"),
    "quality":     ("⚖  Quality Dispute",    "Short weight / wrong grade — oracle splits payment",      "badge-orange"),
    "nondelivery": ("🚫  Non-Delivery",       "Tracking shows delivered; buyer disputes — oracle rules", "badge-red"),
}

tabs = st.tabs([v[0] for v in SCENARIOS.values()])

for tab, (scenario_key, (tab_label, description, badge)) in zip(tabs, SCENARIOS.items()):
    with tab:

        # ── Description card ──────────────────────────────────────────────────
        badge_map = {
            "badge-green":  ("RELEASED",         "#155724", "#d4edda"),
            "badge-blue":   ("REFUNDED",          "#0c5460", "#d1ecf1"),
            "badge-orange": ("DISPUTE_RESOLVED",  "#856404", "#ffeeba"),
            "badge-red":    ("REFUNDED / RELEASED","#721c24","#f8d7da"),
        }
        exit_state, fc, bc = badge_map[badge]

        st.markdown(f"""
        <div class='scenario-card'>
          <b>{description}</b><br>
          <span style='background:{bc};color:{fc};padding:2px 8px;
                border-radius:10px;font-size:0.78rem;font-weight:600'>
            Exit → {exit_state}
          </span>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")

        # ── Form ──────────────────────────────────────────────────────────────
        col1, col2 = st.columns([1, 1])

        with col1:
            st.markdown("**Purchase Order**")
            po_number  = st.text_input("PO Number",
                value=f"PO-ARIKINA-2026-{scenario_key.upper()[:3]}",
                key=f"{scenario_key}_po")
            ingredient = st.text_input("Ingredient",
                value="Shea Butter 200kg - Ghana",
                key=f"{scenario_key}_ing")
            amount_xlm = st.number_input("Amount (XLM)",
                min_value=10.0, max_value=5000.0, value=500.0, step=50.0,
                key=f"{scenario_key}_amt",
                help="1 XLM = $1 USD equivalent in this demo")

            if scenario_key in ("happy", "quality", "nondelivery"):
                tracking_id = st.text_input("Tracking ID",
                    value="DHL-GH-2026-0088",
                    key=f"{scenario_key}_track")
            else:
                tracking_id = None

        with col2:
            st.markdown("**Scenario Parameters**")

            delivery_window = st.number_input(
                "Delivery Window (seconds)",
                min_value=10, max_value=300, value=30, step=5,
                key=f"{scenario_key}_win",
                help="Demo: 30s. Production: 30 days (2592000s)"
            )

            if scenario_key == "quality":
                dispute_reason = st.text_area(
                    "Dispute Reason",
                    value="Delivered 140kg, PO specified 200kg — 30% short weight",
                    height=80,
                    key=f"{scenario_key}_reason"
                )
                supplier_pct = st.slider(
                    "Supplier Settlement %",
                    min_value=0, max_value=100, value=70, step=5,
                    key=f"{scenario_key}_pct",
                    help="Fraction of escrow released to supplier. Remainder returns to buyer."
                )
                buyer_pct = 100 - supplier_pct
                st.caption(f"Supplier: {supplier_pct}%  ·  Buyer: {buyer_pct}%  "
                           f"·  Supplier: {amount_xlm * supplier_pct/100:,.0f} XLM  "
                           f"·  Buyer back: {amount_xlm * buyer_pct/100:,.0f} XLM")

            elif scenario_key == "nondelivery":
                oracle_verdict = st.radio(
                    "Oracle Verdict",
                    ["BUYER_WINS", "SUPPLIER_WINS"],
                    index=0,
                    key=f"{scenario_key}_verdict",
                    help="BUYER_WINS → full refund. SUPPLIER_WINS → full release to supplier."
                )
                verdict_desc = {
                    "BUYER_WINS":    "Full refund to buyer — carrier/supplier liable",
                    "SUPPLIER_WINS": "Full release to supplier — buyer claim rejected",
                }
                st.caption(verdict_desc[oracle_verdict])

            elif scenario_key == "deadline":
                st.info(
                    f"Oracle will auto-approve refund after **{delivery_window}s** "
                    "with no delivery confirmed. Script waits for deadline to pass."
                )

            elif scenario_key == "cancel":
                st.info(
                    "Guard: script raises an error if a tracking ID is already "
                    "on-chain. Cancellation is only valid pre-shipment."
                )

        # ── Run button ────────────────────────────────────────────────────────
        st.markdown("---")
        run_col, hint_col = st.columns([1, 3])
        with run_col:
            run = st.button(f"▶  Run {tab_label.strip()}", key=f"run_{scenario_key}",
                            type="primary", use_container_width=True)
        with hint_col:
            wire_fee = 45 + amount_xlm * 0.03
            st.markdown(
                f"<small style='color:#555'>Wire fee: <b>${wire_fee:.2f}</b>  ·  "
                f"Stellar fee: <b>${amount_xlm * 0.00001:.4f}</b>  ·  "
                f"Savings: <b>${wire_fee - amount_xlm * 0.00001:.2f}</b></small>",
                unsafe_allow_html=True
            )

        # ── Execution ─────────────────────────────────────────────────────────
        if run:
            import importlib
            import escrow as e
            importlib.reload(e)  # pick up any code changes

            # Patch delivery window
            e.DELIVERY_WINDOW_SECS = int(delivery_window)

            wallets = load_wallets()
            buyer_kp    = e.kp(wallets["buyer"]["secret_key"])
            supplier_kp = e.kp(wallets["supplier"]["secret_key"])
            oracle_kp   = e.kp(wallets["oracle"]["secret_key"])

            ctx = e.EscrowContext(
                po_number   = po_number,
                ingredient  = ingredient,
                amount_xlm  = float(amount_xlm),
                buyer_kp    = buyer_kp,
                supplier_kp = supplier_kp,
                oracle_kp   = oracle_kp,
            )

            output_container = st.empty()
            error_container  = st.empty()

            try:
                with st.spinner(f"Running {scenario_key} scenario on Stellar testnet..."):
                    with StdoutCapture(output_container) as cap:

                        if scenario_key == "happy":
                            e.create_escrow(ctx);            time.sleep(2)
                            e.fund_escrow(ctx);              time.sleep(2)
                            e.confirm_shipment(ctx, tracking_id); time.sleep(2)
                            e.confirm_delivery(ctx)

                        elif scenario_key == "deadline":
                            e.create_escrow(ctx); time.sleep(2)
                            e.fund_escrow(ctx)
                            e.refund_deadline_expired(ctx)

                        elif scenario_key == "cancel":
                            e.create_escrow(ctx); time.sleep(2)
                            e.fund_escrow(ctx);   time.sleep(2)
                            e.refund_cancelled(ctx)

                        elif scenario_key == "quality":
                            e.create_escrow(ctx);  time.sleep(2)
                            e.fund_escrow(ctx);    time.sleep(2)
                            e.confirm_shipment(ctx, tracking_id); time.sleep(2)
                            e.dispute_quality(ctx, dispute_reason, supplier_pct / 100.0)

                        elif scenario_key == "nondelivery":
                            e.create_escrow(ctx);  time.sleep(2)
                            e.fund_escrow(ctx);    time.sleep(2)
                            e.confirm_shipment(ctx, tracking_id); time.sleep(2)
                            e.dispute_nondelivery(ctx, oracle_verdict)

                # Save escrow key
                wallets["escrow"] = {
                    "label":      f"Escrow ({scenario_key})",
                    "public_key": ctx.escrow_kp.public_key,
                    "secret_key": ctx.escrow_kp.secret,
                }
                e.save_wallets(wallets)

            except Exception as ex:
                error_container.error(f"**Error:** {ex}")
                st.stop()

            # ── Results panel ─────────────────────────────────────────────────
            st.success(f"Scenario complete — State: **{ctx.state.value}**")

            res_col1, res_col2 = st.columns([1, 1])

            with res_col1:
                st.markdown("**Transaction Log**")
                for step, tx_hash in ctx.tx_hashes.items():
                    url = EXPLORER_TX.format(tx_hash)
                    st.markdown(
                        f"<div class='tx-link'><code>{step:<20}</code>"
                        f"<a href='{url}' target='_blank'>{tx_hash[:20]}…</a></div>",
                        unsafe_allow_html=True
                    )

            with res_col2:
                st.markdown("**Final Balances**")
                for role in ["buyer", "supplier"]:
                    w = wallets.get(role, {})
                    pk = w.get("public_key", "")
                    bal = get_xlm_balance(pk)
                    st.markdown(
                        f"<b>{w.get('label', role)}</b>: "
                        f"<span class='balance-val'>{bal}</span>",
                        unsafe_allow_html=True
                    )
                escrow_pk = ctx.escrow_kp.public_key
                escrow_bal = get_xlm_balance(escrow_pk)
                st.markdown(
                    f"<b>Escrow</b>: <span class='balance-val'>{escrow_bal}</span> "
                    f"<a href='{EXPLORER_ACC.format(escrow_pk)}' target='_blank' style='font-size:0.75rem'>↗</a>",
                    unsafe_allow_html=True
                )

            # Wire comparison
            wire_fee    = 45 + float(amount_xlm) * 0.03
            stellar_fee = float(amount_xlm) * 0.00001
            savings     = wire_fee - stellar_fee
            st.markdown(
                f"<div style='background:#e8f8f5;border-radius:8px;padding:0.6rem 1rem;"
                f"margin-top:0.75rem;font-size:0.88rem'>"
                f"💸 <b>Wire fee:</b> ${wire_fee:.2f} &nbsp;→&nbsp; "
                f"<b>Stellar fee:</b> ${stellar_fee:.4f} &nbsp;·&nbsp; "
                f"<b>Saved: ${savings:.2f}</b> ({savings/wire_fee*100:.0f}% reduction)"
                f"</div>",
                unsafe_allow_html=True
            )
