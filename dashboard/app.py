"""
Stablecoin Supply Chain Payment Dashboard
Example: Personal Care Brand — Ingredient Sourcing

NOTE: All data in this dashboard is illustrative/example only.
Replace the mock data section with live Circle API + on-chain queries.

Run: streamlit run dashboard/app.py
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import random

st.set_page_config(
    page_title="Arikina — Supplier Payment Dashboard",
    page_icon="🌿",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Mock data — replace with live Circle API + on-chain queries in production
# ---------------------------------------------------------------------------

SUPPLIERS = [
    {"name": "Nkemdirim Naturals Cooperative", "country": "Ghana", "ingredient": "Raw Shea Butter", "category": "Lipid"},
    {"name": "Atlas Botanicals SARL",          "country": "Morocco", "ingredient": "Argan Oil (Organic)", "category": "Lipid"},
    {"name": "Givaudan India Ltd",             "country": "India", "ingredient": "Jasmine Absolute", "category": "Fragrance"},
    {"name": "Amazônia Extracts",              "country": "Brazil", "ingredient": "Cupuaçu Butter", "category": "Lipid"},
    {"name": "Alpine Actives GmbH",            "country": "Switzerland", "ingredient": "Hyaluronic Acid", "category": "Active"},
    {"name": "East Africa Botanicals",         "country": "Kenya", "ingredient": "Baobab Oil", "category": "Botanical"},
]

def generate_po_data():
    rows = []
    statuses = ["Released", "Released", "Released", "In Transit", "Escrowed", "Disputed"]
    for i, s in enumerate(SUPPLIERS):
        qty = random.choice([50, 100, 150, 200, 300])
        price = random.uniform(8, 200)
        total = round(qty * price, 2)
        wire_cost = round(45 + total * 0.03, 2)
        stablecoin_cost = round(total * 0.0001, 4)
        rows.append({
            "PO Number":   f"PO-2026{i+1:04d}",
            "Supplier":    s["name"],
            "Country":     s["country"],
            "Ingredient":  s["ingredient"],
            "Category":    s["category"],
            "Qty (kg)":    qty,
            "Unit Price":  round(price, 2),
            "Total USDC":  total,
            "Wire Cost":   wire_cost,
            "Stable Cost": stablecoin_cost,
            "Savings":     round(wire_cost - stablecoin_cost, 2),
            "Status":      statuses[i],
            "Date":        datetime.now() - timedelta(days=random.randint(1, 60)),
        })
    return pd.DataFrame(rows)

df = generate_po_data()

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.title("🌿 Stablecoin Supplier Payments")
st.caption("B2B ingredient sourcing payment tracker | Powered by USDC on Stellar | Example data only")

# ---------------------------------------------------------------------------
# KPI Row
# ---------------------------------------------------------------------------

col1, col2, col3, col4, col5 = st.columns(5)

total_volume = df["Total USDC"].sum()
total_savings = df["Savings"].sum()
released = df[df["Status"] == "Released"]
in_transit = df[df["Status"] == "In Transit"]
active_suppliers = df["Supplier"].nunique()

col1.metric("Total USDC Volume", f"${total_volume:,.0f}")
col2.metric("Total Savings vs Wire", f"${total_savings:,.2f}", "+savings")
col3.metric("Payments Released", len(released))
col4.metric("In Transit", len(in_transit))
col5.metric("Active Suppliers", active_suppliers)

st.divider()

# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------

chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    st.subheader("Payment Volume by Supplier Country")
    country_vol = df.groupby("Country")["Total USDC"].sum().reset_index()
    fig = px.bar(country_vol, x="Country", y="Total USDC", color="Country",
                 labels={"Total USDC": "USDC Volume"},
                 color_discrete_sequence=px.colors.qualitative.Set2)
    fig.update_layout(showlegend=False, height=300)
    st.plotly_chart(fig, use_container_width=True)

with chart_col2:
    st.subheader("Wire Cost vs Stablecoin Cost")
    cost_df = pd.DataFrame({
        "Method": ["Traditional Wire"] * len(df) + ["Stablecoin (USDC)"] * len(df),
        "Cost ($)": list(df["Wire Cost"]) + list(df["Stable Cost"]),
        "PO": list(df["PO Number"]) * 2,
    })
    fig2 = px.bar(cost_df, x="PO", y="Cost ($)", color="Method", barmode="group",
                  color_discrete_map={"Traditional Wire": "#ef4444", "Stablecoin (USDC)": "#22c55e"})
    fig2.update_layout(height=300)
    st.plotly_chart(fig2, use_container_width=True)

# ---------------------------------------------------------------------------
# Payment Status Flow
# ---------------------------------------------------------------------------

st.subheader("Payment Status Distribution")

status_counts = df["Status"].value_counts().reset_index()
status_counts.columns = ["Status", "Count"]
status_colors = {
    "Released": "#22c55e",
    "In Transit": "#3b82f6",
    "Escrowed": "#f59e0b",
    "Disputed": "#ef4444",
}
fig3 = px.pie(status_counts, names="Status", values="Count",
              color="Status",
              color_discrete_map=status_colors)
fig3.update_layout(height=280)
st.plotly_chart(fig3, use_container_width=True)

# ---------------------------------------------------------------------------
# PO Table
# ---------------------------------------------------------------------------

st.subheader("Purchase Orders")

status_filter = st.multiselect(
    "Filter by status",
    options=df["Status"].unique().tolist(),
    default=df["Status"].unique().tolist(),
)
filtered = df[df["Status"].isin(status_filter)]

def color_status(val):
    colors = {
        "Released": "background-color: #dcfce7; color: #166534",
        "In Transit": "background-color: #dbeafe; color: #1e40af",
        "Escrowed": "background-color: #fef3c7; color: #92400e",
        "Disputed": "background-color: #fee2e2; color: #991b1b",
    }
    return colors.get(val, "")

display_cols = ["PO Number", "Supplier", "Country", "Ingredient", "Qty (kg)", "Total USDC", "Savings", "Status"]
st.dataframe(
    filtered[display_cols].style.applymap(color_status, subset=["Status"]),
    use_container_width=True,
    hide_index=True,
)

# ---------------------------------------------------------------------------
# Savings Calculator
# ---------------------------------------------------------------------------

st.divider()
st.subheader("Savings Calculator")
st.caption("Estimate your annual wire savings by switching to stablecoin payments")

calc_col1, calc_col2 = st.columns(2)
with calc_col1:
    monthly_pos = st.slider("Monthly purchase orders", 1, 50, 8)
    avg_po_value = st.slider("Average PO value (USD)", 1000, 100000, 12000, step=500)

with calc_col2:
    annual_volume = monthly_pos * avg_po_value * 12
    annual_wire_cost = (monthly_pos * 45 + annual_volume * 0.03) * 12 / 12 * 12
    annual_stable_cost = annual_volume * 0.0001
    annual_savings = annual_wire_cost - annual_stable_cost

    st.metric("Annual Payment Volume", f"${annual_volume:,.0f}")
    st.metric("Annual Wire Cost (est.)", f"${annual_wire_cost:,.0f}")
    st.metric("Annual Stablecoin Cost (est.)", f"${annual_stable_cost:,.2f}")
    st.metric("Annual Savings", f"${annual_savings:,.0f}", delta=f"${annual_savings/12:,.0f}/mo")
