import sqlite3
import yfinance as yf
import requests
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from io import StringIO
import os
import subprocess

# ----------------------------------------
# 💾 GCS-støtte
# ----------------------------------------
DB_PATH = "aksjeradar.db"
BUCKET_NAME = "arcane-woods-475308-j7-sqlite"
GCS_URI = f"gs://{BUCKET_NAME}/{DB_PATH}"

def download_db_from_gcs():
    """Hent eksisterende database fra GCS hvis den finnes."""
    print(f"📥 Laster ned {GCS_URI} (hvis den finnes)...")
    try:
        subprocess.run(["gsutil", "cp", GCS_URI, DB_PATH], check=False)
    except Exception as e:
        print(f"⚠️ Kunne ikke laste ned database fra GCS: {e}")

def upload_db_to_gcs():
    """Last opp oppdatert database til GCS."""
    print(f"📤 Laster opp {DB_PATH} til {GCS_URI}...")
    try:
        subprocess.run(["gsutil", "cp", DB_PATH, GCS_URI], check=True)
    except Exception as e:
        print(f"⚠️ Kunne ikke laste opp database til GCS: {e}")

# ----------------------------------------
# Resten av koden din (uendret)
# ----------------------------------------

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


def get_trending_yahoo(region="US"):
    url = f"https://query1.finance.yahoo.com/v1/finance/trending/{region}"
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
        symbols = [item["symbol"] for item in data["finance"]["result"][0]["quotes"]]
        return symbols
    except Exception as e:
        print(f"[Yahoo Trending] Feil: {e}")
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
        df = tables[-2]
        return df["Ticker"].tolist()
    except Exception as e:
        print(f"[Finviz] Feil: {e}")
        return []


def get_all_tickers():
    existing = get_existing_tickers()
    yahoo_US = get_trending_yahoo()
    yahoo_CA = get_trending_yahoo("CA")
    yahoo_GB = get_trending_yahoo("GB")
    finviz_top = get_finviz_top("ta_topgainers")
    finviz_active = get_finviz_top("ta_mostactive")

    all_tickers = set(existing + yahoo_US + yahoo_CA + yahoo_GB + finviz_top + finviz_active)
    all_tickers = [t for t in all_tickers if t.isalpha()]
    print(f"Totalt {len(all_tickers)} tickere (inkludert eksisterende og trendende).")
    return all_tickers


def calculate_momentum(ticker):
    try:
        tk = yf.Ticker(ticker)
        hist = tk.history(period="2y")
        if hist.empty:
            return None, None, None, None, None
        latest = hist["Close"].iloc[-1]

        def pct_change(days):
            if len(hist) < days + 1:
                return None
            old_price = hist["Close"].iloc[-(days + 1)]
            return ((latest - old_price) / old_price) * 100

        mom_1d = pct_change(1)
        mom_1m = pct_change(22)
        mom_3m = pct_change(66)
        mom_1y = pct_change(252)
        return latest, mom_1d, mom_1m, mom_3m, mom_1y
    except Exception as e:
        print(f"[Momentum] Feil ved {ticker}: {e}")
        return None, None, None, None, None


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
                continue
            data = (
                t, ts, info.get("trailingPE"), info.get("priceToBook"),
                info.get("debtToEquity"), info.get("dividendYield"),
                mom_1d, mom_1y, mom_1m, mom_3m, price,
                info.get("targetMeanPrice"), info.get("targetLowPrice"),
                info.get("targetHighPrice"), info.get("marketCap"),
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


if __name__ == "__main__":
    # 🔹 Nye linjer: last ned DB → kjør → last opp
    download_db_from_gcs()
    update_database()
    upload_db_to_gcs()
