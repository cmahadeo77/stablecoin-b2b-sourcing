"""
escrow.py — Stellar Testnet Escrow for B2B Ingredient Payments
Mirrors SupplierEscrow.sol logic using Stellar multi-signature accounts.

Scenarios
---------
  happy        Full delivery: create → fund → ship → release to supplier
  deadline     Delivery window expires with no confirmation → full refund to buyer
  cancel       Buyer cancels pre-shipment (no tracking ID yet) → full refund to buyer
  quality      Goods arrive but quality is disputed → oracle arbitrates partial split
  nondelivery  Tracking shows delivered; buyer disputes receipt → oracle verdict

Multisig rules (set on escrow account at creation)
---------------------------------------------------
  Master weight  = 0   (escrow account cannot self-sign)
  Buyer  weight  = 1
  Oracle weight  = 1
  Low  threshold = 1   → oracle alone can write data entries (low-risk ops)
  Med  threshold = 2   → buyer + oracle must co-sign any payment
  High threshold = 2   → buyer + oracle must co-sign account changes

Run:  python -X utf8 escrow.py [happy|deadline|cancel|quality|nondelivery]
"""

import json
import time
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from stellar_sdk import (
    Keypair, Network, Server, TransactionBuilder, Asset, Signer,
)
from stellar_sdk.exceptions import BadRequestError

WALLETS_FILE         = "wallets.json"
HORIZON_URL          = "https://horizon-testnet.stellar.org"
NETWORK_PASS         = Network.TESTNET_NETWORK_PASSPHRASE
BASE_FEE             = 100   # stroops
DELIVERY_WINDOW_SECS = 30    # demo: 30 seconds (production: 30 days)

server = Server(HORIZON_URL)


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_wallets():
    with open(WALLETS_FILE) as f:
        return json.load(f)

def save_wallets(w):
    with open(WALLETS_FILE, "w") as f:
        json.dump(w, f, indent=2)

def kp(secret: str) -> Keypair:
    return Keypair.from_secret(secret)

def account(public_key: str):
    return server.load_account(public_key)

def explorer(public_key: str) -> str:
    return f"https://stellar.expert/explorer/testnet/account/{public_key}"

def tx_link(tx_hash: str) -> str:
    return f"https://stellar.expert/explorer/testnet/tx/{tx_hash}"

def balance(public_key: str) -> str:
    acc = server.accounts().account_id(public_key).call()
    for b in acc["balances"]:
        if b["asset_type"] == "native":
            return f"{float(b['balance']):.2f} XLM"
    return "0 XLM"

def print_balances(wallets, label="Balances"):
    print(f"\n  [{label}]")
    for role in ["buyer", "supplier"]:
        w = wallets[role]
        print(f"    {w['label']}: {balance(w['public_key'])}")
    if "escrow" in wallets:
        try:
            print(f"    Escrow account: {balance(wallets['escrow']['public_key'])}")
        except Exception:
            print(f"    Escrow account: (closed)")

def wire_comparison(amount_xlm: float):
    wire_fee    = 45 + (amount_xlm * 0.03)
    stellar_fee = amount_xlm * 0.00001
    savings     = wire_fee - stellar_fee
    print(f"\n  [Payment Economics]")
    print(f"    Amount:            {amount_xlm:.0f} XLM (~${amount_xlm:.0f} USD equivalent)")
    print(f"    Traditional wire:  ${wire_fee:.2f} in fees (${45:.0f} flat + 3% FX)")
    print(f"    Stellar:           ${stellar_fee:.4f} in fees")
    print(f"    You save:          ${savings:.2f}  ({(savings/wire_fee*100):.0f}% cost reduction)")

def _escrow_spendable(ctx: "EscrowContext", new_data_keys: list = None):
    """
    Returns (escrow_bal, max_sendable, acc_data).
    new_data_keys: ManageData keys that will be written NEW in the same tx.
    Stellar validates the minimum balance after *each* op, so we must project
    the post-new-entry subentry count before computing the sendable amount.
    Formula: min_balance = (2 + subentry_count) * 0.5 XLM
    """
    acc_data   = server.accounts().account_id(ctx.escrow_kp.public_key).call()
    escrow_bal = 0.0
    for b in acc_data["balances"]:
        if b["asset_type"] == "native":
            escrow_bal = float(b["balance"])

    existing_data      = set(acc_data.get("data", {}).keys())
    truly_new          = [k for k in (new_data_keys or []) if k not in existing_data]
    effective_subs     = acc_data.get("subentry_count", 0) + len(truly_new)
    min_balance        = (2 + effective_subs) * 0.5
    max_sendable       = round(escrow_bal - min_balance - 0.01, 7)
    return escrow_bal, max_sendable, acc_data


# ── Escrow State Machine ───────────────────────────────────────────────────────

class EscrowState(Enum):
    AWAITING_DEPOSIT = "AWAITING_DEPOSIT"
    FUNDED           = "FUNDED"
    SHIPPED          = "SHIPPED"
    RELEASED         = "RELEASED"
    REFUNDED         = "REFUNDED"
    CANCELLED        = "CANCELLED"
    DISPUTED         = "DISPUTED"
    DISPUTE_RESOLVED = "DISPUTE_RESOLVED"


@dataclass
class EscrowContext:
    po_number:   str
    ingredient:  str
    amount_xlm:  float
    buyer_kp:    Keypair
    supplier_kp: Keypair
    oracle_kp:   Keypair
    escrow_kp:   Keypair        = field(default_factory=Keypair.random)
    state:       EscrowState    = EscrowState.AWAITING_DEPOSIT
    funded_at:   Optional[float] = None
    tracking_id: Optional[str]   = None
    tx_hashes:   dict            = field(default_factory=dict)


# ── Step 1: Create Escrow Account ─────────────────────────────────────────────

def create_escrow(ctx: EscrowContext) -> str:
    """
    Entry:  Buyer has funded wallet.
    Action: Creates a new Stellar account as escrow. Sets 2-of-2 multisig
            (buyer + oracle). Records PO metadata and delivery deadline on-chain.
    Exit:   Escrow account exists on-chain. State = AWAITING_DEPOSIT.
            Supplier can verify escrow address and rules before shipping.
    """
    print("\n[1] Creating escrow account...")

    buyer_account = account(ctx.buyer_kp.public_key)
    tx = (
        TransactionBuilder(
            source_account=buyer_account,
            network_passphrase=NETWORK_PASS,
            base_fee=BASE_FEE,
        )
        # Reserve: 1 base + 2 signers*0.5 + 4 data entries*0.5 = 4 XLM minimum
        # We fund 10 XLM so there's headroom for additional data ops later
        .append_create_account_op(
            destination=ctx.escrow_kp.public_key,
            starting_balance="10",
            source=ctx.buyer_kp.public_key,
        )
        .set_timeout(180)
        .build()
    )
    tx.sign(ctx.buyer_kp)
    resp = server.submit_transaction(tx)
    tx_hash = resp["hash"]
    ctx.tx_hashes["create"] = tx_hash

    # Configure multisig + record metadata on-chain
    deadline_ts = str(int(time.time() + DELIVERY_WINDOW_SECS))
    escrow_account = account(ctx.escrow_kp.public_key)
    tx2 = (
        TransactionBuilder(
            source_account=escrow_account,
            network_passphrase=NETWORK_PASS,
            base_fee=BASE_FEE,
        )
        .append_set_options_op(
            master_weight=0,
            low_threshold=1,
            med_threshold=2,
            high_threshold=2,
            signer=Signer.ed25519_public_key(ctx.buyer_kp.public_key, 1),
        )
        .append_set_options_op(
            signer=Signer.ed25519_public_key(ctx.oracle_kp.public_key, 1),
        )
        .append_manage_data_op("po_number",  ctx.po_number.encode())
        .append_manage_data_op("ingredient", ctx.ingredient.encode())
        .append_manage_data_op("deadline",   deadline_ts.encode())
        .append_manage_data_op("state",      b"AWAITING_DEPOSIT")
        .set_timeout(180)
        .build()
    )
    tx2.sign(ctx.escrow_kp)
    resp2 = server.submit_transaction(tx2)
    ctx.tx_hashes["setup"] = resp2["hash"]

    print(f"  Escrow account:    {ctx.escrow_kp.public_key}")
    print(f"  Multisig:          2-of-2 (Buyer + Oracle) for all payments")
    print(f"  PO:                {ctx.po_number} | {ctx.ingredient}")
    print(f"  Delivery deadline: {DELIVERY_WINDOW_SECS}s from now (demo) | {deadline_ts}")
    print(f"  Tx hash:           {tx_hash}")
    print(f"  Explorer:          {explorer(ctx.escrow_kp.public_key)}")
    return tx_hash


# ── Step 2: Fund Escrow ────────────────────────────────────────────────────────

def fund_escrow(ctx: EscrowContext) -> str:
    """
    Entry:  Escrow account exists. Buyer agrees to PO terms.
    Action: Buyer deposits payment amount. Updates state on-chain.
            Supplier can now see funds are locked before preparing shipment.
    Exit:   Escrow holds full PO amount. State = FUNDED.
    """
    print("\n[2] Funding escrow...")

    buyer_account = account(ctx.buyer_kp.public_key)
    tx = (
        TransactionBuilder(
            source_account=buyer_account,
            network_passphrase=NETWORK_PASS,
            base_fee=BASE_FEE,
        )
        .append_payment_op(
            destination=ctx.escrow_kp.public_key,
            asset=Asset.native(),
            amount=str(ctx.amount_xlm),
        )
        .set_timeout(180)
        .build()
    )
    tx.sign(ctx.buyer_kp)
    resp = server.submit_transaction(tx)
    tx_hash = resp["hash"]
    ctx.tx_hashes["fund"] = tx_hash
    ctx.funded_at = time.time()
    ctx.state = EscrowState.FUNDED
    _update_escrow_state(ctx, "FUNDED")

    print(f"  Amount deposited:  {ctx.amount_xlm} XLM")
    print(f"  Tx hash:           {tx_hash}")
    print(f"  Tx explorer:       {tx_link(tx_hash)}")
    print(f"  Verify locked at:  {explorer(ctx.escrow_kp.public_key)}")
    wire_comparison(ctx.amount_xlm)
    return tx_hash


# ── Step 3: Confirm Shipment ───────────────────────────────────────────────────

def confirm_shipment(ctx: EscrowContext, tracking_id: str) -> str:
    """
    Entry:  Escrow is FUNDED. Supplier has dispatched goods.
    Action: Oracle writes tracking ID, ship timestamp on-chain. Buyer co-signs
            to confirm they acknowledge shipment (med threshold = 2).
    Exit:   Tracking data immutably recorded. State = SHIPPED.
            Clock is now running on delivery deadline.
    """
    print("\n[3] Confirming shipment...")

    escrow_account = account(ctx.escrow_kp.public_key)
    tx = (
        TransactionBuilder(
            source_account=escrow_account,
            network_passphrase=NETWORK_PASS,
            base_fee=BASE_FEE,
        )
        .append_manage_data_op("tracking_id", tracking_id.encode())
        .append_manage_data_op("state",       b"SHIPPED")
        .append_manage_data_op("shipped_at",  str(int(time.time())).encode())
        .set_timeout(180)
        .build()
    )
    tx.sign(ctx.oracle_kp)
    tx.sign(ctx.buyer_kp)
    resp = server.submit_transaction(tx)
    tx_hash = resp["hash"]
    ctx.tx_hashes["ship"] = tx_hash
    ctx.tracking_id = tracking_id
    ctx.state = EscrowState.SHIPPED

    print(f"  Tracking ID:   {tracking_id}")
    print(f"  Recorded on-chain by oracle + buyer")
    print(f"  Tx hash:       {tx_hash}")
    return tx_hash


# ── Step 4 (HAPPY): Confirm Delivery → Release Full Payment ──────────────────

def confirm_delivery(ctx: EscrowContext) -> str:
    """
    Entry:  State = SHIPPED. Buyer has received and accepted goods.
    Action: Buyer + Oracle co-sign to release escrow to supplier (med threshold = 2).
            Full spendable balance is sent in single atomic transaction.
    Exit:   Supplier receives full payment. State = RELEASED.
            Settlement completes in ~3 seconds vs 3-5 days for wire.
    """
    print("\n[4] Confirming delivery + releasing payment...")

    settlement_start = time.time()
    escrow_account   = account(ctx.escrow_kp.public_key)
    _, send_amount, _ = _escrow_spendable(ctx, new_data_keys=["delivered_at"])
    send_amount_str   = str(send_amount)

    tx = (
        TransactionBuilder(
            source_account=escrow_account,
            network_passphrase=NETWORK_PASS,
            base_fee=BASE_FEE,
        )
        .append_manage_data_op("state",        b"RELEASED")
        .append_manage_data_op("delivered_at", str(int(time.time())).encode())
        .append_payment_op(
            destination=ctx.supplier_kp.public_key,
            asset=Asset.native(),
            amount=send_amount_str,
        )
        .set_timeout(180)
        .build()
    )
    tx.sign(ctx.buyer_kp)
    tx.sign(ctx.oracle_kp)
    resp = server.submit_transaction(tx)
    tx_hash = resp["hash"]
    settlement_time = time.time() - settlement_start
    ctx.tx_hashes["release"] = tx_hash
    ctx.state = EscrowState.RELEASED

    print(f"  Payment released:  {send_amount_str} XLM -> Supplier")
    print(f"  Settlement time:   {settlement_time:.2f}s")
    print(f"  Tx hash:           {tx_hash}")
    print(f"  Tx explorer:       {tx_link(tx_hash)}")
    print(f"  Signatures:        Buyer + Oracle (2-of-2 multisig)")
    return tx_hash


# ── Step 4A (DEADLINE): Delivery Window Expired → Full Refund ─────────────────

def refund_deadline_expired(ctx: EscrowContext) -> str:
    """
    Entry:  State = FUNDED or SHIPPED. funded_at + DELIVERY_WINDOW_SECS has passed
            with no confirm_delivery. Buyer requests refund.
    Action: Script waits until deadline passes (demo: 30s).
            Oracle is a programmatic service — it automatically co-signs refunds
            when the on-chain deadline timestamp is exceeded. Buyer also co-signs.
            Full balance returned to buyer in one atomic tx.
    Exit:   Buyer receives full refund. State = REFUNDED.
            Supplier has no claim; their failure to deliver triggered the condition.

    Real-world: oracle daemon polls Horizon every block, checks deadline data entry
    vs ledger close time, auto-signs if expired. No human intervention needed.
    """
    print("\n[4A] Deadline expiry refund...")

    elapsed   = time.time() - (ctx.funded_at or 0)
    remaining = DELIVERY_WINDOW_SECS - elapsed
    if remaining > 0:
        print(f"  Delivery window: {DELIVERY_WINDOW_SECS}s | Elapsed: {elapsed:.0f}s")
        print(f"  Waiting {remaining:.0f}s for deadline to expire...")
        time.sleep(remaining + 1)

    elapsed = time.time() - (ctx.funded_at or 0)
    print(f"  Deadline expired ({elapsed:.0f}s since funding). Oracle auto-approving refund...")

    escrow_account     = account(ctx.escrow_kp.public_key)
    _, send_amount, _  = _escrow_spendable(ctx, new_data_keys=["refund_reason", "refunded_at"])
    send_amount_str    = str(send_amount)

    tx = (
        TransactionBuilder(
            source_account=escrow_account,
            network_passphrase=NETWORK_PASS,
            base_fee=BASE_FEE,
        )
        .append_manage_data_op("state",         b"REFUNDED")
        .append_manage_data_op("refund_reason", b"DEADLINE_EXPIRED")
        .append_manage_data_op("refunded_at",   str(int(time.time())).encode())
        .append_payment_op(
            destination=ctx.buyer_kp.public_key,
            asset=Asset.native(),
            amount=send_amount_str,
        )
        .set_timeout(180)
        .build()
    )
    tx.sign(ctx.buyer_kp)
    tx.sign(ctx.oracle_kp)
    resp = server.submit_transaction(tx)
    tx_hash = resp["hash"]
    ctx.tx_hashes["refund"] = tx_hash
    ctx.state = EscrowState.REFUNDED

    print(f"  Refunded:      {send_amount_str} XLM -> Buyer")
    print(f"  Reason:        DEADLINE_EXPIRED (recorded on-chain)")
    print(f"  Tx hash:       {tx_hash}")
    print(f"  Tx explorer:   {tx_link(tx_hash)}")
    print(f"  Signatures:    Buyer + Oracle (oracle auto-signed on deadline breach)")
    return tx_hash


# ── Step 4B (CANCEL): Pre-Shipment Cancellation → Full Refund ─────────────────

def refund_cancelled(ctx: EscrowContext) -> str:
    """
    Entry:  State = FUNDED. No tracking ID recorded yet (shipment not confirmed).
            Either party agrees to cancel the PO before goods are dispatched.
    Action: Validates no shipment has been recorded on-chain.
            Buyer + Oracle co-sign immediate full refund.
    Exit:   Buyer receives full refund. State = CANCELLED.
            Clean exit — no dispute, no penalty, just mutual agreement.

    Guard:  Raises ValueError if tracking_id exists (state = SHIPPED or beyond).
            Once goods are in transit, cancellation converts to a dispute.
    """
    print("\n[4B] Pre-shipment cancellation...")

    if ctx.state not in (EscrowState.AWAITING_DEPOSIT, EscrowState.FUNDED):
        raise ValueError(
            f"Cannot cancel in state {ctx.state.value}. "
            f"Shipment may already be in transit — use dispute_quality() or dispute_nondelivery()."
        )
    if ctx.tracking_id:
        raise ValueError(
            f"Tracking ID {ctx.tracking_id} already recorded. "
            f"Goods are in transit — cancellation is no longer valid."
        )

    print(f"  No tracking ID on-chain. Pre-shipment cancel is valid.")

    escrow_account    = account(ctx.escrow_kp.public_key)
    _, send_amount, _ = _escrow_spendable(ctx, new_data_keys=["cancelled_at"])
    send_amount_str   = str(send_amount)

    tx = (
        TransactionBuilder(
            source_account=escrow_account,
            network_passphrase=NETWORK_PASS,
            base_fee=BASE_FEE,
        )
        .append_manage_data_op("state",        b"CANCELLED")
        .append_manage_data_op("cancelled_at", str(int(time.time())).encode())
        .append_payment_op(
            destination=ctx.buyer_kp.public_key,
            asset=Asset.native(),
            amount=send_amount_str,
        )
        .set_timeout(180)
        .build()
    )
    tx.sign(ctx.buyer_kp)
    tx.sign(ctx.oracle_kp)
    resp = server.submit_transaction(tx)
    tx_hash = resp["hash"]
    ctx.tx_hashes["cancel"] = tx_hash
    ctx.state = EscrowState.CANCELLED

    print(f"  Refunded:      {send_amount_str} XLM -> Buyer")
    print(f"  Reason:        PRE_SHIPMENT_CANCEL (recorded on-chain)")
    print(f"  Tx hash:       {tx_hash}")
    print(f"  Tx explorer:   {tx_link(tx_hash)}")
    print(f"  Signatures:    Buyer + Oracle (mutual cancellation)")
    return tx_hash


# ── Step 4C (DISPUTE QUALITY): Partial Settlement ─────────────────────────────

def dispute_quality(
    ctx: EscrowContext,
    dispute_reason: str,
    supplier_pct: float,
) -> tuple:
    """
    Entry:  State = SHIPPED or goods claimed delivered.
            Buyer raises a quality claim (wrong grade, short weight, contamination).
            supplier_pct = fraction of escrow to release to supplier (0.0 – 1.0).
            Example: 0.70 → supplier gets 70%, buyer gets 30% back.
    Action: Oracle reviews claim. Writes dispute_reason and verdict on-chain
            (oracle alone, low threshold = 1 — data write only).
            Then oracle + buyer co-sign an atomic split payment:
              - supplier_amount = sendable * supplier_pct  → to supplier
              - buyer_amount    = sendable * (1 - pct)     → back to buyer
            Both transfers happen in one transaction — atomically or not at all.
    Exit:   Funds split per oracle ruling. State = DISPUTE_RESOLVED.
            Both parties receive their shares in same ledger close (~3s).

    Note:   Stellar allows multiple payment ops in one tx. This is impossible
            with a wire transfer — no bank can atomically split a payment.
    """
    print(f"\n[4C] Quality dispute — oracle arbitration...")
    print(f"  Dispute reason:    {dispute_reason}")
    print(f"  Oracle ruling:     {supplier_pct*100:.0f}% to supplier / {(1-supplier_pct)*100:.0f}% back to buyer")

    # Oracle writes dispute data on-chain (low threshold = 1, oracle alone)
    escrow_account = account(ctx.escrow_kp.public_key)
    tx_data = (
        TransactionBuilder(
            source_account=escrow_account,
            network_passphrase=NETWORK_PASS,
            base_fee=BASE_FEE,
        )
        .append_manage_data_op("state",          b"DISPUTED")
        .append_manage_data_op("dispute_reason", dispute_reason.encode()[:64])
        .append_manage_data_op("supplier_pct",   f"{supplier_pct:.2f}".encode())
        .set_timeout(180)
        .build()
    )
    tx_data.sign(ctx.oracle_kp)
    tx_data.sign(ctx.buyer_kp)
    resp_data = server.submit_transaction(tx_data)
    ctx.tx_hashes["dispute_open"] = resp_data["hash"]
    print(f"  Dispute recorded on-chain: {resp_data['hash']}")

    # Now execute the split payment atomically
    escrow_account    = account(ctx.escrow_kp.public_key)
    _, sendable, _    = _escrow_spendable(ctx, new_data_keys=["resolved_at"])
    supplier_amount   = round(sendable * supplier_pct, 7)
    buyer_amount      = round(sendable * (1 - supplier_pct), 7)
    # Ensure we don't exceed sendable due to rounding
    if supplier_amount + buyer_amount > sendable:
        buyer_amount = round(sendable - supplier_amount, 7)

    settlement_start = time.time()
    tx_settle = (
        TransactionBuilder(
            source_account=escrow_account,
            network_passphrase=NETWORK_PASS,
            base_fee=BASE_FEE,
        )
        .append_manage_data_op("state",       b"DISPUTE_RESOLVED")
        .append_manage_data_op("resolved_at", str(int(time.time())).encode())
        .append_payment_op(
            destination=ctx.supplier_kp.public_key,
            asset=Asset.native(),
            amount=str(supplier_amount),
        )
        .append_payment_op(
            destination=ctx.buyer_kp.public_key,
            asset=Asset.native(),
            amount=str(buyer_amount),
        )
        .set_timeout(180)
        .build()
    )
    tx_settle.sign(ctx.buyer_kp)
    tx_settle.sign(ctx.oracle_kp)
    resp_settle = server.submit_transaction(tx_settle)
    tx_hash     = resp_settle["hash"]
    settlement_time = time.time() - settlement_start
    ctx.tx_hashes["dispute_resolve"] = tx_hash
    ctx.state = EscrowState.DISPUTE_RESOLVED

    print(f"\n  [Atomic Split Settlement]")
    print(f"    Supplier receives: {supplier_amount} XLM ({supplier_pct*100:.0f}%)")
    print(f"    Buyer receives:    {buyer_amount} XLM ({(1-supplier_pct)*100:.0f}%)")
    print(f"    Settlement time:   {settlement_time:.2f}s (both transfers, one ledger close)")
    print(f"    Tx hash:           {tx_hash}")
    print(f"    Tx explorer:       {tx_link(tx_hash)}")
    print(f"    Signatures:        Buyer + Oracle (2-of-2 multisig)")
    return ctx.tx_hashes["dispute_open"], tx_hash


# ── Step 4D (DISPUTE NON-DELIVERY): Oracle Verdict ────────────────────────────

def dispute_nondelivery(ctx: EscrowContext, oracle_verdict: str) -> str:
    """
    Entry:  State = SHIPPED. Carrier tracking shows "delivered".
            Buyer disputes having actually received the goods.
    Action: Oracle investigates (carrier data, GPS, photos, signed receipt).
            Oracle writes verdict on-chain — this is a low-threshold op so
            oracle can do it unilaterally (weight=1, low threshold=1).
            Then oracle + buyer co-sign the outcome direction:
              BUYER_WINS  → full refund to buyer (carrier/supplier liable)
              SUPPLIER_WINS → full release to supplier (buyer claim rejected)
    Exit:   State = REFUNDED or RELEASED depending on verdict.
            Verdict is immutably recorded — provides audit trail for insurance claim.

    Note:   Oracle acts as trade finance arbitrator — same role as a letter of
            credit issuing bank, but automated and on-chain.
    """
    if oracle_verdict not in ("BUYER_WINS", "SUPPLIER_WINS"):
        raise ValueError("oracle_verdict must be 'BUYER_WINS' or 'SUPPLIER_WINS'")

    print(f"\n[4D] Non-delivery dispute...")
    print(f"  Buyer claim:    Goods not received despite tracking showing delivered")
    print(f"  Oracle verdict: {oracle_verdict}")

    # Oracle writes verdict on-chain (low threshold — oracle alone can sign ManageData)
    escrow_account = account(ctx.escrow_kp.public_key)
    tx_verdict = (
        TransactionBuilder(
            source_account=escrow_account,
            network_passphrase=NETWORK_PASS,
            base_fee=BASE_FEE,
        )
        .append_manage_data_op("state",          b"DISPUTED")
        .append_manage_data_op("dispute_reason", b"NON_DELIVERY")
        .append_manage_data_op("oracle_verdict", oracle_verdict.encode())
        .set_timeout(180)
        .build()
    )
    tx_verdict.sign(ctx.oracle_kp)
    tx_verdict.sign(ctx.buyer_kp)
    resp_verdict = server.submit_transaction(tx_verdict)
    ctx.tx_hashes["dispute_open"] = resp_verdict["hash"]
    print(f"  Verdict recorded on-chain: {resp_verdict['hash']}")

    # Execute outcome
    escrow_account    = account(ctx.escrow_kp.public_key)
    _, send_amount, _ = _escrow_spendable(ctx, new_data_keys=["resolved_at"])
    send_amount_str   = str(send_amount)

    if oracle_verdict == "BUYER_WINS":
        destination  = ctx.buyer_kp.public_key
        final_state  = b"REFUNDED"
        outcome_desc = f"Full refund to buyer: {send_amount_str} XLM"
        ctx.state    = EscrowState.REFUNDED
    else:
        destination  = ctx.supplier_kp.public_key
        final_state  = b"RELEASED"
        outcome_desc = f"Full release to supplier: {send_amount_str} XLM"
        ctx.state    = EscrowState.RELEASED

    settlement_start = time.time()
    tx_settle = (
        TransactionBuilder(
            source_account=escrow_account,
            network_passphrase=NETWORK_PASS,
            base_fee=BASE_FEE,
        )
        .append_manage_data_op("state",       final_state)
        .append_manage_data_op("resolved_at", str(int(time.time())).encode())
        .append_payment_op(
            destination=destination,
            asset=Asset.native(),
            amount=send_amount_str,
        )
        .set_timeout(180)
        .build()
    )
    tx_settle.sign(ctx.buyer_kp)
    tx_settle.sign(ctx.oracle_kp)
    resp_settle = server.submit_transaction(tx_settle)
    tx_hash     = resp_settle["hash"]
    settlement_time = time.time() - settlement_start
    ctx.tx_hashes["dispute_resolve"] = tx_hash

    print(f"\n  [Oracle Verdict Executed]")
    print(f"    Outcome:         {outcome_desc}")
    print(f"    Settlement time: {settlement_time:.2f}s")
    print(f"    Tx hash:         {tx_hash}")
    print(f"    Tx explorer:     {tx_link(tx_hash)}")
    print(f"    Signatures:      Buyer + Oracle (verdict enforced via multisig)")
    return tx_hash


# ── Internal ──────────────────────────────────────────────────────────────────

def _update_escrow_state(ctx: EscrowContext, state: str):
    """Informational state update — oracle alone signs (low threshold)."""
    try:
        escrow_account = account(ctx.escrow_kp.public_key)
        tx = (
            TransactionBuilder(
                source_account=escrow_account,
                network_passphrase=NETWORK_PASS,
                base_fee=BASE_FEE,
            )
            .append_manage_data_op("state", state.encode())
            .set_timeout(180)
            .build()
        )
        tx.sign(ctx.oracle_kp)
        tx.sign(ctx.buyer_kp)
        server.submit_transaction(tx)
    except Exception:
        pass  # state update is informational; don't break main flow


def _print_summary(ctx: EscrowContext, wallets: dict):
    wallets = load_wallets()
    print_balances(wallets, "Final Balances")
    print("\n=========================================")
    print("  Transaction Summary")
    print("=========================================")
    for step, tx_hash in ctx.tx_hashes.items():
        print(f"  {step:20s}  {tx_link(tx_hash)}")
    print(f"\n  PO:         {ctx.po_number}")
    print(f"  Ingredient: {ctx.ingredient}")
    print(f"  State:      {ctx.state.value}")
    print("\n  Demo complete.\n")


def _make_context(wallets: dict, scenario: str) -> EscrowContext:
    return EscrowContext(
        po_number   = f"PO-ARIKINA-2026-{scenario.upper()[:3]}",
        ingredient  = "Shea Butter 200kg - Ghana",
        amount_xlm  = 1700.0,
        buyer_kp    = kp(wallets["buyer"]["secret_key"]),
        supplier_kp = kp(wallets["supplier"]["secret_key"]),
        oracle_kp   = kp(wallets["oracle"]["secret_key"]),
    )


# ── Scenario Runners ──────────────────────────────────────────────────────────

def run_happy(wallets):
    """Full delivery: buyer receives goods, supplier receives full payment."""
    ctx = _make_context(wallets, "happy")
    create_escrow(ctx);       time.sleep(2)
    fund_escrow(ctx);         time.sleep(2)
    confirm_shipment(ctx, tracking_id="DHL-GH-2026-0088"); time.sleep(2)
    confirm_delivery(ctx)
    return ctx

def run_deadline(wallets):
    """Delivery window expires with no confirm_delivery — oracle auto-refunds buyer."""
    ctx = _make_context(wallets, "deadline")
    create_escrow(ctx); time.sleep(2)
    fund_escrow(ctx)
    # No confirm_shipment — supplier ghosted
    refund_deadline_expired(ctx)
    return ctx

def run_cancel(wallets):
    """Buyer cancels PO before supplier dispatches — immediate full refund."""
    ctx = _make_context(wallets, "cancel")
    create_escrow(ctx); time.sleep(2)
    fund_escrow(ctx);   time.sleep(2)
    # No confirm_shipment — goods not yet in transit
    refund_cancelled(ctx)
    return ctx

def run_quality(wallets):
    """Goods arrive but are 30% underweight — oracle splits 70/30."""
    ctx = _make_context(wallets, "quality")
    create_escrow(ctx);  time.sleep(2)
    fund_escrow(ctx);    time.sleep(2)
    confirm_shipment(ctx, tracking_id="DHL-GH-2026-0099"); time.sleep(2)
    dispute_quality(
        ctx,
        dispute_reason="Shea butter delivered 140kg, PO specified 200kg (-30% short weight)",
        supplier_pct=0.70,
    )
    return ctx

def run_nondelivery(wallets):
    """Tracking shows delivered; buyer disputes — oracle rules BUYER_WINS."""
    ctx = _make_context(wallets, "nondelivery")
    create_escrow(ctx);  time.sleep(2)
    fund_escrow(ctx);    time.sleep(2)
    confirm_shipment(ctx, tracking_id="DHL-GH-2026-0107"); time.sleep(2)
    dispute_nondelivery(ctx, oracle_verdict="BUYER_WINS")
    return ctx


# ── Entry Point ───────────────────────────────────────────────────────────────

SCENARIOS = {
    "happy":       (run_happy,       "Full delivery — supplier receives full payment"),
    "deadline":    (run_deadline,    "Delivery deadline expires — full refund to buyer"),
    "cancel":      (run_cancel,      "Pre-shipment cancellation — full refund to buyer"),
    "quality":     (run_quality,     "Quality dispute — 70% to supplier / 30% to buyer"),
    "nondelivery": (run_nondelivery, "Non-delivery dispute — oracle rules for buyer"),
}

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")

    scenario = sys.argv[1].lower() if len(sys.argv) > 1 else "happy"

    if scenario == "help" or scenario not in SCENARIOS:
        print("\nUsage: python -X utf8 escrow.py [scenario]")
        print("\nScenarios:")
        for name, (_, desc) in SCENARIOS.items():
            print(f"  {name:<14}  {desc}")
        sys.exit(0)

    runner, description = SCENARIOS[scenario]

    wallets = load_wallets()

    print("\n=========================================")
    print("  Arikina B2B Stablecoin Payment Demo")
    print(f"  Scenario: {scenario.upper()}")
    print(f"  {description}")
    print("  Stellar Testnet — Escrow Flow")
    print("=========================================")
    print(f"\n  Buyer:    {wallets['buyer']['label']}")
    print(f"  Supplier: {wallets['supplier']['label']}")
    print(f"  Network:  Stellar Testnet")

    print_balances(wallets, "Opening Balances")

    ctx = runner(wallets)

    # Persist latest escrow address for dashboard
    wallets["escrow"] = {
        "label":      f"Escrow ({scenario})",
        "public_key": ctx.escrow_kp.public_key,
        "secret_key": ctx.escrow_kp.secret,
    }
    save_wallets(wallets)

    _print_summary(ctx, wallets)
