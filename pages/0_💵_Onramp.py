"""
pages/0_💵_Onramp.py — Circle Onramp: USD → USDC → Stellar
"""
import os, sys, time, json
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import streamlit as st
from stellar_utils import (
    BRAND_CSS, EXPLORER_TX, EXPLORER_ACC,
    load_wallets, fetch_account, get_xlm_balance, render_sidebar, short,
)

st.set_page_config(page_title="Onramp — Arikina Escrow",
                   page_icon="💵", layout="wide")
st.markdown(BRAND_CSS, unsafe_allow_html=True)
st.markdown("""
<style>
  .flow-box {
    background:#F5F5F0; border-radius:10px; padding:1.1rem 1.3rem;
    text-align:center; border-top:3px solid #1A7A72;
  }
  .flow-arrow {
    font-size:1.8rem; color:#C9A84C; text-align:center;
    padding-top:1.5rem;
  }
  .status-pending  { color:#856404; font-weight:600; }
  .status-complete { color:#155724; font-weight:600; }
  .status-failed   { color:#721c24; font-weight:600; }
</style>
""", unsafe_allow_html=True)

wallets = load_wallets()
with st.sidebar:
    render_sidebar(wallets)

# ── Header ────────────────────────────────────────────────────────────────────

st.markdown("## 💵 USD → USDC Onramp")
st.markdown(
    "Simulate an ACH transfer from Arikina's bank account into Circle, "
    "then push USDC directly to the Stellar buyer wallet — ready to fund escrow."
)

# ── Setup check ───────────────────────────────────────────────────────────────

config_exists = os.path.exists("circle_config.json")
try:
    with open("circle_config.json") as f:
        cfg = json.load(f)
    api_key_set = cfg.get("api_key", "").startswith("TEST_API") or (
        len(cfg.get("api_key","")) > 20 and
        not cfg["api_key"].startswith("PASTE")
    )
except Exception:
    api_key_set = False

if not config_exists or not api_key_set:
    st.warning("**Circle sandbox API key not configured.** Follow the setup steps below.")
    st.markdown("---")
    st.markdown("### Setup — Get Your Free Circle Sandbox Key (5 minutes)")

    col1, col2 = st.columns([1.2, 1])
    with col1:
        st.markdown("""
        **Step 1** — Create account or log in
        → [app.circle.com](https://app.circle.com)

        **Step 2** — Switch to Sandbox
        → Toggle in the top-right corner: **Sandbox**

        **Step 3** — Create API Key
        → Developer → API Keys → **+ Create API Key**
        → Scope: **Business Account** → All permissions
        → Copy the key (starts with `TEST_API_KEY:...`)

        **Step 4** — Save it locally
        """)
        st.code("""# In your terminal:
cd C:\\Users\\cmaha\\stablecoin-demo
copy circle_config.example.json circle_config.json
# Then open circle_config.json and paste your key""", language="bash")

        st.markdown("**Step 5** — Refresh this page")

    with col2:
        st.info("""
        **Why Circle?**

        Circle is the issuer of USDC — the dollar-pegged stablecoin used in B2B payments.

        Their sandbox is:
        - Free forever
        - No real money moves
        - Full API parity with production
        - Supports Stellar testnet natively

        In production, Circle's ACH onramp is free. Wire onramp is $15 flat. No FX markup.
        """)
    st.stop()

# ── API key loaded — show the full onramp UI ──────────────────────────────────

from circle_onramp import CircleClient, get_master_wallet, verify_api_key

client = CircleClient(cfg["api_key"])

# ── Flow diagram ──────────────────────────────────────────────────────────────

st.markdown("### Payment Flow")
fc1, fa1, fc2, fa2, fc3, fa3, fc4 = st.columns([2, 0.4, 2, 0.4, 2, 0.4, 2])

buyer_pk  = wallets.get("buyer", {}).get("public_key", "")
buyer_acc = fetch_account(buyer_pk) if buyer_pk else {}
xlm_bal   = get_xlm_balance(buyer_acc)

with fc1:
    st.markdown("""
    <div class='flow-box'>
      <div style='font-size:1.5rem'>🏦</div>
      <b>Arikina Bank Account</b><br>
      <small style='color:#555'>Wells Fargo / Chase<br>USD — ACH</small><br>
      <span style='font-size:1rem;font-weight:700;color:#0D1B2A'>Simulated</span>
    </div>
    """, unsafe_allow_html=True)

with fa1:
    st.markdown("<div class='flow-arrow'>→</div>", unsafe_allow_html=True)

with fc2:
    try:
        circle_wallet = get_master_wallet(client)
        wid   = circle_wallet.get("walletId") or circle_wallet.get("id", "—")
        bals  = circle_wallet.get("balances", [])
        usdc  = next((float(b["amount"]) for b in bals if b.get("currency") == "USD"), 0.0)
        winfo = f'<span style="font-size:1rem;font-weight:700;color:#0D1B2A">${usdc:,.2f} USDC</span>'
        wid_s = f'<small style="color:#888">{wid[:8]}…</small>'
    except Exception as e:
        winfo = f'<small style="color:#c00">{e}</small>'
        wid_s = ""
        circle_wallet = {}

    st.markdown(f"""
    <div class='flow-box'>
      <div style='font-size:1.5rem'>⭕</div>
      <b>Circle Wallet</b><br>
      <small style='color:#555'>Sandbox USDC<br>{wid_s}</small><br>
      {winfo}
    </div>
    """, unsafe_allow_html=True)

with fa2:
    st.markdown("<div class='flow-arrow'>→</div>", unsafe_allow_html=True)

with fc3:
    st.markdown(f"""
    <div class='flow-box'>
      <div style='font-size:1.5rem'>🌟</div>
      <b>Stellar Wallet</b><br>
      <small style='color:#555'>{short(buyer_pk)}<br>Testnet</small><br>
      <span style='font-size:1rem;font-weight:700;color:#0D1B2A'>{xlm_bal:,.2f} XLM</span>
    </div>
    """, unsafe_allow_html=True)

with fa3:
    st.markdown("<div class='flow-arrow'>→</div>", unsafe_allow_html=True)

with fc4:
    st.markdown("""
    <div class='flow-box' style='border-top-color:#C9A84C'>
      <div style='font-size:1.5rem'>🔐</div>
      <b>Escrow Contract</b><br>
      <small style='color:#555'>2-of-2 multisig<br>PO-locked</small><br>
      <span style='font-size:1rem;color:#888'>Awaiting funds</span>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# ── Onramp form ───────────────────────────────────────────────────────────────

st.markdown("### Run the Onramp")

col_form, col_info = st.columns([1, 1])

with col_form:
    amount_usd = st.number_input(
        "Amount (USD)",
        min_value=10.0, max_value=50000.0, value=1700.0, step=100.0,
        help="Dollar amount to onramp via ACH"
    )
    po_ref = st.text_input("PO Reference (memo)", value="PO-ARIKINA-2026-001")

    wire_cost   = 45 + amount_usd * 0.03
    circle_cost = 0.0
    st.markdown(
        f"<small>Traditional wire: <b>${wire_cost:.2f}</b> &nbsp;→&nbsp; "
        f"Circle ACH: <b>${circle_cost:.2f}</b> &nbsp;·&nbsp; "
        f"Save: <b>${wire_cost:.2f}</b></small>",
        unsafe_allow_html=True,
    )

    run_onramp = st.button("▶  Run Onramp: Bank → Circle → Stellar",
                           type="primary", use_container_width=True)
    st.caption("Sandbox only — no real money moves")

with col_info:
    st.markdown("""
    **What happens when you click Run:**

    1. **ACH simulated** — Circle's mock API credits your Circle wallet with USDC
    2. **Polling** — we watch the Circle wallet balance update (~10s)
    3. **Transfer initiated** — Circle pushes USDC to your Stellar testnet address
    4. **Settling** — we watch the Stellar tx confirm (~30–60s)
    5. **Verified** — Stellar Horizon confirms USDC balance on-chain

    **In production:**
    Step 1 takes 1–3 business days (ACH) or same-day (wire).
    Steps 2–5 are identical but on Stellar mainnet with real USDC.
    """)

# ── Execution ─────────────────────────────────────────────────────────────────

if run_onramp:
    from circle_onramp import (
        simulate_ach_deposit, wait_for_deposit,
        transfer_to_stellar, wait_for_transfer,
        verify_stellar_balance, print_onramp_economics,
    )

    wallet_id = circle_wallet.get("walletId") or circle_wallet.get("id", "")
    if not wallet_id:
        st.error("Could not get Circle wallet ID. Check your API key.")
        st.stop()

    log_container = st.empty()
    err_container = st.empty()

    class StdoutCapture:
        def __init__(self, c):
            self._c = c; self._buf = []; self._orig = sys.stdout
        def __enter__(self): sys.stdout = self; return self
        def __exit__(self, *_): sys.stdout = self._orig
        def write(self, t):
            self._orig.write(t); self._buf.append(t)
            self._c.code("".join(self._buf), language=None)
        def flush(self): pass

    results = {}
    try:
        with st.spinner("Running onramp..."):
            with StdoutCapture(log_container):
                # Step 3: ACH
                simulate_ach_deposit(client, amount_usd, description=po_ref)
                # Step 4: Wait for credit
                updated_wallet = wait_for_deposit(client, circle_wallet, amount_usd)
                wallet_id = updated_wallet.get("walletId") or updated_wallet.get("id", wallet_id)
                # Step 5: Transfer
                transfer = transfer_to_stellar(
                    client, wallet_id, buyer_pk, amount_usd, memo=po_ref
                )
                transfer_id = transfer.get("id", "")
                # Step 6: Wait for settlement
                if transfer_id:
                    completed = wait_for_transfer(client, transfer_id)
                    results["tx_hash"] = completed.get("transactionHash", "")
                    results["transfer_id"] = transfer_id
                # Step 7: Verify
                balances = verify_stellar_balance(buyer_pk)
                results["usdc_balance"] = balances.get("usdc")
                # Economics
                print_onramp_economics(amount_usd)

    except Exception as ex:
        err_container.error(f"**Error:** {ex}")
        st.stop()

    # ── Results ───────────────────────────────────────────────────────────────
    st.success("Onramp complete — USDC landed in Stellar wallet")
    r1, r2 = st.columns(2)

    with r1:
        st.markdown("**Summary**")
        st.markdown(f"- Amount: **${amount_usd:,.2f} USD → USDC**")
        st.markdown(f"- Destination: `{short(buyer_pk)}`")
        if results.get("usdc_balance") is not None:
            st.markdown(f"- USDC balance on Stellar: **${results['usdc_balance']:,.2f}**")
        if results.get("tx_hash"):
            url = EXPLORER_TX.format(results["tx_hash"])
            st.markdown(f"- [View on Stellar Explorer ↗]({url})")

    with r2:
        st.markdown("**Economics**")
        st.metric("Traditional wire cost", f"${wire_cost:.2f}")
        st.metric("Circle ACH cost",       "$0.00", delta=f"-${wire_cost:.2f}", delta_color="inverse")
        st.caption("Next: go to Test Harness → run Happy Path to fund the escrow")
