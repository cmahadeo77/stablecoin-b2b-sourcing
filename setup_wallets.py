"""
setup_wallets.py — One-time Stellar testnet wallet setup
Creates and funds 3 accounts: Buyer (Arikina), Supplier (Overseas Partner), Oracle (Delivery)
Run: python setup_wallets.py
Saves keypairs to wallets.json
"""

import json
import requests
from stellar_sdk import Keypair

WALLETS_FILE = "wallets.json"
FRIENDBOT    = "https://friendbot.stellar.org"

ROLES = [
    ("buyer",    "Arikina (Buyer)"),
    ("supplier", "Overseas Supplier"),
    ("oracle",   "Delivery Oracle"),
]

def fund_account(public_key: str, label: str) -> bool:
    print(f"  Funding {label} via Friendbot...", end=" ")
    r = requests.get(FRIENDBOT, params={"addr": public_key}, timeout=30)
    if r.status_code == 200:
        print("✓")
        return True
    else:
        print(f"✗ ({r.status_code})")
        return False

def main():
    print("\n─────────────────────────────────────────")
    print("  Stellar Testnet Wallet Setup")
    print("─────────────────────────────────────────\n")

    wallets = {}
    for role, label in ROLES:
        kp = Keypair.random()
        wallets[role] = {
            "label":       label,
            "public_key":  kp.public_key,
            "secret_key":  kp.secret,
        }
        print(f"[{label}]")
        print(f"  Public key: {kp.public_key}")
        print(f"  Secret key: {kp.secret}")
        fund_account(kp.public_key, label)
        print()

    with open(WALLETS_FILE, "w") as f:
        json.dump(wallets, f, indent=2)

    print(f"✓ Wallets saved to {WALLETS_FILE}")
    print("\nStellar Explorer links (testnet):")
    for role, data in wallets.items():
        print(f"  {data['label']}: https://stellar.expert/explorer/testnet/account/{data['public_key']}")

    print("\nNext: python escrow.py\n")

if __name__ == "__main__":
    main()
