import pandas as pd
import requests
import sqlite3
import yfinance as yf
from datetime import datetime, timezone
from io import StringIO

# Koble til database (lager aksjeradar.db hvis den ikke finnes)
conn = sqlite3.connect("aksjeradar.db")
cur = conn.cursor()

# Opprett tabell (kjøres bare én gang)
#cur.execute("""DROP TABLE stock_data""")
#conn.commit()
cur.execute("""
CREATE TABLE IF NOT EXISTS stock_data (
    ticker TEXT,
    timestamp TEXT,
    pe REAL,
    pb REAL,
    debt_to_equity REAL,
    dividend_yield REAL,
    mom_1d REAL,
    mom_1y REAL,
    mom_1m REAL,
    mom_3m REAL,
    price REAL,
    target REAL,
    targetLow REAL,
    targetHigh REAL,
    marketcap REAL,
    name TEXT,
    PRIMARY KEY (ticker)
)
""")
conn.commit()

# --- Hente og lagre data ---
def update_ticker(ticker, ts):
    tk = yf.Ticker(ticker)
    info = tk.info
    hist0 = tk.history(period="1d")
    hist = tk.history(period="1y")
    hist1 = tk.history(period="1mo")
    hist3 = tk.history(period="3mo")
    mom0 = mom = mom1 = mom3 = None
    if not hist0.empty:
        mom0 = (hist0["Close"].iloc[-1] / hist0["Close"].iloc[0] - 1) * 100
    if not hist.empty:
        mom = (hist["Close"].iloc[-1] / hist["Close"].iloc[0] - 1) * 100
    if not hist1.empty:
        mom1 = (hist1["Close"].iloc[-1] / hist1["Close"].iloc[0] - 1) * 100
    if not hist3.empty:
        mom3 = (hist3["Close"].iloc[-1] / hist3["Close"].iloc[0] - 1) * 100

    data = (
        ticker,
        ts,
        info.get("trailingPE"),
        info.get("priceToBook"),
        info.get("debtToEquity"),
        (info.get("dividendYield") or 0) * 100,
        mom0,
        mom,
        mom1,
        mom3,
        info.get("currentPrice"),
        info.get("targetMeanPrice"),
        info.get("targetLowPrice"),
        info.get("targetHighPrice"),
        info.get("marketCap"),
        info.get("longName"),
    )
    cur.execute("""
        INSERT OR REPLACE INTO stock_data
        (ticker, timestamp, pe, pb, debt_to_equity, dividend_yield, mom_1d, mom_1y, mom_1m, mom_3m, price, target, targetLow, targetHigh, marketcap, name)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, data)
    conn.commit()

"""Returnerer en liste med tickere som allerede ligger i databasen."""
cur.execute("SELECT DISTINCT ticker FROM stock_data;")
tickers = [row[0] for row in cur.fetchall()]
print(f"📊 Fant {len(tickers)} tickere i databasen.")

def get_trending_tickers(region="US"):
    url = f"https://query1.finance.yahoo.com/v1/finance/trending/{region}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/127.0.0.1 Safari/537.36"
    }

    r = requests.get(url, headers=headers)
    r.raise_for_status()
    data = r.json()

    try:
        result = data["finance"]["result"]
        for res in result:
            quotes = res.get("quotes", [])
            for q in quotes:
                if "symbol" in q and q["symbol"].isalpha and not '-' in q["symbol"]:
                    parts = q["symbol"].split('.', 1)  # Split only at the first occurrence of '.'
                    return [parts[0]]
    except (KeyError, IndexError) as e:
        print("JSON-struktur uventet:", e)
        return []

def get_finviz_top(category="ta_topgainers"):
    url = f"https://finviz.com/screener.ashx?v=111&s={category}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/127.0.0.1 Safari/537.36"
    }

    try:
        response = requests.get(url, headers=headers)
        tables = pd.read_html(StringIO(response.text))
        if not tables:
            return []
        df = tables[-2]  # Tabellen med aksjer
        return df["Ticker"].tolist()
    except Exception as e:
        print(f"[Finviz] Feil: {e}")
        return []

def get_stocktwits_trending():
    url = "https://api.stocktwits.com/api/2/trending/symbols.json"
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Referer": "https://stocktwits.com/",
            "Origin": "https://stocktwits.com"
        }

        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
        return [s["symbol"] for s in data.get("symbols", [])]
    except Exception as e:
        print(f"[StockTwits] Feil: {e}")
        return []

# ---- LISTE MED TICKERE ----
#tickers = []
tickers += get_trending_tickers("US")
tickers += get_trending_tickers("CA")
tickers += get_trending_tickers("GB")
tickers += get_finviz_top("ta_topgainers")
tickers += get_finviz_top("ta_mostactive")

unique = list(dict.fromkeys(tickers));

ts = datetime.now(timezone.utc).isoformat()
for t in unique:
    update_ticker(t, ts)

conn.close()
