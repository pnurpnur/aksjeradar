import streamlit as st
import pandas as pd
import sqlite3
import yfinance as yf
from st_aggrid import AgGrid, GridOptionsBuilder
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
    df = df.loc[df["price"].notnull()]

    # Beregn targetPercent
    df["targetPercent"] = ((df["target"] - df["price"]) / df["price"]) * 100

    # Fjern uønskede kolonner
    df = df.drop(columns=["pe", "debt_to_equity", "dividend_yield", "marketcap", "timestamp"], errors="ignore")

    # Sorter etter targetPercent
    df = df.sort_values(by="mom_1m", ascending=False)

    # Avrund tall
    for col in ["price", "target", "targetLow", "targetHigh", "pb", "mom_1d", "mom_1m", "mom_3m", "mom_1y", "targetPercent"]:
        if col in df.columns:
            df[col] = df[col].round(2)

    return df

# --- App setup ---
st.set_page_config(page_title="Aksjeradar", layout="centered", initial_sidebar_state="collapsed")

# --- CSS styling ---
st.markdown("""
    <style>
    .header {
        display: flex;
        align-items: center;
        gap: 10px;
        font-size: 25px;
    }
    </style>
""", unsafe_allow_html=True)

# Bruk inline base64-bilde i tittelen
st.markdown(
    f"""
    <div class="header">
        <img src="data:image/png;base64,{logo_b64}" width="40">
        Aksjeradar
    </div>
    """,
    unsafe_allow_html=True,
)

#st.caption("📈 Oppdag de mest spennende aksjene basert på nøkkeltall og momentum.")

df = load_stock_data()

# --- Vis data med AgGrid ---
#st.subheader("Toppliste")
st.caption("Trykk på en rad for å vise detaljer nedenfor 👇")

# Velg kolonner som skal vises
columns = [
    "ticker", "name", "price", "target", "mom_1m", "mom_3m", "mom_1y", "targetPercent"
]
df_display = df[columns].copy()

# Bygg AgGrid-oppsett
gb = GridOptionsBuilder.from_dataframe(df_display)
gb.configure_selection("single", use_checkbox=False)
gb.configure_pagination(enabled=True, paginationAutoPageSize=True, paginationPageSize=10)

# Fargekod targetPercent
cell_style_jscode = """
function(params) {
    if (params.value > 0) {
        return {'color': 'green', 'font-weight': 'bold'};
    } else if (params.value < 0) {
        return {'color': 'red', 'font-weight': 'bold'};
    } else {
        return {'color': 'black'};
    }
}
"""
#gb.configure_column("targetPercent", cellStyle=cell_style_jscode)
gb.configure_column("ticker", header_name="Ticker")
gb.configure_column("name", header_name="Navn")

grid_options = gb.build()

# Render tabellen
grid_response = AgGrid(
    df_display,
    gridOptions=grid_options,
    height=500,
    width="100%",
    fit_columns_on_grid_load=True,
)

# --- Hent valgt rad (robust versjon) ---
selected = grid_response.get("selected_rows")

# Noen ganger returneres en DataFrame — vi håndterer begge tilfeller
if selected is None:
    ticker = None
elif isinstance(selected, pd.DataFrame):
    ticker = selected.iloc[0]["ticker"] if not selected.empty else None
elif isinstance(selected, list) and len(selected) > 0:
    ticker = selected[0].get("ticker")
else:
    ticker = None

# --- Detaljvisning ---
if ticker:
    st.markdown("---")
    st.header(f"📊 Detaljer for {ticker}")

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
