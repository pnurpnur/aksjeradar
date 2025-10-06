import requests
import sqlite3
import yfinance as yf
from datetime import datetime, timezone

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
    PRIMARY KEY (ticker, timestamp)
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
        (ticker, timestamp, pe, pb, debt_to_equity, dividend_yield, mom_1d, mom_1y, mom_1m, mom_3m, target, targetLow, targetHigh, price, marketcap, name)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, data)
    conn.commit()

def get_trending_tickers(region="US"):
    url = f"https://query1.finance.yahoo.com/v1/finance/trending/{region}"
    r = requests.get(url)
    print(r.json)
    data = r.json()
    tickers = [item["symbol"] for item in data["finance"]["result"][0]["quotes"]]
    return tickers

# ---- LISTE MED TICKERE ----

tickers = get_trending_tickers("US")

ts = datetime.now(timezone.utc).isoformat()
for t in tickers:
    update_ticker(t, ts)

conn.close()
