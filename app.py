import streamlit as st
import sqlite3
import pandas as pd
import numpy as np

st.set_page_config(page_title="Aksjeradar Screener", layout="wide")
st.title("📊 Aksjeradar — Screener fra database")

# ---- Koble til database ----
conn = sqlite3.connect("aksjeradar.db")

# Hent siste timestamp
last_ts = pd.read_sql("SELECT MAX(timestamp) as ts FROM stock_data", conn)["ts"].iloc[0]
st.write(f"📅 Data hentet sist: {last_ts}")

df = pd.read_sql("""
SELECT * FROM stock_data
WHERE timestamp = (SELECT MAX(timestamp) FROM stock_data)
""", conn)

# ---- Scoring ----
st.sidebar.header("Scoring-innstillinger")
w_pe = st.sidebar.slider("Vekt: Lav P/E", 0.0, 1.0, 0.2)
w_pb = st.sidebar.slider("Vekt: Lav P/B", 0.0, 1.0, 0.2)
w_debt = st.sidebar.slider("Vekt: Lav Gjeld/Egenkapital", 0.0, 1.0, 0.2)
w_mom = st.sidebar.slider("Vekt: Momentum (1 år)", 0.0, 1.0, 0.2)
w_div = st.sidebar.slider("Vekt: Utbytte yield", 0.0, 1.0, 0.2)
top_n = st.sidebar.number_input("Vis topp N", 1, 50, 10)

weights = np.array([w_pe, w_pb, w_debt, w_mom, w_div])
if weights.sum() == 0:
    weights = np.array([0.2,0.2,0.2,0.2,0.2])
else:
    weights = weights / weights.sum()

def robust_rank_series(s, invert=False):
    s = pd.to_numeric(s, errors="coerce")
    med = np.nanmedian(s)
    s_filled = s.fillna(med)
    ranks = (s_filled.rank(method="average") - 1) / (len(s_filled) - 1) if len(s_filled) > 1 else s_filled*0
    return 1-ranks if invert else ranks

df["rank_PE"] = robust_rank_series(df["pe"], invert=True)
df["rank_PB"] = robust_rank_series(df["pb"], invert=True)
df["rank_Debt"] = robust_rank_series(df["debt_to_equity"], invert=True)
df["rank_Momentum"] = robust_rank_series(df["mom_1y"])
df["rank_Dividend"] = robust_rank_series(df["dividend_yield"])

df["score"] = (
    weights[0]*df["rank_PE"] +
    weights[1]*df["rank_PB"] +
    weights[2]*df["rank_Debt"] +
    weights[3]*df["rank_Momentum"] +
    weights[4]*df["rank_Dividend"]
)

df["Score_0_100"] = ((df["score"] - df["score"].min()) / (df["score"].max()-df["score"].min())*100).round(2)

# ---- Toppliste ----
df_sorted = df.sort_values("Score_0_100", ascending=False).reset_index(drop=True)

st.subheader("🏆 Toppliste")
st.dataframe(
    df_sorted[["ticker","name","price","pe","pb","mom_1y","mom_1m","mom_3m","target","Score_0_100"]].head(top_n),
    height=420
)

csv = df_sorted.to_csv(index=False)
st.download_button("⬇️ Last ned CSV", data=csv, file_name="aksjeradar_screen.csv", mime="text/csv")
