"""
generate_use_case_pdf.py — Arikina B2B Stablecoin Escrow: Use Case Reference
Generates a formatted PDF documenting all 5 escrow scenarios.
Run: python -X utf8 generate_use_case_pdf.py
"""

import sys
sys.stdout.reconfigure(encoding="utf-8")

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY

OUTPUT = "Arikina_B2B_Escrow_Use_Cases.pdf"

# ── Brand colors ──────────────────────────────────────────────────────────────
NAVY   = colors.HexColor("#0D1B2A")
TEAL   = colors.HexColor("#1A7A72")
GOLD   = colors.HexColor("#C9A84C")
LIGHT  = colors.HexColor("#F5F5F0")
MID    = colors.HexColor("#E8E8E0")
WHITE  = colors.white
RED    = colors.HexColor("#B03A2E")
GREEN  = colors.HexColor("#1E8449")
ORANGE = colors.HexColor("#CA6F1E")

# ── Styles ────────────────────────────────────────────────────────────────────
base = getSampleStyleSheet()

def style(name, parent="Normal", **kw):
    s = ParagraphStyle(name, parent=base[parent], **kw)
    return s

H1     = style("H1",     "Normal",  fontSize=22, leading=28, textColor=NAVY,
               fontName="Helvetica-Bold", spaceAfter=6)
H2     = style("H2",     "Normal",  fontSize=14, leading=18, textColor=WHITE,
               fontName="Helvetica-Bold")
H3     = style("H3",     "Normal",  fontSize=11, leading=15, textColor=NAVY,
               fontName="Helvetica-Bold", spaceBefore=8, spaceAfter=4)
BODY   = style("BODY",   "Normal",  fontSize=9.5, leading=14, textColor=NAVY,
               fontName="Helvetica", spaceAfter=4)
SMALL  = style("SMALL",  "Normal",  fontSize=8.5, leading=12, textColor=colors.HexColor("#444"),
               fontName="Helvetica", spaceAfter=3)
CODE   = style("CODE",   "Normal",  fontSize=8,   leading=11, textColor=NAVY,
               fontName="Courier", backColor=MID, leftIndent=6, rightIndent=6,
               spaceAfter=4, spaceBefore=4)
BULLET = style("BULLET", "Normal",  fontSize=9.5, leading=14, textColor=NAVY,
               fontName="Helvetica", leftIndent=16, spaceAfter=3,
               bulletIndent=6)
LABEL  = style("LABEL",  "Normal",  fontSize=8,   leading=10, textColor=WHITE,
               fontName="Helvetica-Bold")
TAGLINE = style("TAGLINE","Normal", fontSize=10.5, leading=14,
                textColor=colors.HexColor("#555"), fontName="Helvetica-Oblique",
                spaceAfter=12)
CAPTION = style("CAPTION","Normal", fontSize=8, leading=11,
                textColor=colors.HexColor("#666"), fontName="Helvetica-Oblique",
                spaceAfter=6)

# ── Helpers ───────────────────────────────────────────────────────────────────

def section_header(title, subtitle=None, color=TEAL):
    """Colored banner row used for each scenario heading."""
    inner = [Paragraph(title, H2)]
    if subtitle:
        sub_style = ParagraphStyle("sub", parent=H2, fontSize=8.5,
                                   textColor=colors.HexColor("#CCE9E6"), fontName="Helvetica")
        inner.append(Paragraph(subtitle, sub_style))
    t = Table([[inner]], colWidths=[6.5*inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), color),
        ("TOPPADDING",  (0,0), (-1,-1), 8),
        ("BOTTOMPADDING",(0,0),(-1,-1), 8),
        ("LEFTPADDING", (0,0), (-1,-1), 10),
        ("RIGHTPADDING",(0,0), (-1,-1), 10),
        ("ROUNDEDCORNERS", [4]),
    ]))
    return t

def kv_table(rows, col1=1.6*inch, col2=4.9*inch):
    """Two-column label/value table."""
    data = []
    for k, v in rows:
        data.append([
            Paragraph(k, SMALL),
            Paragraph(v, SMALL),
        ])
    t = Table(data, colWidths=[col1, col2])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (0,-1), MID),
        ("BACKGROUND", (1,0), (1,-1), WHITE),
        ("LINEBELOW",  (0,0), (-1,-2), 0.3, colors.HexColor("#DDD")),
        ("TOPPADDING",  (0,0), (-1,-1), 4),
        ("BOTTOMPADDING",(0,0),(-1,-1), 4),
        ("LEFTPADDING", (0,0), (-1,-1), 6),
        ("RIGHTPADDING",(0,0),(-1,-1), 6),
        ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 8.5),
        ("VALIGN",   (0,0), (-1,-1), "TOP"),
        ("BOX", (0,0), (-1,-1), 0.5, colors.HexColor("#CCC")),
    ]))
    return t

def flow_table(steps):
    """Horizontal step flow: [Step, →, Step, →, Step ...]"""
    cells = []
    styles_ = []
    for i, (num, label, color) in enumerate(steps):
        cells.append(Paragraph(f"<b>{num}</b><br/>{label}", LABEL))
        idx = len(cells) - 1
        styles_.append(("BACKGROUND", (idx,0), (idx,0), color))
        if i < len(steps) - 1:
            cells.append(Paragraph("<b>→</b>", style("ARR","Normal",
                fontSize=12, textColor=NAVY, fontName="Helvetica-Bold")))

    w = 6.5 / len(cells)
    t = Table([cells], colWidths=[w*inch]*len(cells))
    t.setStyle(TableStyle([
        ("ALIGN",   (0,0), (-1,-1), "CENTER"),
        ("VALIGN",  (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",   (0,0), (-1,-1), 6),
        ("BOTTOMPADDING",(0,0), (-1,-1), 6),
        ("LEFTPADDING",  (0,0), (-1,-1), 3),
        ("RIGHTPADDING", (0,0), (-1,-1), 3),
        *styles_,
    ]))
    return t

def outcome_box(outcome_text, color=GREEN):
    """Green/red outcome callout."""
    t = Table([[Paragraph(f"<b>Exit Outcome:</b> {outcome_text}", SMALL)]],
              colWidths=[6.5*inch])
    t.setStyle(TableStyle([
        ("BACKGROUND",  (0,0), (-1,-1), colors.HexColor("#EAF7EE") if color==GREEN else colors.HexColor("#FDEDEC")),
        ("LEFTBORDERPADDING", (0,0), (-1,-1), 0),
        ("LINEBEFOREBOLD", (0,0), (0,-1), 3, color),
        ("LEFTPADDING",   (0,0), (-1,-1), 10),
        ("TOPPADDING",    (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ("BOX", (0,0), (-1,-1), 0.5, color),
    ]))
    return t

def spacer(h=0.15): return Spacer(1, h*inch)

# ── Document ──────────────────────────────────────────────────────────────────

def build():
    doc = SimpleDocTemplate(
        OUTPUT,
        pagesize=letter,
        leftMargin=0.9*inch, rightMargin=0.9*inch,
        topMargin=0.85*inch, bottomMargin=0.85*inch,
        title="Arikina B2B Stablecoin Escrow — Use Case Reference",
        author="Chris Mahadeo | Arikina",
    )

    story = []

    # ── Cover / Title ─────────────────────────────────────────────────────────
    story.append(spacer(0.1))
    story.append(Paragraph("Arikina B2B Stablecoin Escrow", H1))
    story.append(Paragraph("Use Case Reference — Stellar Testnet", TAGLINE))
    story.append(HRFlowable(width="100%", thickness=2, color=GOLD, spaceAfter=8))
    story.append(Paragraph(
        "This document describes the five escrow scenarios built on the Stellar testnet "
        "as part of Arikina's B2B ingredient payment infrastructure. Each scenario maps "
        "to a real trade finance use case — from clean delivery to disputed shipments — "
        "and demonstrates how programmable escrow can replace traditional letters of credit "
        "and wire-based payment terms at a fraction of the cost.",
        BODY
    ))
    story.append(spacer(0.12))

    # ── Architecture Overview ─────────────────────────────────────────────────
    story.append(Paragraph("Architecture Overview", H3))
    story.append(kv_table([
        ("Network",        "Stellar Testnet (Horizon API)"),
        ("Escrow model",   "Per-PO account with 2-of-2 multisig (Buyer + Oracle)"),
        ("Signers",        "Buyer (weight 1) · Oracle (weight 1)"),
        ("Low threshold",  "1 — Oracle alone can write data entries (shipment confirmation, verdict)"),
        ("Med threshold",  "2 — Buyer + Oracle must co-sign all payment operations"),
        ("High threshold", "2 — Buyer + Oracle must co-sign account option changes"),
        ("On-chain data",  "PO number · ingredient · state · deadline · tracking ID · dispute metadata"),
        ("Settlement",     "~3–5 seconds · $0.017 fee per transaction vs $96 traditional wire"),
        ("CLI",            "python -X utf8 escrow.py [happy|deadline|cancel|quality|nondelivery]"),
    ]))
    story.append(spacer(0.18))

    # ═══════════════════════════════════════════════════════════════════════════
    # SCENARIO 1 — HAPPY PATH
    # ═══════════════════════════════════════════════════════════════════════════
    story.append(KeepTogether([
        section_header("Scenario 1 — Full Delivery (Happy Path)",
                       "python -X utf8 escrow.py happy", color=TEAL),
        spacer(0.08),
        Paragraph("Business Context", H3),
        Paragraph(
            "Standard PO fulfillment. Buyer locks payment in escrow before shipment. "
            "Supplier ships goods, oracle records tracking ID on-chain. On confirmed "
            "delivery, buyer and oracle co-sign release — supplier receives full payment "
            "in seconds, not days.",
            BODY
        ),
    ]))

    story.append(flow_table([
        ("1", "Create\nEscrow", TEAL),
        ("2", "Fund\nEscrow", TEAL),
        ("3", "Confirm\nShipment", TEAL),
        ("4", "Confirm\nDelivery", TEAL),
        ("✓", "Supplier\nPaid", GREEN),
    ]))
    story.append(spacer(0.1))
    story.append(kv_table([
        ("Entry point",  "Buyer has funded wallet. Supplier agrees to PO terms."),
        ("Step 1",       "Buyer calls create_escrow() — new Stellar account created, 2-of-2 multisig set, "
                         "PO number + ingredient + delivery deadline written on-chain."),
        ("Step 2",       "Buyer calls fund_escrow() — deposits 1,700 XLM (~$1,700). Supplier can verify "
                         "payment is locked at escrow address before preparing shipment."),
        ("Step 3",       "confirm_shipment(tracking_id) — oracle writes tracking ID + shipped_at timestamp. "
                         "Buyer co-signs (med threshold = 2). Data is immutable."),
        ("Step 4",       "confirm_delivery() — buyer + oracle co-sign. Full spendable balance sent to "
                         "supplier atomically. Settlement completes in ~3s."),
        ("Exit outcome", "State = RELEASED. Supplier balance increases by payment amount. "
                         "Escrow holds only minimum reserve (~5 XLM)."),
        ("Wire equiv.",  "$96 fee (wire) → $0.017 (Stellar). 3–5 days → 3 seconds."),
    ]))
    story.append(spacer(0.05))
    story.append(outcome_box("State → RELEASED | Supplier receives 100% of PO amount | ~3s settlement", GREEN))
    story.append(spacer(0.2))

    # ═══════════════════════════════════════════════════════════════════════════
    # SCENARIO 2 — DEADLINE EXPIRY
    # ═══════════════════════════════════════════════════════════════════════════
    story.append(KeepTogether([
        section_header("Scenario 2 — Delivery Deadline Expired",
                       "python -X utf8 escrow.py deadline", color=colors.HexColor("#1A5276")),
        spacer(0.08),
        Paragraph("Business Context", H3),
        Paragraph(
            "Supplier takes payment (escrow funded) but fails to deliver within the agreed "
            "window — either ghosting on the order or experiencing a fulfillment failure. "
            "The delivery deadline is written on-chain at escrow creation. When it passes, "
            "the oracle — a programmatic service monitoring the ledger — automatically "
            "co-signs a full refund. No human arbitration required.",
            BODY
        ),
    ]))

    story.append(flow_table([
        ("1", "Create\nEscrow", TEAL),
        ("2", "Fund\nEscrow", TEAL),
        ("—", "No\nShipment", colors.HexColor("#777")),
        ("⏱", "Deadline\nExpires", ORANGE),
        ("↩", "Auto\nRefund", RED),
    ]))
    story.append(spacer(0.1))
    story.append(kv_table([
        ("Entry point",    "State = FUNDED. funded_at + DELIVERY_WINDOW_SECS has passed with no confirm_delivery."),
        ("Trigger",        "Oracle daemon polls Horizon each block, reads deadline data entry, "
                           "compares to current ledger close time. When expired, oracle auto-signs refund."),
        ("Condition",      "time.time() − funded_at > DELIVERY_WINDOW_SECS "
                           "(demo: 30 seconds / production: 30 days)"),
        ("On-chain record","state=REFUNDED · refund_reason=DEADLINE_EXPIRED · refunded_at=<timestamp>"),
        ("Signatures",     "Buyer + Oracle (oracle programmatically obligated to sign on deadline breach — "
                           "this is the 'smart contract' equivalent of a time-lock clause)"),
        ("Guard",          "Refund is blocked if deliver_deadline has not yet passed. "
                           "Script waits and notifies remaining time."),
        ("Exit outcome",   "State = REFUNDED. Full balance returned to buyer. Supplier has no claim."),
    ]))
    story.append(spacer(0.05))
    story.append(outcome_box("State → REFUNDED | Buyer receives 100% refund | Deadline breach recorded on-chain", RED))
    story.append(spacer(0.2))

    # ═══════════════════════════════════════════════════════════════════════════
    # SCENARIO 3 — PRE-SHIPMENT CANCELLATION
    # ═══════════════════════════════════════════════════════════════════════════
    story.append(KeepTogether([
        section_header("Scenario 3 — Pre-Shipment Cancellation",
                       "python -X utf8 escrow.py cancel", color=colors.HexColor("#6E2F7C")),
        spacer(0.08),
        Paragraph("Business Context", H3),
        Paragraph(
            "Either party mutually agrees to cancel the PO before goods are dispatched. "
            "Common in ingredient sourcing when crop yields change, quality certifications "
            "are not met, or buyer specifications are revised post-order. The smart "
            "contract enforces a hard guard: if a tracking ID is already on-chain, "
            "cancellation is rejected — the dispute path must be used instead.",
            BODY
        ),
    ]))

    story.append(flow_table([
        ("1", "Create\nEscrow", TEAL),
        ("2", "Fund\nEscrow", TEAL),
        ("✗", "No\nTracking ID", colors.HexColor("#777")),
        ("↩", "Cancel\n+ Refund", colors.HexColor("#6E2F7C")),
    ]))
    story.append(spacer(0.1))
    story.append(kv_table([
        ("Entry point",  "State = FUNDED. No tracking ID recorded. Both parties agree to cancel."),
        ("Hard guard",   "Raises ValueError if ctx.tracking_id is set (goods already in transit). "
                         "This is enforced in code — not just a business rule."),
        ("On-chain record", "state=CANCELLED · cancelled_at=<timestamp>"),
        ("Signatures",   "Buyer + Oracle (mutual consent — oracle confirms no shipment was recorded)"),
        ("Distinction",  "Cancel vs Refund: Cancel = pre-shipment mutual agreement (clean). "
                         "Refund = deadline breach (supplier fault). Both end with buyer recovery "
                         "but carry different on-chain reason codes for audit/insurance."),
        ("Exit outcome", "State = CANCELLED. Full balance returned to buyer immediately. "
                         "No penalty, no dispute, no waiting."),
    ]))
    story.append(spacer(0.05))
    story.append(outcome_box("State → CANCELLED | Buyer receives 100% refund | Mutual consent, no penalty", colors.HexColor("#6E2F7C")))
    story.append(spacer(0.2))

    # ═══════════════════════════════════════════════════════════════════════════
    # SCENARIO 4 — QUALITY DISPUTE (PARTIAL SETTLEMENT)
    # ═══════════════════════════════════════════════════════════════════════════
    story.append(KeepTogether([
        section_header("Scenario 4 — Quality Dispute (Partial Settlement)",
                       "python -X utf8 escrow.py quality", color=ORANGE),
        spacer(0.08),
        Paragraph("Business Context", H3),
        Paragraph(
            "Goods arrive but fail to meet specification — wrong grade, short weight, "
            "contamination, or improper certification. The buyer raises a dispute with "
            "documented evidence. The oracle (acting as trade finance arbitrator) reviews "
            "the claim and rules on a split: the fraction of the PO that was legitimately "
            "fulfilled goes to the supplier; the remainder is refunded to the buyer. "
            "Both transfers happen atomically in a single Stellar transaction — something "
            "no wire transfer system can do.",
            BODY
        ),
    ]))

    story.append(flow_table([
        ("1", "Create\nEscrow", TEAL),
        ("2", "Fund\nEscrow", TEAL),
        ("3", "Confirm\nShipment", TEAL),
        ("4", "Buyer\nDisputes", ORANGE),
        ("⚖", "Oracle\nRules", ORANGE),
        ("↔", "Atomic\nSplit", GREEN),
    ]))
    story.append(spacer(0.1))
    story.append(kv_table([
        ("Entry point",   "State = SHIPPED. Buyer calls dispute_quality(reason, supplier_pct)."),
        ("supplier_pct",  "Fraction of escrow to release to supplier (0.0–1.0). "
                          "Example: 0.70 → supplier gets 70%, buyer gets 30% back."),
        ("Phase 1",       "Oracle writes dispute_reason + supplier_pct + state=DISPUTED on-chain "
                          "(low threshold = 1, oracle alone can write data). Buyer co-signs."),
        ("Phase 2",       "Oracle + buyer co-sign atomic settlement transaction containing "
                          "two payment ops: supplier_amount + buyer_amount. Both execute or neither does."),
        ("Example",       "PO: 200kg Shea Butter at $1,700. Delivered: 140kg (30% short). "
                          "Oracle rules 70/30. Supplier receives $1,190. Buyer receives $510."),
        ("On-chain record","state=DISPUTE_RESOLVED · dispute_reason · supplier_pct · resolved_at"),
        ("Key insight",   "Atomic split settlement is impossible with wire transfers. "
                          "Stellar executes both transfers in one ledger close (~3s)."),
        ("Exit outcome",  "State = DISPUTE_RESOLVED. Funds split per ruling. Both parties settle simultaneously."),
    ]))
    story.append(spacer(0.05))
    story.append(outcome_box(
        "State → DISPUTE_RESOLVED | Supplier receives 70% | Buyer receives 30% | Atomic split in ~5s",
        ORANGE
    ))
    story.append(spacer(0.2))

    # ═══════════════════════════════════════════════════════════════════════════
    # SCENARIO 5 — NON-DELIVERY DISPUTE
    # ═══════════════════════════════════════════════════════════════════════════
    story.append(KeepTogether([
        section_header("Scenario 5 — Non-Delivery Dispute (Oracle Verdict)",
                       "python -X utf8 escrow.py nondelivery", color=RED),
        spacer(0.08),
        Paragraph("Business Context", H3),
        Paragraph(
            "Carrier tracking shows the shipment as delivered, but the buyer claims the "
            "goods were never received — a common scenario involving porch theft, wrong "
            "delivery address, or fraudulent tracking updates. The oracle investigates "
            "(carrier GPS data, proof of delivery photos, signed receipt) and issues a "
            "binding verdict. The verdict is written on-chain before settlement, creating "
            "an immutable audit trail usable for insurance claims or legal proceedings.",
            BODY
        ),
    ]))

    story.append(flow_table([
        ("1", "Create\nEscrow", TEAL),
        ("2", "Fund\nEscrow", TEAL),
        ("3", "Ship +\nTrack", TEAL),
        ("4", "Buyer\nDisputes", RED),
        ("⚖", "Oracle\nVerdict", RED),
        ("✓/↩", "Release or\nRefund", GREEN),
    ]))
    story.append(spacer(0.1))
    story.append(kv_table([
        ("Entry point",    "State = SHIPPED. Carrier shows delivered. Buyer calls dispute_nondelivery(verdict)."),
        ("oracle_verdict", "BUYER_WINS → full refund to buyer (carrier/supplier liable)\n"
                           "SUPPLIER_WINS → full release to supplier (buyer claim rejected)"),
        ("Phase 1",        "Oracle writes oracle_verdict + dispute_reason=NON_DELIVERY + state=DISPUTED "
                           "on-chain. Low threshold (1) — oracle can do this unilaterally. Buyer co-signs."),
        ("Phase 2",        "Oracle + buyer co-sign payment to the verdict-winning party. "
                           "Verdict is immutably recorded before funds move."),
        ("Audit trail",    "Verdict tx hash provides court-admissible timestamp of oracle ruling. "
                           "All evidence reasoning can be appended as additional ManageData entries."),
        ("Oracle role",    "Mirrors a letter of credit issuing bank — independent arbitrator who "
                           "holds no funds but controls their release. Fully automated, on-chain."),
        ("Exit outcome",   "State = REFUNDED (buyer wins) or RELEASED (supplier wins). "
                           "Full amount sent to ruling party."),
    ]))
    story.append(spacer(0.05))
    story.append(outcome_box(
        "State → REFUNDED or RELEASED | Oracle verdict immutably recorded | Full settlement in ~4s",
        RED
    ))
    story.append(spacer(0.2))

    # ═══════════════════════════════════════════════════════════════════════════
    # COMPARISON TABLE
    # ═══════════════════════════════════════════════════════════════════════════
    story.append(Paragraph("Scenario Comparison", H3))
    headers = ["Scenario", "Entry State", "Exit State", "Signers", "Settlement"]
    rows = [
        ["1 · Happy Path",         "FUNDED → SHIPPED",    "RELEASED",         "Buyer + Oracle", "~3s · $0.017"],
        ["2 · Deadline Expiry",    "FUNDED (no delivery)","REFUNDED",         "Buyer + Oracle\n(oracle auto)", "~3s after deadline"],
        ["3 · Cancel",             "FUNDED (no tracking)","CANCELLED",        "Buyer + Oracle", "~3s"],
        ["4 · Quality Dispute",    "SHIPPED",             "DISPUTE_RESOLVED", "Buyer + Oracle", "~5s · atomic split"],
        ["5 · Non-Delivery",       "SHIPPED",             "REFUNDED/RELEASED","Buyer + Oracle\n(oracle verdict)", "~4s"],
    ]

    col_w = [1.6*inch, 1.4*inch, 1.3*inch, 1.35*inch, 1.35*inch]
    tdata = [[Paragraph(h, style("TH","Normal", fontSize=8.5, fontName="Helvetica-Bold",
                                  textColor=WHITE)) for h in headers]]
    for row in rows:
        tdata.append([Paragraph(cell, SMALL) for cell in row])

    t = Table(tdata, colWidths=col_w, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,0), NAVY),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[WHITE, LIGHT]),
        ("LINEBELOW",    (0,0), (-1,-1), 0.3, colors.HexColor("#DDD")),
        ("TOPPADDING",   (0,0), (-1,-1), 5),
        ("BOTTOMPADDING",(0,0), (-1,-1), 5),
        ("LEFTPADDING",  (0,0), (-1,-1), 6),
        ("RIGHTPADDING", (0,0), (-1,-1), 6),
        ("FONTSIZE",     (0,0), (-1,-1), 8.5),
        ("VALIGN",       (0,0), (-1,-1), "TOP"),
        ("BOX",          (0,0), (-1,-1), 0.5, colors.HexColor("#BBB")),
    ]))
    story.append(t)
    story.append(spacer(0.2))

    # ═══════════════════════════════════════════════════════════════════════════
    # PAYMENT ECONOMICS
    # ═══════════════════════════════════════════════════════════════════════════
    story.append(Paragraph("Payment Economics — $1,700 PO Example", H3))
    econ_data = [
        [Paragraph(h, style("TH2","Normal",fontSize=8.5,fontName="Helvetica-Bold",textColor=WHITE))
         for h in ["Method", "Fixed Fee", "FX / Variable", "Total Cost", "Settlement Time"]],
        [Paragraph(c, SMALL) for c in ["Traditional Wire", "$45.00", "3.0% ($51.00)", "$96.00", "3–5 business days"]],
        [Paragraph(c, SMALL) for c in ["Letter of Credit", "$150–$500", "0.5–2.5%", "$200–$1,000+", "5–10 days"]],
        [Paragraph(c, style("BOLD_SMALL","Normal",fontSize=8.5,fontName="Helvetica-Bold",textColor=TEAL))
         for c in ["Stellar Escrow", "$0.00001", "0.001%", "$0.017", "3–5 seconds"]],
    ]
    et = Table(econ_data, colWidths=[1.5*inch, 1.0*inch, 1.4*inch, 1.1*inch, 1.5*inch])
    et.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,0), NAVY),
        ("ROWBACKGROUNDS",(0,1),(-1,-2),[WHITE, LIGHT]),
        ("BACKGROUND",   (0,-1),(-1,-1), colors.HexColor("#E8F8F5")),
        ("LINEBELOW",    (0,0), (-1,-1), 0.3, colors.HexColor("#DDD")),
        ("TOPPADDING",   (0,0), (-1,-1), 5),
        ("BOTTOMPADDING",(0,0), (-1,-1), 5),
        ("LEFTPADDING",  (0,0), (-1,-1), 6),
        ("RIGHTPADDING", (0,0), (-1,-1), 6),
        ("FONTSIZE",     (0,0), (-1,-1), 8.5),
        ("BOX",          (0,0), (-1,-1), 0.5, colors.HexColor("#BBB")),
    ]))
    story.append(et)
    story.append(spacer(0.12))
    story.append(Paragraph(
        "<b>99.98% cost reduction</b> vs traditional wire. "
        "For Arikina's typical ingredient order volume (~$2M/year across 40+ POs), "
        "Stellar settlement eliminates ~$38,400/year in wire fees and FX markups.",
        BODY
    ))
    story.append(spacer(0.25))

    # ── Footer ────────────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=1, color=GOLD, spaceAfter=6))
    story.append(Paragraph(
        "Chris Mahadeo · chris@arikina.com · Arikina Ingredients &amp; Supply Co. · "
        "Stellar Testnet Demo — April 2026",
        CAPTION
    ))
    story.append(Paragraph(
        "Due to ongoing market volatility, pricing and availability remain subject to change without notice. "
        "XLM used as USD proxy on testnet. Production deployment would use Circle USDC on Stellar.",
        CAPTION
    ))

    doc.build(story)
    print(f"PDF written: {OUTPUT}")


if __name__ == "__main__":
    build()
