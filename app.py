import streamlit as st
import pandas as pd
import sqlite3
import yfinance as yf
import base64

# Les logo og konverter til base64
with open("logo.png", "rb") as f:
    logo_b64 = base64.b64encode(f.read()).decode("utf-8")

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
    df = df.drop(columns=["pe", "debt_to_equity", "dividend_yield", "marketcap", "timestamp"], errors="ignore")

    # Sorter etter targetPercent
    df = df.sort_values(by="targetPercent", ascending=False)

    # Avrund tall
    for col in ["price", "target", "targetLow", "targetHigh", "pb", "mom_1d", "mom_1m", "mom_3m", "mom_1y", "targetPercent"]:
        if col in df.columns:
            df[col] = df[col].round(2)

    return df


# --- App setup ---
st.set_page_config(page_title="Aksjeradar", layout="wide")

# Bruk inline base64-bilde i tittelen
st.markdown(
    f"""
    <div style="display:flex; align-items:center; gap:10px;">
        <img src="data:image/png;base64,{logo_b64}" width="40">
        <h1 style="margin:0;">Aksjeradar</h1>
    </div>
    """,
    unsafe_allow_html=True,
)

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

#st.subheader(f"Toppliste — side {st.session_state.page}/{num_pages}")
st.caption("Klikk på en ticker for å vise detaljer nedenfor 👇")

# --- CSS styling ---
st.markdown("""
    <style>
    .stock-table th {
        /*background-color: #f5f5f5;*/
        padding: 6px;
        text-align: left;
        border: 0;
        width: 7%;
    }
    .stock-table th.name {
        width: 21%;
    }
    .stock-table td {
        padding: 6px;
    }
    .stock-row:hover {
        background-color: #f0f8ff;
    }
    </style>
""", unsafe_allow_html=True)

# --- Vis tabell ---
st.markdown("<table class='stock-table' width='100%'><thead><tr>"
            "<th>Ticker</th><th class='name'>Navn</th><th>Pris</th><th>Target</th>"
            "<th>Low</th><th>High</th><th>P/B</th><th>1D</th><th>1M</th>"
            "<th>3M</th><th>1Y</th><th>Target %</th>"
            "</tr></thead><tbody>", unsafe_allow_html=True)

for _, row in df_page.iterrows():
    color = "green" if row["targetPercent"] > 0 else "red" if row["targetPercent"] < 0 else "black"
    cols = st.columns([1, 3, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1])

    # Første kolonne = knapp
    with cols[0]:
        if st.button(row["ticker"], key=f"ticker_{row['ticker']}"):
            st.session_state.selected_ticker = row["ticker"]

    # De andre kolonnene = tekst
    cols[1].write(row.get("name", ""))
    cols[2].write(row["price"])
    cols[3].write(row["target"])
    cols[4].write(row["targetLow"])
    cols[5].write(row["targetHigh"])
    cols[6].write(row["pb"])
    cols[7].write(f"{row['mom_1d']:+.2f}%")
    cols[8].write(f"{row['mom_1m']:+.2f}%")
    cols[9].write(f"{row['mom_3m']:+.2f}%")
    cols[10].write(f"{row['mom_1y']:+.2f}%")
    cols[11].markdown(f"<span style='color:{color}; font-weight:bold'>{row['targetPercent']:+.2f}%</span>", unsafe_allow_html=True)

st.markdown("</tbody></table>", unsafe_allow_html=True)

# --- Paginering ---
col_prev, col_mid, col_next = st.columns([1, 2, 1])
with col_prev:
    if st.session_state.page > 1:
        if st.button("◀️ Forrige", key="forrige"):
            st.session_state.page -= 1
            st.session_state.selected_ticker = None
            st.rerun()
with col_mid:
    st.markdown(f"<div style='text-align:center; color:gray;'>Side {st.session_state.page} av {num_pages}</div>", unsafe_allow_html=True)
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
            st.write(f"**Børs:** {info.get('fullExchangeName', '-')}")
            st.write(f"**Summary:** {info.get('longBusinessSummary', '-')}")

        with col2:
            st.write("### Kurs siste år")
            hist = tk.history(period="1y")
            if not hist.empty:
                st.line_chart(hist["Close"])
            else:
                st.info("Ingen historiske data tilgjengelig.")
    except Exception as e:
        st.error(f"Kunne ikke hente data for {ticker}: {e}")
