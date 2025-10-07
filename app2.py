import streamlit as st
import sqlite3
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt

DB_PATH = "aksjeradar.db"

st.set_page_config(page_title="Aksjeradar", layout="wide")

# --- Hjelpefunksjoner ---
def get_data():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM stock_data", conn)
    conn.close()
    df = df[df["price"].notna()]
    df["targetPercent"] = ((df["target"] - df["price"]) / df["price"]) * 100
    df = df.sort_values("targetPercent", ascending=False)
    return df

def format_target(val):
    if pd.isna(val):
        return ""
    return f"{val:.1f}%"

# --- Hent data ---
df = get_data()

# Skjul uønskede kolonner
cols_to_hide = ["pe", "debt_to_equity", "dividend_yield", "marketcap", "timestamp"]
df_display = df.drop(columns=[c for c in cols_to_hide if c in df.columns])

# Formater targetPercent som tekst
df_display["targetPercent"] = df_display["targetPercent"].apply(format_target)

st.title("📊 Aksjeradar")
st.caption("Oppdag aksjer med størst oppside basert på målpris vs dagens kurs.")

# --- Vis tabell ---
st.write("### 📈 Oversikt")
st.markdown("Klikk på **Vis detaljer** for å se mer informasjon og kursgraf.")

# Bygg pent dataframe med knapp per rad
for i, row in df_display.iterrows():
    with st.container(border=True):
        cols = st.columns([2, 2, 2, 2, 2, 2])
        cols[0].markdown(f"**{row['ticker']}**")
        cols[1].write(row["name"])
        cols[2].write(f"{row['price']:.2f}")
        cols[3].write(f"{row['target']:.2f}" if row["target"] else "-")
        cols[4].markdown(f"**{row['targetPercent']}**")
        if cols[5].button("Vis detaljer", key=row["ticker"]):
            st.session_state["selected_ticker"] = row["ticker"]

# --- Hvis ticker valgt ---
if "selected_ticker" in st.session_state:
    ticker = st.session_state["selected_ticker"]
    st.divider()
    st.subheader(f"📊 Detaljer for {ticker}")

    try:
        tk = yf.Ticker(ticker)
        info = tk.info

        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Navn:** {info.get('shortName', 'N/A')}")
            st.write(f"**Sektor:** {info.get('sector', 'N/A')}")
            st.write(f"**Bransje:** {info.get('industry', 'N/A')}")
        with col2:
            st.write(f"**Markedsverdi:** {info.get('marketCap', 'N/A')}")
            st.write(f"**P/E:** {info.get('trailingPE', 'N/A')}")
            st.write(f"**P/B:** {info.get('priceToBook', 'N/A')}")

        # --- Hent og vis graf ---
        hist = tk.history(period="1y")
        if not hist.empty:
            fig, ax = plt.subplots()
            ax.plot(hist.index, hist["Close"], label="Pris", linewidth=2)
            ax.set_title(f"{ticker} – siste 12 måneder")
            ax.set_xlabel("Dato")
            ax.set_ylabel("Pris (USD)")
            ax.legend()
            st.pyplot(fig)
        else:
            st.info("Ingen historiske data tilgjengelig.")
    except Exception as e:
        st.error(f"Feil ved henting av {ticker}: {e}")
