import streamlit as st
import pandas as pd
import sqlite3
import yfinance as yf

DB_PATH = "aksjeradar.db"
PAGE_SIZE = 10


# -------------------------
# Database
# -------------------------
def delete_ticker(ticker: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM stock_data WHERE ticker = ?", (ticker,))
    conn.commit()
    conn.close()
    load_stock_data.clear()


# -------------------------
# Data
# -------------------------
@st.cache_data(ttl=600)
def load_stock_data():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM stock_data", conn)
    conn.close()

    df = df[df["price"].notnull()].copy()

    df["targetPercent"] = ((df["target"] - df["price"]) / df["price"]) * 100

    df["TradingView"] = df["ticker"].apply(
        lambda t: f"https://www.tradingview.com/symbols/{t}/?timeframe=12M"
    )

    df = df.drop(
        columns=["pe", "debt_to_equity", "dividend_yield", "marketcap", "timestamp"],
        errors="ignore"
    )

    for col in [
        "price", "target", "targetLow", "targetHigh", "pb",
        "mom_1d", "mom_1m", "mom_3m", "mom_1y", "targetPercent"
    ]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").round(2)

    return df.reset_index(drop=True)


# -------------------------
# App setup
# -------------------------
st.set_page_config(page_title="Aksjeradar", layout="wide")
st.title("📊 Aksjeradar")

df = load_stock_data()

if "page" not in st.session_state:
    st.session_state.page = 1
if "selected_ticker" not in st.session_state:
    st.session_state.selected_ticker = None


# -------------------------
# Sortering (global)
# -------------------------
c1, c2 = st.columns([3, 1])

with c1:
    sort_by = st.selectbox(
        "Sorter etter",
        df.columns,
        index=df.columns.get_loc("targetPercent")
    )

with c2:
    ascending = st.toggle("Stigende", value=False)

df = df.sort_values(sort_by, ascending=ascending, na_position="last")


# -------------------------
# Paginering
# -------------------------
num_pages = max(1, (len(df) - 1) // PAGE_SIZE + 1)
start = (st.session_state.page - 1) * PAGE_SIZE
end = start + PAGE_SIZE
df_page = df.iloc[start:end]


# -------------------------
# Tabell (rad for rad)
# -------------------------
st.markdown("### Aksjer")

header = st.columns([2, 3, 1, 1, 1, 1, 1, 1])
header[0].markdown("**Ticker**")
header[1].markdown("**Navn**")
header[2].markdown("**Pris**")
header[3].markdown("**Target %**")
header[4].markdown("**1M %**")
header[5].markdown("**1Y %**")
header[6].markdown("**TV**")
header[7].markdown("**🗑️**")

for _, row in df_page.iterrows():
    cols = st.columns([2, 3, 1, 1, 1, 1, 1, 1])

    # Klikkbar ticker = detaljer
    if cols[0].button(row["ticker"], key=f"sel_{row['ticker']}"):
        st.session_state.selected_ticker = row["ticker"]

    cols[1].write(row.get("name", ""))
    cols[2].write(row["price"])
    cols[3].write(row["targetPercent"])
    cols[4].write(row.get("mom_1m"))
    cols[5].write(row.get("mom_1y"))

    cols[6].link_button("📈", row["TradingView"])

    if cols[7].button("🗑️", key=f"del_{row['ticker']}"):
        delete_ticker(row["ticker"])
        if st.session_state.selected_ticker == row["ticker"]:
            st.session_state.selected_ticker = None
        st.rerun()


# -------------------------
# Paginering-knapper
# -------------------------
p1, p2, p3 = st.columns([1, 2, 1])

with p1:
    if st.session_state.page > 1:
        if st.button("◀️ Forrige"):
            st.session_state.page -= 1
            st.rerun()

with p2:
    st.markdown(
        f"<div style='text-align:center;color:gray;'>Side {st.session_state.page} av {num_pages}</div>",
        unsafe_allow_html=True
    )

with p3:
    if st.session_state.page < num_pages:
        if st.button("Neste ▶️"):
            st.session_state.page += 1
            st.rerun()


# -------------------------
# Detaljer
# -------------------------
ticker = st.session_state.selected_ticker
if ticker:
    st.markdown("---")
    st.header(f"📈 {ticker}")

    try:
        tk = yf.Ticker(ticker)
        info = tk.info

        c1, c2 = st.columns([1, 1])

        with c1:
            st.subheader(info.get("longName", ticker))
            st.write(f"**Sektor:** {info.get('sector', '-')}")
            st.write(f"**Bransje:** {info.get('industry', '-')}")
            st.write(f"**Markedsverdi:** {info.get('marketCap', 0):,}")
            st.write(f"**P/E:** {info.get('trailingPE', '-')}")
            st.write(f"**P/B:** {info.get('priceToBook', '-')}")
            st.write(info.get("longBusinessSummary", ""))

        with c2:
            hist = tk.history(period="1y")
            if not hist.empty:
                st.line_chart(hist["Close"])

    except Exception as e:
        st.error(f"Kunne ikke hente data for {ticker}: {e}")
