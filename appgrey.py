import streamlit as st
import pandas as pd
import sqlite3
import yfinance as yf
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

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

    # Rund av for pen visning
    df["targetPercent"] = df["targetPercent"].round(2)
    return df


# --- Farge på targetPercent (for bruk i AgGrid) ---
def color_for_value(value):
    if pd.isna(value):
        return "black"
    elif value > 0:
        return "green"
    elif value < 0:
        return "red"
    return "black"


# --- App ---
st.set_page_config(page_title="Aksjeradar", layout="wide")
st.title("📊 Aksjeradar — Beste kjøpskandidater")

df = load_stock_data()

# --- Paginering ---
page_size = 10
num_pages = (len(df) - 1) // page_size + 1
page = st.number_input("Side", 1, num_pages, 1)
start = (page - 1) * page_size
end = start + page_size
df_page = df.iloc[start:end].reset_index(drop=True)

# --- Formatér for visning ---
df_page["targetPercentStr"] = df_page["targetPercent"].apply(
    lambda x: f"{x:+.2f}%" if pd.notna(x) else "-"
)
df_page["color"] = df_page["targetPercent"].apply(color_for_value)

# --- Konfigurer AgGrid ---
gb = GridOptionsBuilder.from_dataframe(
    df_page[["ticker", "name", "price", "target", "targetLow", "targetHigh", "targetPercentStr"]]
)
gb.configure_pagination(paginationAutoPageSize=False, paginationPageSize=10)
gb.configure_selection("single", use_checkbox=False)
gb.configure_default_column(editable=False, wrapText=True, autoHeight=True)
gb.configure_column(
    "targetPercentStr",
    headerName="Target %",
    cellStyle={"fontWeight": "bold"},
)
gb.configure_column("ticker", headerName="Ticker", cellStyle={"fontWeight": "bold"})
grid_options = gb.build()

# --- Render AgGrid ---
st.subheader(f"Toppliste (side {page}/{num_pages}) — sortert etter oppside mot targetpris")
st.caption("Klikk på en rad for å vise detaljer nedenfor 👇")

grid_response = AgGrid(
    df_page,
    gridOptions=grid_options,
    update_mode=GridUpdateMode.SELECTION_CHANGED,
    allow_unsafe_jscode=True,
    theme="streamlit",
    width="container",
)

# --- Hent valgt ticker ---
selected_rows = grid_response["selected_rows"]
selected_ticker = selected_rows[0]["ticker"] if selected_rows else None

# --- Detaljvisning ---
if selected_ticker:
    st.markdown("---")
    st.header(f"📈 Detaljer for {selected_ticker}")

    try:
        tk = yf.Ticker(selected_ticker)
        info = tk.info

        col1, col2 = st.columns([1, 1])

        with col1:
            st.markdown(f"### {info.get('longName', selected_ticker)}")
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
        st.error(f"Kunne ikke hente data for {selected_ticker}: {e}")
