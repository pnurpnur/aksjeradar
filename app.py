import streamlit as st
import pandas as pd
import sqlite3
import yfinance as yf

DB_PATH = "aksjeradar.db"

# --- Hent data fra databasen ---
@st.cache_data(ttl=600)
def load_stock_data():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM stock_data", conn)
    conn.close()

    # Fjern rader uten pris
    df = df[df["price"].notnull()]

    # Beregn targetPercent
    df["targetPercent"] = ((df["target"] - df["price"]) / df["price"]) * 100

    # Fjern uønskede kolonner
    cols_to_exclude = ["pe", "debt_to_equity", "dividend_yield", "marketcap", "timestamp"]
    df = df.drop(columns=cols_to_exclude, errors="ignore")

    # Sorter etter targetPercent
    df = df.sort_values(by="targetPercent", ascending=False)

    # Avrund for visning
    num_cols = ["price", "target", "targetLow", "targetHigh", "mom_1d", "mom_1m", "mom_3m", "mom_1y", "pb", "targetPercent"]
    for c in num_cols:
        if c in df.columns:
            df[c] = df[c].round(2)

    return df


# --- App setup ---
st.set_page_config(page_title="Aksjeradar", layout="wide")
st.title("📊 Aksjeradar — Beste kjøpskandidater")

df = load_stock_data()

# --- State og paginering ---
if "page" not in st.session_state:
    st.session_state.page = 1
if "selected_ticker" not in st.session_state:
    st.session_state.selected_ticker = None

page_size = 10
num_pages = (len(df) - 1) // page_size + 1

start = (st.session_state.page - 1) * page_size
end = start + page_size
df_page = df.iloc[start:end].reset_index(drop=True)

st.subheader(f"Toppliste — side {st.session_state.page}/{num_pages}")
st.caption("Klikk på en ticker for å vise detaljer nedenfor 👇")

# --- Bygg tabell med klikkbare tickere ---
rows = []
for i, row in df_page.iterrows():
    # Farge på targetPercent
    color = "green" if row["targetPercent"] > 0 else "red" if row["targetPercent"] < 0 else "black"
    target_html = f"<span style='color:{color};font-weight:bold'>{row['targetPercent']:+.2f}%</span>"

    # Knapp for å åpne detaljer
    col_button = st.button(row["ticker"], key=f"btn_{row['ticker']}")
    if col_button:
        st.session_state.selected_ticker = row["ticker"]

    # Legg resten av rad-data
    rows.append({
        " ": f"<b>{row['ticker']}</b>",
        "Navn": row.get("name", ""),
        "Pris": f"{row.get('price', 0):.2f}",
        "Target": f"{row.get('target', 0):.2f}",
        "Low": f"{row.get('targetLow', 0):.2f}",
        "High": f"{row.get('targetHigh', 0):.2f}",
        "P/B": f"{row.get('pb', 0):.2f}",
        "1D": f"{row.get('mom_1d', 0):+.2f}%",
        "1M": f"{row.get('mom_1m', 0):+.2f}%",
        "3M": f"{row.get('mom_3m', 0):+.2f}%",
        "1Y": f"{row.get('mom_1y', 0):+.2f}%",
        "Target %": target_html,
    })

# --- Bygg DataFrame for visning ---
df_display = pd.DataFrame(rows)

# --- CSS for finere tabell ---
st.markdown("""
    <style>
    table {
        border-collapse: collapse;
        width: 100%;
    }
    th {
        background-color: #F5F5F5;
        padding: 8px;
        text-align: left;
    }
    td {
        padding: 6px 8px;
    }
    tr:nth-child(even) {
        background-color: #FAFAFA;
    }
    tr:hover {
        background-color: #F0F8FF;
    }
    </style>
""", unsafe_allow_html=True)

# --- Vis tabell ---
st.markdown(df_display.to_html(escape=False, index=False), unsafe_allow_html=True)

# --- Paginering ---
col_prev, col_mid, col_next = st.columns([1, 2, 1])
with col_prev:
    if st.session_state.page > 1:
        if st.button("◀️ Forrige"):
            st.session_state.page -= 1
            st.session_state.selected_ticker = None
            st.rerun()
with col_mid:
    st.markdown(
        f"<div style='text-align:center; color:gray;'>Side {st.session_state.page} av {num_pages}</div>",
        unsafe_allow_html=True,
    )
with col_next:
    if st.session_state.page < num_pages:
        if st.button("Neste ▶️"):
            st.session_state.page += 1
            st.session_state.selected_ticker = None
            st.rerun()

# --- Detaljvisning ---
ticker = st.session_state.selected_ticker
if ticker:
    st.markdown("---")
    st.header(f"📈 Detaljer for {ticker}")

    try:
        tk = yf.Ticker(ticker)
        info = tk.info

        col1, col2 = st.columns([1, 1])
        with col1:
            st.markdown(f"### {info.get('longName', ticker)}")
            st.write(f"**Sektor:** {info.get('sector', '-')}")
            st.write(f"**Bransje:** {info.get('industry', '-')}")
            st.write(f"**Markedsverdi:** {info.get('marketCap', 0):,}")
            st.write(f"**P/E:** {info.get('trailingPE', '-')}")
            st.write(f"**P/B:** {info.get('priceToBook', '-')}")
            st.write(f"**Utbytteyield:** {(info.get('dividendYield') or 0)*100:.2f}%")
            st.write(f"**Beta:** {info.get('beta', '-')}")

        with col2:
            st.write("### Kurs siste år")
            hist = tk.history(period="1y")
            if not hist.empty:
                st.line_chart(hist["Close"])
            else:
                st.info("Ingen historiske data tilgjengelig.")
    except Exception as e:
        st.error(f"Kunne ikke hente data for {ticker}: {e}")
