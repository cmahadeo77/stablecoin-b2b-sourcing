"""
Stablecoin B2B Payment Flow — Ingredient Sourcing
Personal Care Brand Example

Simulates the core payment orchestration logic for paying ingredient
suppliers via USDC stablecoin with escrow and delivery confirmation.

NOTE: Wallet addresses, supplier names, and order values are illustrative.
      In production, integrate with Circle Payments API and a deployed
      SupplierEscrow smart contract.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional
import hashlib
import json
import uuid


class PaymentStatus(Enum):
    DRAFT = "draft"
    ESCROWED = "escrowed"
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    RELEASED = "released"
    DISPUTED = "disputed"
    REFUNDED = "refunded"


class IngredientCategory(Enum):
    BOTANICAL = "botanical"
    LIPID = "lipid"          # oils, butters
    FRAGRANCE = "fragrance"
    ACTIVE = "active"        # vitamins, peptides, etc.
    PRESERVATIVE = "preservative"
    SURFACTANT = "surfactant"


@dataclass
class Supplier:
    name: str
    country: str
    wallet_address: str
    category: IngredientCategory
    verified: bool = False
    payment_history: list = field(default_factory=list)

    def to_dict(self):
        return {
            "name": self.name,
            "country": self.country,
            "wallet": self.wallet_address,
            "category": self.category.value,
            "verified": self.verified,
            "transactions": len(self.payment_history),
        }


@dataclass
class PurchaseOrder:
    po_number: str
    supplier: Supplier
    ingredient: str
    quantity_kg: float
    unit_price_usd: float
    buyer_wallet: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    status: PaymentStatus = PaymentStatus.DRAFT
    escrow_tx_hash: Optional[str] = None
    delivery_tx_hash: Optional[str] = None
    release_tx_hash: Optional[str] = None
    expected_delivery: Optional[datetime] = None

    @property
    def total_usdc(self) -> float:
        return round(self.quantity_kg * self.unit_price_usd, 2)

    @property
    def traditional_wire_cost(self) -> float:
        """Estimate cost of paying via traditional wire transfer."""
        wire_fee = 45.0
        fx_spread = self.total_usdc * 0.03  # ~3% FX spread
        return round(wire_fee + fx_spread, 2)

    @property
    def stablecoin_cost(self) -> float:
        """Estimate cost of paying via stablecoin (Stellar/Solana)."""
        return round(self.total_usdc * 0.0001, 4)  # ~0.01% network fee

    @property
    def savings(self) -> float:
        return round(self.traditional_wire_cost - self.stablecoin_cost, 2)

    def to_dict(self):
        return {
            "po_number": self.po_number,
            "supplier": self.supplier.name,
            "country": self.supplier.country,
            "ingredient": self.ingredient,
            "quantity_kg": self.quantity_kg,
            "unit_price_usd": self.unit_price_usd,
            "total_usdc": self.total_usdc,
            "status": self.status.value,
            "wire_cost_estimate": self.traditional_wire_cost,
            "stablecoin_cost_estimate": self.stablecoin_cost,
            "savings": self.savings,
            "escrow_tx": self.escrow_tx_hash,
            "delivery_tx": self.delivery_tx_hash,
            "release_tx": self.release_tx_hash,
        }


class EscrowPaymentOrchestrator:
    """
    Orchestrates B2B stablecoin payments with escrow.

    In production this wraps Circle's Payments API and a deployed
    smart contract. Here it simulates the state machine and logs
    the economics.
    """

    def __init__(self, buyer_name: str, buyer_wallet: str):
        self.buyer_name = buyer_name
        self.buyer_wallet = buyer_wallet
        self.purchase_orders: dict[str, PurchaseOrder] = {}
        self.total_savings = 0.0

    def _mock_tx_hash(self, label: str) -> str:
        raw = f"{label}-{uuid.uuid4()}"
        return "0x" + hashlib.sha256(raw.encode()).hexdigest()[:40]

    def create_po(
        self,
        supplier: Supplier,
        ingredient: str,
        quantity_kg: float,
        unit_price_usd: float,
        delivery_days: int = 21,
    ) -> PurchaseOrder:
        po_number = f"PO-{datetime.utcnow().strftime('%Y%m%d')}-{str(uuid.uuid4())[:6].upper()}"
        po = PurchaseOrder(
            po_number=po_number,
            supplier=supplier,
            ingredient=ingredient,
            quantity_kg=quantity_kg,
            unit_price_usd=unit_price_usd,
            buyer_wallet=self.buyer_wallet,
            expected_delivery=datetime.utcnow() + timedelta(days=delivery_days),
        )
        self.purchase_orders[po_number] = po
        print(f"[PO CREATED] {po_number} | {ingredient} | {quantity_kg}kg | ${po.total_usdc} USDC")
        return po

    def fund_escrow(self, po: PurchaseOrder) -> str:
        """Deposit USDC into escrow smart contract."""
        assert po.status == PaymentStatus.DRAFT, "PO must be in DRAFT to fund escrow"

        tx_hash = self._mock_tx_hash("escrow")
        po.escrow_tx_hash = tx_hash
        po.status = PaymentStatus.ESCROWED

        print(f"\n[ESCROW FUNDED] {po.po_number}")
        print(f"  Amount:      ${po.total_usdc} USDC")
        print(f"  Tx hash:     {tx_hash}")
        print(f"  From:        {self.buyer_wallet[:10]}...")
        print(f"  To (escrow): contract-{po.po_number.lower()}")
        print(f"  Supplier:    {po.supplier.name} ({po.supplier.country})")
        print(f"  Cost savings vs wire: ${po.savings}")
        return tx_hash

    def confirm_shipment(self, po: PurchaseOrder, tracking_id: str) -> None:
        assert po.status == PaymentStatus.ESCROWED
        po.status = PaymentStatus.IN_TRANSIT
        print(f"\n[SHIPMENT CONFIRMED] {po.po_number} | Tracking: {tracking_id}")

    def confirm_delivery(self, po: PurchaseOrder) -> str:
        """Oracle triggers delivery confirmation — releases escrow."""
        assert po.status == PaymentStatus.IN_TRANSIT

        delivery_tx = self._mock_tx_hash("delivery")
        release_tx = self._mock_tx_hash("release")

        po.delivery_tx_hash = delivery_tx
        po.release_tx_hash = release_tx
        po.status = PaymentStatus.RELEASED

        po.supplier.payment_history.append(po.po_number)
        self.total_savings += po.savings

        print(f"\n[DELIVERY CONFIRMED + PAYMENT RELEASED] {po.po_number}")
        print(f"  Delivery confirmed: {delivery_tx}")
        print(f"  Payment released:   {release_tx}")
        print(f"  Supplier received:  ${po.total_usdc} USDC instantly")
        print(f"  Cumulative savings: ${self.total_savings:.2f}")
        return release_tx

    def print_summary(self):
        print("\n" + "=" * 60)
        print(f"PAYMENT SUMMARY — {self.buyer_name}")
        print("=" * 60)
        total_volume = sum(po.total_usdc for po in self.purchase_orders.values())
        released = [po for po in self.purchase_orders.values() if po.status == PaymentStatus.RELEASED]
        print(f"  Total POs:          {len(self.purchase_orders)}")
        print(f"  Released:           {len(released)}")
        print(f"  Total USDC volume:  ${total_volume:,.2f}")
        print(f"  Total savings:      ${self.total_savings:,.2f}")
        print(f"  Avg savings/PO:     ${self.total_savings / max(len(released), 1):,.2f}")
        print("=" * 60)
        print("\nPurchase Order Details:")
        for po in self.purchase_orders.values():
            print(f"\n  {po.po_number}")
            print(f"    {po.ingredient} from {po.supplier.name} ({po.supplier.country})")
            print(f"    {po.quantity_kg}kg @ ${po.unit_price_usd}/kg = ${po.total_usdc} USDC")
            print(f"    Status: {po.status.value}")
            print(f"    Wire would have cost: ${po.traditional_wire_cost} | Saved: ${po.savings}")


# ---------------------------------------------------------------------------
# Demo: Arikina sourcing run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Supplier registry
    shea_supplier = Supplier(
        name="Nkemdirim Naturals Cooperative",
        country="Ghana",
        wallet_address="GBNKOSI...STELLAR_ADDR",
        category=IngredientCategory.LIPID,
        verified=True,
    )
    argan_supplier = Supplier(
        name="Atlas Botanicals SARL",
        country="Morocco",
        wallet_address="GAMOROC...STELLAR_ADDR",
        category=IngredientCategory.LIPID,
        verified=True,
    )
    fragrance_supplier = Supplier(
        name="Givaudan India Ltd",
        country="India",
        wallet_address="GAINDIx...STELLAR_ADDR",
        category=IngredientCategory.FRAGRANCE,
        verified=False,
    )

    # Initialize orchestrator — replace with your brand name and Circle wallet address
    orchestrator = EscrowPaymentOrchestrator(
        buyer_name="Your Brand Name",
        buyer_wallet="GA_YOUR_STELLAR_WALLET_ADDRESS_HERE",
    )

    # PO 1: Shea butter from Ghana
    po1 = orchestrator.create_po(shea_supplier, "Raw Shea Butter (Grade A)", quantity_kg=200, unit_price_usd=8.50)
    orchestrator.fund_escrow(po1)
    orchestrator.confirm_shipment(po1, "DHL-GH-2026-0088")
    orchestrator.confirm_delivery(po1)

    # PO 2: Argan oil from Morocco
    po2 = orchestrator.create_po(argan_supplier, "Cold-Press Argan Oil (Certified Organic)", quantity_kg=50, unit_price_usd=42.00)
    orchestrator.fund_escrow(po2)
    orchestrator.confirm_shipment(po2, "FedEx-MA-2026-0412")
    orchestrator.confirm_delivery(po2)

    # PO 3: Fragrance compound (new supplier — escrow provides trust)
    po3 = orchestrator.create_po(fragrance_supplier, "Jasmine Absolute Compound", quantity_kg=10, unit_price_usd=185.00, delivery_days=30)
    orchestrator.fund_escrow(po3)
    orchestrator.confirm_shipment(po3, "UPS-IN-2026-9901")
    # Delivery pending — still IN_TRANSIT

    orchestrator.print_summary()
