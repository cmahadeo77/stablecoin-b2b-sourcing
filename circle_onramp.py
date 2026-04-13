"""
circle_onramp.py — Circle Business API Onramp (Sandbox)
Simulates: USD in bank account → ACH → USDC in Circle → USDC on Stellar

Full flow:
  1. verify_api_key()          — confirm Circle sandbox connection
  2. get_master_wallet()       — fetch Circle USDC wallet + balance
  3. simulate_ach_deposit()    — mock ACH bank transfer into Circle (sandbox only)
  4. wait_for_deposit()        — poll until USDC credit appears in Circle wallet
  5. transfer_to_stellar()     — send USDC from Circle wallet → Stellar testnet address
  6. wait_for_transfer()       — poll until transfer completes
  7. verify_stellar_balance()  — confirm USDC landed in Stellar wallet

Prerequisites:
  1. Sign up at https://app.circle.com → Developer → Sandbox
  2. Create an API key (Business Account scope)
  3. Save it to circle_config.json (copy from circle_config.example.json)

Run: python -X utf8 circle_onramp.py [amount_usd]
     python -X utf8 circle_onramp.py 1700
"""

import json, time, uuid, sys
from datetime import datetime, timezone
from pathlib import Path
import requests

sys.stdout.reconfigure(encoding="utf-8")

# ── Config ─────────────────────────────────────────────────────────────────────

SANDBOX_URL   = "https://api-sandbox.circle.com"
CONFIG_FILE   = "circle_config.json"
WALLETS_FILE  = "wallets.json"

# Stellar USDC issuer on testnet (Circle's testnet anchor)
# Source: https://developers.circle.com/developer-tools/docs/supported-chains
USDC_ISSUER_TESTNET = "GBBD47IF6LWK7P7MDEVSCWR7DPUWV3NY3DTQEVFL4NAT4AQH3ZLLFLA5"
USDC_ASSET_CODE     = "USDC"
STELLAR_CHAIN       = "XLM"

POLL_INTERVAL = 3   # seconds between status checks
POLL_TIMEOUT  = 120 # max seconds to wait


# ── Config loading ─────────────────────────────────────────────────────────────

def load_config() -> dict:
    path = Path(CONFIG_FILE)
    if not path.exists():
        print(f"""
  ERROR: {CONFIG_FILE} not found.

  Setup steps:
  1. Go to https://app.circle.com → Log in or create account
  2. Switch to SANDBOX environment (top-right toggle)
  3. Click Developer → API Keys → Create API Key
  4. Scope: Business Account (full access)
  5. Copy the key and paste into {CONFIG_FILE}:

     cp circle_config.example.json circle_config.json
     # then edit circle_config.json and add your key
""")
        sys.exit(1)
    with open(path) as f:
        cfg = json.load(f)
    if not cfg.get("api_key") or cfg["api_key"].startswith("PASTE"):
        print(f"  ERROR: API key not set in {CONFIG_FILE}. Add your Circle sandbox key.")
        sys.exit(1)
    return cfg

def load_wallets() -> dict:
    with open(WALLETS_FILE) as f:
        return json.load(f)


# ── Circle API client ──────────────────────────────────────────────────────────

class CircleClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type":  "application/json",
            "Accept":        "application/json",
        })

    def get(self, path: str) -> dict:
        r = self.session.get(f"{SANDBOX_URL}{path}", timeout=15)
        r.raise_for_status()
        return r.json()

    def post(self, path: str, body: dict) -> dict:
        r = self.session.post(f"{SANDBOX_URL}{path}", json=body, timeout=15)
        try:
            data = r.json()
        except Exception:
            data = {"raw": r.text}
        if r.status_code >= 400:
            raise ValueError(f"Circle API {r.status_code}: {json.dumps(data, indent=2)}")
        return data


# ── Step 1: Verify API key ─────────────────────────────────────────────────────

def verify_api_key(client: CircleClient) -> dict:
    """
    Entry:  API key in circle_config.json
    Action: GET /v1/configuration — confirms sandbox connection
    Exit:   Returns environment info; raises on auth failure
    """
    print("\n[1] Verifying Circle sandbox connection...")
    data = client.get("/v1/configuration")
    payments_env = data.get("data", {}).get("payments", {}).get("masterWalletId", "—")
    print(f"  Connected to: Circle Sandbox")
    print(f"  Master Wallet ID: {payments_env}")
    return data.get("data", {})


# ── Step 2: Get master wallet ──────────────────────────────────────────────────

def get_master_wallet(client: CircleClient) -> dict:
    """
    Entry:  Authenticated Circle client
    Action: GET /v1/businessAccount/wallets — fetches Circle USDC wallet
    Exit:   Returns wallet dict with id, balances
    """
    print("\n[2] Fetching Circle USDC wallet...")
    data = client.get("/v1/businessAccount/wallets")
    wallets = data.get("data", [])
    if not wallets:
        raise ValueError("No wallets found. Ensure API key has Business Account scope.")

    wallet = wallets[0]
    wallet_id = wallet.get("walletId") or wallet.get("id", "—")
    balances  = wallet.get("balances", [])
    usdc_bal  = next((b for b in balances if b.get("currency") == "USD"), None)

    print(f"  Wallet ID:      {wallet_id}")
    print(f"  USDC Balance:   ${float(usdc_bal['amount']):,.2f}" if usdc_bal else "  USDC Balance:   $0.00")
    return wallet


# ── Step 3: Simulate ACH deposit ──────────────────────────────────────────────

def simulate_ach_deposit(client: CircleClient, amount_usd: float, description: str = "") -> dict:
    """
    Entry:  Circle master wallet exists. amount_usd = dollar value to deposit.
    Action: POST /v1/mocks/businessAccount/banks/wires/fund
            Sandbox-only mock: simulates an incoming wire/ACH from a US bank account.
            Circle credits the master wallet with USDC equivalent.
    Exit:   Returns mock transaction tracking ref.
            Funds appear in wallet within ~10 seconds (sandbox).

    Real-world equivalent: Arikina initiates ACH pull from their Wells Fargo / Chase
    business account. Circle debits the bank and credits USDC 1:1.
    Processing time: 1–3 business days (ACH) or same-day (wire).
    """
    print(f"\n[3] Simulating ACH deposit of ${amount_usd:,.2f} USD...")
    tracking_ref = f"ARI{uuid.uuid4().hex[:8].upper()}"
    body = {
        "trackingRef": tracking_ref,
        "amount": {
            "amount":   f"{amount_usd:.2f}",
            "currency": "USD",
        },
        "beneficiaryBank": {
            "accountNumber": "12340010",      # mock US bank account
            "routingNumber":  "021000021",    # mock routing (JPMorgan Chase)
        },
    }
    data = client.post("/v1/mocks/businessAccount/banks/wires/fund", body)
    print(f"  Tracking ref:   {tracking_ref}")
    print(f"  Simulated from: US Bank Account ****0010 (mock)")
    print(f"  Amount:         ${amount_usd:,.2f} USD")
    print(f"  Status:         ACH initiated (sandbox — settles in ~10s)")
    return {**data.get("data", {}), "trackingRef": tracking_ref, "amount_usd": amount_usd}


# ── Step 4: Wait for deposit ───────────────────────────────────────────────────

def wait_for_deposit(client: CircleClient, wallet: dict, expected_amount: float) -> dict:
    """
    Entry:  ACH deposit initiated. Previous USDC balance known.
    Action: Polls GET /v1/businessAccount/wallets every 3s until USDC balance
            increases by expected_amount (or timeout).
    Exit:   Returns updated wallet with new USDC balance.
    """
    print(f"\n[4] Waiting for USDC to credit in Circle wallet...")

    prev_balances = wallet.get("balances", [])
    prev_usdc = float(next((b["amount"] for b in prev_balances
                            if b.get("currency") == "USD"), "0"))

    deadline = time.time() + POLL_TIMEOUT
    while time.time() < deadline:
        time.sleep(POLL_INTERVAL)
        updated  = client.get("/v1/businessAccount/wallets")
        wallets  = updated.get("data", [])
        if wallets:
            balances = wallets[0].get("balances", [])
            new_usdc = float(next((b["amount"] for b in balances
                                   if b.get("currency") == "USD"), "0"))
            delta = new_usdc - prev_usdc
            print(f"  Polling... USDC balance: ${new_usdc:,.2f} (delta: +${delta:,.2f})")
            if delta >= expected_amount * 0.99:  # within 1% tolerance
                print(f"  USDC credited:  ${new_usdc:,.2f}")
                return wallets[0]

    raise TimeoutError(f"USDC did not credit within {POLL_TIMEOUT}s. Check Circle dashboard.")


# ── Step 5: Transfer USDC to Stellar ──────────────────────────────────────────

def transfer_to_stellar(
    client:    CircleClient,
    wallet_id: str,
    stellar_address: str,
    amount_usd: float,
    memo: str = "",
) -> dict:
    """
    Entry:  USDC is in Circle master wallet. Stellar buyer address is known.
    Action: POST /v1/businessAccount/transfers
            Instructs Circle to push USDC from their wallet to the Stellar
            testnet address. Circle handles the on-chain transaction.
    Exit:   Returns transfer object with id and initial status.
            Transfer completes in ~30–60 seconds (sandbox).

    Real-world: On mainnet this sends actual USDC (issued by Circle, GA5ZSEJY...)
    to the Stellar address. The buyer's Stellar wallet must have a USDC trustline.
    """
    print(f"\n[5] Transferring ${amount_usd:,.2f} USDC → Stellar testnet...")
    print(f"  Destination:    {stellar_address[:12]}…{stellar_address[-4:]}")

    body = {
        "idempotencyKey": str(uuid.uuid4()),
        "source": {
            "type": "wallet",
            "id":   wallet_id,
        },
        "destination": {
            "type":    "blockchain",
            "address": stellar_address,
            "chain":   STELLAR_CHAIN,
        },
        "amount": {
            "amount":   f"{amount_usd:.2f}",
            "currency": "USD",
        },
    }
    if memo:
        body["destination"]["addressTag"] = memo

    data = client.post("/v1/businessAccount/transfers", body)
    transfer = data.get("data", {})
    transfer_id = transfer.get("id", "—")
    status      = transfer.get("status", "—")

    print(f"  Transfer ID:    {transfer_id}")
    print(f"  Status:         {status}")
    print(f"  Chain:          Stellar (XLM)")
    return transfer


# ── Step 6: Wait for transfer completion ──────────────────────────────────────

def wait_for_transfer(client: CircleClient, transfer_id: str) -> dict:
    """
    Entry:  Transfer initiated with a transfer_id.
    Action: Polls GET /v1/businessAccount/transfers/{id} until status = complete.
    Exit:   Returns completed transfer with txHash (Stellar transaction hash).

    Statuses: pending → running → complete | failed
    """
    print(f"\n[6] Waiting for transfer to settle on Stellar...")
    deadline = time.time() + POLL_TIMEOUT

    while time.time() < deadline:
        time.sleep(POLL_INTERVAL)
        data     = client.get(f"/v1/businessAccount/transfers/{transfer_id}")
        transfer = data.get("data", {})
        status   = transfer.get("status", "pending")
        tx_hash  = transfer.get("transactionHash", "")

        print(f"  Status: {status}" + (f"  |  tx: {tx_hash[:20]}…" if tx_hash else ""))

        if status == "complete":
            print(f"  Settled on Stellar!")
            print(f"  Stellar tx hash: {tx_hash}")
            print(f"  Explorer: https://stellar.expert/explorer/testnet/tx/{tx_hash}")
            return transfer
        if status == "failed":
            raise ValueError(f"Transfer failed: {json.dumps(transfer, indent=2)}")

    raise TimeoutError(f"Transfer did not complete within {POLL_TIMEOUT}s.")


# ── Step 7: Verify Stellar USDC balance ───────────────────────────────────────

def verify_stellar_balance(stellar_address: str) -> dict:
    """
    Entry:  USDC transfer to Stellar address should be complete.
    Action: Queries Stellar Horizon for account balances.
            Looks for USDC trustline (asset_code=USDC, asset_issuer=Circle).
    Exit:   Returns USDC balance. If no trustline, shows setup instructions.
    """
    print(f"\n[7] Verifying USDC balance on Stellar...")
    HORIZON = "https://horizon-testnet.stellar.org"
    try:
        r = requests.get(f"{HORIZON}/accounts/{stellar_address}", timeout=10)
        if r.status_code != 200:
            print(f"  Account not found or not yet activated.")
            return {}

        balances = r.json().get("balances", [])
        xlm_bal  = next((float(b["balance"]) for b in balances if b["asset_type"] == "native"), 0)
        usdc_bal = next((float(b["balance"]) for b in balances
                         if b.get("asset_code") == "USDC"), None)

        print(f"  XLM balance:  {xlm_bal:,.4f} XLM (for fees)")

        if usdc_bal is not None:
            print(f"  USDC balance: ${usdc_bal:,.2f} USDC  ✓")
        else:
            print(f"  USDC balance: No USDC trustline found.")
            print(f"  → Run setup_usdc_trustline() to add the trustline first.")

        return {"xlm": xlm_bal, "usdc": usdc_bal}

    except Exception as e:
        print(f"  Horizon error: {e}")
        return {}


# ── Trustline setup ────────────────────────────────────────────────────────────

def setup_usdc_trustline(buyer_secret: str):
    """
    Sets up a USDC trustline on the buyer's Stellar account.
    Must be done once before Circle can send USDC to the Stellar address.

    Entry:  Buyer has XLM balance for fees (minimum 0.5 XLM for trustline reserve)
    Exit:   Buyer account now accepts Circle USDC on Stellar testnet
    """
    from stellar_sdk import Keypair, Network, Server, TransactionBuilder, Asset

    print("\n[SETUP] Adding USDC trustline to buyer Stellar account...")
    HORIZON_URL  = "https://horizon-testnet.stellar.org"
    NETWORK_PASS = Network.TESTNET_NETWORK_PASSPHRASE

    buyer_kp = Keypair.from_secret(buyer_secret)
    server   = Server(HORIZON_URL)
    acc      = server.load_account(buyer_kp.public_key)

    usdc_asset = Asset(USDC_ASSET_CODE, USDC_ISSUER_TESTNET)

    tx = (
        TransactionBuilder(
            source_account=acc,
            network_passphrase=NETWORK_PASS,
            base_fee=100,
        )
        .append_change_trust_op(asset=usdc_asset, limit="1000000")
        .set_timeout(180)
        .build()
    )
    tx.sign(buyer_kp)
    resp = server.submit_transaction(tx)

    print(f"  Trustline added for USDC (Circle issuer)")
    print(f"  Issuer: {USDC_ISSUER_TESTNET}")
    print(f"  Tx hash: {resp['hash']}")
    print(f"  Buyer account now accepts USDC on Stellar testnet")
    return resp["hash"]


# ── Wire comparison ────────────────────────────────────────────────────────────

def print_onramp_economics(amount_usd: float):
    ach_fee     = 0.00                 # Circle: free ACH onramp for businesses
    wire_fee    = 15.00                # Circle: $15 wire fee (production)
    fx_markup   = amount_usd * 0.005  # 0.5% FX markup (traditional bank)
    circle_fee  = 0.0                 # Circle: no fee to move to blockchain
    traditional = fx_markup + 45.0    # bank wire + FX

    print(f"\n  [Onramp Economics — ${amount_usd:,.0f} USD]")
    print(f"    Circle ACH onramp fee:   ${ach_fee:.2f}  (free)")
    print(f"    Circle wire fee:         ${wire_fee:.2f}  (if wire, not ACH)")
    print(f"    Circle → Stellar:        ${circle_fee:.2f}  (free)")
    print(f"    Traditional FX markup:   ${fx_markup:.2f}  (0.5% bank FX)")
    print(f"    Traditional bank wire:   $45.00  (flat fee)")
    print(f"    ─────────────────────────────────────")
    print(f"    Circle total:            ${ach_fee + circle_fee:.2f}")
    print(f"    Traditional total:       ${traditional:.2f}")
    print(f"    You save:                ${traditional:.2f}  on the onramp alone")


# ── Full demo runner ───────────────────────────────────────────────────────────

def run_onramp_demo(amount_usd: float = 1700.0):
    print("\n=========================================")
    print("  Arikina B2B Stablecoin — Onramp Demo")
    print("  Circle Sandbox → Stellar Testnet")
    print("=========================================")

    cfg     = load_config()
    wallets = load_wallets()
    client  = CircleClient(cfg["api_key"])

    buyer_pk     = wallets["buyer"]["public_key"]
    buyer_secret = wallets["buyer"]["secret_key"]

    print(f"\n  Buyer Stellar address: {buyer_pk}")
    print(f"  Amount to onramp:      ${amount_usd:,.2f} USD")
    print(f"  Destination:           USDC on Stellar testnet")

    # Step 1: Verify connection
    verify_api_key(client)

    # Step 2: Get wallet
    wallet    = get_master_wallet(client)
    wallet_id = wallet.get("walletId") or wallet.get("id")

    # Step 3: Simulate ACH
    simulate_ach_deposit(client, amount_usd,
                         description=f"Arikina PO funding ${amount_usd:,.0f}")

    # Step 4: Wait for credit
    wallet = wait_for_deposit(client, wallet, amount_usd)
    wallet_id = wallet.get("walletId") or wallet.get("id")

    # Step 5: Transfer to Stellar
    transfer = transfer_to_stellar(
        client, wallet_id, buyer_pk, amount_usd,
        memo="Arikina PO funding"
    )
    transfer_id = transfer.get("id")

    # Step 6: Wait for settlement
    completed = wait_for_transfer(client, transfer_id)
    tx_hash   = completed.get("transactionHash", "")

    # Step 7: Verify Stellar balance
    verify_stellar_balance(buyer_pk)

    # Economics
    print_onramp_economics(amount_usd)

    print(f"\n=========================================")
    print(f"  Onramp Complete")
    print(f"=========================================")
    print(f"  ${amount_usd:,.2f} USD → USDC → Stellar testnet")
    print(f"  Buyer Stellar address: {buyer_pk}")
    if tx_hash:
        print(f"  Stellar tx:  https://stellar.expert/explorer/testnet/tx/{tx_hash}")
    print(f"\n  Ready to fund escrow. Run: python -X utf8 escrow.py happy\n")


if __name__ == "__main__":
    amount = float(sys.argv[1]) if len(sys.argv) > 1 else 1700.0
    run_onramp_demo(amount)
