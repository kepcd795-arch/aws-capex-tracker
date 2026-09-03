import sqlite3
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="AWS CapEx & Utilization Tracker", layout="wide"
)
st.title("AWS CapEx & ROI Early Signal Tracker")
st.markdown(
    "Monitoring upstream hardware buildouts vs. downstream compute demand in real-time."
)

conn = sqlite3.connect("aws_metrics.db")
cursor = conn.cursor()

# Ensure tables exist so queries don't fail if DB is empty
cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS spot_prices (
        timestamp TEXT, instance_type TEXT, az TEXT, spot_price REAL
    )
"""
)
cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS odm_revenue (
        date TEXT, ticker TEXT, company_name TEXT, revenue_ntd_thousands INTEGER,
        PRIMARY KEY(date, ticker)
    )
"""
)
conn.commit()

col1, col2 = st.columns(2)

with col1:
    st.subheader("1. Upstream Buildout: Taiwan Server ODM Sales")
    st.caption(
        "Monthly revenue from Foxconn, Wiwynn, and Quanta (leading indicator for cloud CapEx)."
    )

    odm_df = pd.read_sql_query(
        "SELECT * FROM odm_revenue ORDER BY date ASC", conn
    )
    if not odm_df.empty:
        fig_odm = px.bar(
            odm_df,
            x="date",
            y="revenue_ntd_thousands",
            color="company_name",
            title="Monthly ODM Revenue (NTD $1,000s)",
            barmode="group",
        )
        st.plotly_chart(fig_odm, use_container_width=True)
    else:
        st.info("No ODM revenue data found yet.")

with col2:
    st.subheader("2. Demand & ROI: AWS EC2 Spot Pricing")
    st.caption(
        "Dynamic spot prices indicate utilization. Price surges indicate high demand relative to capacity."
    )

    spot_df = pd.read_sql_query(
        "SELECT * FROM spot_prices ORDER BY timestamp ASC", conn
    )
    if not spot_df.empty:
        spot_df["timestamp"] = pd.to_datetime(spot_df["timestamp"])
        fig_spot = px.line(
            spot_df,
            x="timestamp",
            y="spot_price",
            color="instance_type",
            title="EC2 Spot Price Fluctuations (us-east-1)",
        )
        st.plotly_chart(fig_spot, use_container_width=True)
    else:
        st.info("No spot price data found yet.")

conn.close()
