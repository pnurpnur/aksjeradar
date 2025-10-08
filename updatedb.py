import sqlite3
import yfinance as yf
import requests
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from io import StringIO

DB_PATH = "aksjeradar.db"

#conn = sqlite3.connect(DB_PATH)
#cursor = conn.cursor()
#cursor.execute("DROP TABLE stock_data")
#conn.commit()

# -------------------------
# 1️⃣ Hent eksisterende tickere
# -------------------------
def get_existing_tickers():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS stock_data ( \
        ticker TEXT PRIMARY KEY, \
        timestamp TEXT, \
        pe REAL, \
        pb REAL, \
        debt_to_equity REAL, \
        dividend_yield REAL, \
        mom_1d REAL, \
        mom_1y REAL, \
        mom_1m REAL, \
        mom_3m REAL, \
        price REAL, \
        target REAL, \
        targetLow REAL, \
        targetHigh REAL, \
        marketcap REAL, \
        name TEXT \
    )")
    conn.commit()
    cursor.execute("SELECT ticker FROM stock_data")
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows]

# -------------------------
# 2️⃣ Hent trendende tickere fra Yahoo Finance
# -------------------------
def get_trending_yahoo(region="US"):
    url = f"https://query1.finance.yahoo.com/v1/finance/trending/{region}"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json"
    }
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
        symbols = [item["symbol"] for item in data["finance"]["result"][0]["quotes"]]
        return symbols
    except Exception as e:
        print(f"[Yahoo Trending] Feil: {e}")
        return []

# -------------------------
# 3️⃣ Hent trendende tickere fra Finviz
# -------------------------
def get_finviz(category="ta_topgainers"):
    url = "https://finviz.com/screener.ashx?v=111&s=ta_topgainers"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/126.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": "https://finviz.com/",
        "Connection": "keep-alive"
    }

    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()

        soup = BeautifulSoup(r.text, "html.parser")
        tickers = []

        for a in soup.select("a.tab-link"):
            symbol = a.text.strip()
            if symbol.isalpha():
                tickers.append(symbol)

        print(f"Hentet {len(tickers)} tickere fra Finviz gainers.")
        return tickers

    except requests.exceptions.HTTPError as e:
        print(f"[Finviz] HTTP-feil: {e}")
        print(f"Responskode: {r.status_code}")
        return []
    except Exception as e:
        print(f"[Finviz] Feil: {e}")
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

# -------------------------
# 4️⃣ Kombiner alle kilder
# -------------------------
def get_all_tickers():
    existing = get_existing_tickers()
    yahoo_US = get_trending_yahoo()
    yahoo_CA = get_trending_yahoo("CA")
    yahoo_GB = get_trending_yahoo("GB")
    finviz_top = get_finviz_top("ta_topgainers")
    finviz_active = get_finviz_top("ta_mostactive")

    all_tickers = set(existing + yahoo_US + yahoo_CA + yahoo_GB + finviz_top + finviz_active)
    all_tickers = [t for t in all_tickers if t.isalpha()]  # kun bokstaver (fjerner rare symboler)
    print(f"Totalt {len(all_tickers)} tickere (inkludert eksisterende og trendende).")
    return all_tickers

# -------------------------
# 5️⃣ Beregn momentum for en ticker
# -------------------------
def calculate_momentum(ticker):
    try:
        tk = yf.Ticker(ticker)
        hist = tk.history(period="2y")
        if hist.empty:
            return None, None, None, None, None

        # Siste pris
        latest = hist["Close"].iloc[-1]

        def pct_change(days):
            if len(hist) < days + 1:
                return None
            old_price = hist["Close"].iloc[-(days + 1)]
            return ((latest - old_price) / old_price) * 100

        mom_1d = pct_change(1)
        mom_1m = pct_change(22)   # ~22 handelsdager
        mom_3m = pct_change(66)   # ~66 handelsdager
        mom_1y = pct_change(252)  # ~1 handelsår

        return latest, mom_1d, mom_1m, mom_3m, mom_1y

    except Exception as e:
        print(f"[Momentum] Feil ved {ticker}: {e}")
        return None, None, None, None, None

# -------------------------
# 5️⃣ Hent data fra yfinance og oppdater DB
# -------------------------
def update_database():
    tickers = get_all_tickers()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    ts = datetime.now(timezone.utc)

    for t in tickers:
        try:
            tk = yf.Ticker(t)
            info = tk.info

            price, mom_1d, mom_1m, mom_3m, mom_1y = calculate_momentum(t)
            if not price:
                continue  # hopp over tickere uten pris

            data = (
                t,
                ts,
                info.get("trailingPE"),
                info.get("priceToBook"),
                info.get("debtToEquity"),
                info.get("dividendYield"),
                mom_1d,
                mom_1y,
                mom_1m,
                mom_3m,
                price,
                info.get("targetMeanPrice"),
                info.get("targetLowPrice"),
                info.get("targetHighPrice"),
                info.get("marketCap"),
                info.get("shortName", "")
            )

            cursor.execute("""
                INSERT OR REPLACE INTO stock_data
                (ticker, timestamp, pe, pb, debt_to_equity, dividend_yield,
                 mom_1d, mom_1y, mom_1m, mom_3m, price, target, targetLow,
                 targetHigh, marketcap, name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, data)

            print(f"✅ Oppdatert {t}")

        except Exception as e:
            print(f"⚠️ Feil ved {t}: {e}")

    conn.commit()
    conn.close()
    print("✅ Ferdig oppdatert database.")

# -------------------------
# 6️⃣ Kjør skriptet
# -------------------------
if __name__ == "__main__":
    update_database()
