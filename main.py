import pandas as pd
import requests
from datetime import datetime
import pytz
import time
import io
import os  # For env vars

# Safe yfinance import (with fallback if live module fails)
try:
    import yfinance as yf
except ImportError as e:
    print(f"yfinance import error: {e}")
    yf = None  # Graceful fail – but shouldn't happen with websockets

# ================== CONFIGURATION ==================
WHATSAPP_WEBHOOK = "https://api.callmebot.com/whatsapp.php"
YOUR_PHONE = os.getenv("YOUR_PHONE", "+852xxxxxxxxx")  # Pulls from Render env var
NOTIFY_METHOD = "callmebot"
APIKEY = os.getenv("APIKEY", "")  # Optional for your bot
# ===================================================

def send_whatsapp(message):
    if NOTIFY_METHOD == "callmebot":
        url = f"{WHATSAPP_WEBHOOK}?phone={YOUR_PHONE}&text={requests.utils.quote(message)}"
        if APIKEY:
            url += f"&apikey={APIKEY}"
        try:
            response = requests.get(url, timeout=15)
            print(f"WhatsApp sent: {response.status_code}")
        except Exception as e:
            print(f"WhatsApp error: {e}")

def get_full_universe():
    us_tickers = []
    hk_tickers = []

    # —— US stocks (NASDAQ + NYSE + AMEX) ——
    try:
        nasdaq_url = "https://ftp.nasdaqtrader.com/SymbolDirectory/nasdaqlisted.txt"
        other_url = "https://ftp.nasdaqtrader.com/SymbolDirectory/otherlisted.txt"
        nasdaq = pd.read_csv(nasdaq_url, sep="|")
        other = pd.read_csv(other_url, sep="|")
        us1 = nasdaq[nasdaq["Test Issue"] == "N"]["Symbol"].dropna().tolist()
        us2 = other[other["Test Issue"] == "N"]["ACT Symbol"].dropna().tolist()
        us_tickers = list(set(us1 + us2))
        print(f"US tickers loaded: {len(us_tickers)}")
    except Exception as e:
        print(f"US fetch error: {e}")
        us_tickers = ["AAPL","MSFT","NVDA","TSLA","GOOGL"]

    # —— HK stocks (Hang Seng + major blue chips) ——
    try:
        url = "https://finance.yahoo.com/quote/%5EHSI/components/"
        tables = pd.read_html(url)
        if tables and len(tables) > 0:
            hsi = tables[0]["Symbol"].str.replace("*","").tolist()
        else:
            hsi = []
        hk_extra = ["0001.HK","0002.HK","0003.HK","0005.HK","0011.HK","0016.HK","0019.HK","0066.HK","0083.HK","0388.HK","0700.HK","09988.HK","03690.HK","01810.HK","01211.HK","00941.HK","01398.HK","03988.HK","00939.HK","0688.HK","0823.HK","1088.HK","1109.HK","1929.HK","2269.HK","2388.HK","2628.HK","3328.HK","3968.HK","9618.HK","9888.HK","9961.HK","9992.HK"]
        hk_tickers = list(set([t + ".HK" if not t.endswith(".HK") else t for t in hsi + hk_extra]))
        print(f"HK tickers loaded: {len(hk_tickers)}")
    except Exception as e:
        print(f"HK fetch error: {e}")
        hk_tickers = ["0700.HK","9988.HK","3690.HK","0005.HK","0388.HK"]

    return us_tickers, hk_tickers

def get_signals():
    if yf is None:
        print("yfinance not available – exiting")
        return

    us_tickers, hk_tickers = get_full_universe()
    all_tickers = us_tickers[:1500] + hk_tickers  # ~1,600 total = perfect balance
    print(f"Scanning {len(all_tickers)} tickers...")

    results = {
        "Stage 2 Breakout": [],
        "Pocket Pivot": [],
        "Power Play": [],
        "3-Week Tight Close": [],
        "All-Time High + Volume Surge": [],
        "IBD 50-style CANSLIM": []
    }

    # Batch download (200 at a time – safe for Render free tier)
    batch_size = 200
    data = {}
    for i in range(0, len(all_tickers), batch_size):
        batch = all_tickers[i:i+batch_size]
        try:
            batch_data = yf.download(batch, period="18mo", interval="1d", auto_adjust=True, threads=True, progress=False)
            # Handle single ticker case
            if isinstance(batch_data.columns, pd.MultiIndex) and len(batch) > 1:
                for t in batch:
                    if t in batch_data:
                        data[t] = batch_data[t].dropna()
            else:
                # Single or flat
                for t in batch:
                    if t in batch_data.columns.get_level_values(0) or t in batch_data:
                        data[t] = batch_data[t].dropna() if isinstance(batch_data, dict) else batch_data
            time.sleep(0.3)  # Rate limit
            print(f"Batch {i//batch_size + 1} done")
        except Exception as e:
            print(f"Batch {i//batch_size + 1} error: {e}")
            continue

    hk_time = datetime.now(pytz.timezone('Asia/Hong_Kong')).strftime("%Y-%m-%d")
    print(f"Data loaded – building message for {hk_time}")

    for ticker in all_tickers:
        try:
            if ticker not in data or data[ticker].empty:
                continue
            df = data[ticker]
            if len(df) < 300:
                continue

            latest = df.iloc[-1]
            prev = df.iloc[-2]
            price = latest['Close']
            volume = latest['Volume']
            avg_vol_50 = df['Volume'].rolling(50).mean().iloc[-1]
            avg_vol_10 = df['Volume'].rolling(10).mean().iloc[-1]

            # Liquidity filter
            if volume < 500000 or avg_vol_50 < 800000:
                continue
            if (".HK" in ticker and price < 10) or (".HK" not in ticker and price < 15):
                continue

            high_52w = df['High'].rolling(252).max().iloc[-1]
            sma_30w = df['Close'].rolling(150).mean().iloc[-1]
            change_pct = (price / prev['Close'] - 1) * 100

            # 1. Stage 2 Breakout
            if price > sma_30w and latest['High'] >= high_52w and volume >= 1.5 * avg_vol_50:
                results["Stage 2 Breakout"].append(f"• {ticker.replace('.HK','')}   ${price:.2f}  (+{change_pct:.1f}%)  Vol {volume/avg_vol_50:.1f}×")

            # 2. Pocket Pivot (fixed index logic)
            down_mask = df['Close'].iloc[-11:-1] < prev['Close']
            down_days_vol = df['Volume'].iloc[-11:-1][down_mask]
            if change_pct > 0 and len(down_days_vol) > 0 and volume > down_days_vol.max():
                results["Pocket Pivot"].append(f"• {ticker.replace('.HK','')}   ${price:.2f}  (+{change_pct:.1f}%)")

            # 3. Power Play
            if latest['High'] >= high_52w * 0.95 and volume >= 2 * avg_vol_50:
                results["Power Play"].append(f"• {ticker.replace('.HK','')}   ${price:.2f}  (+{change_pct:.1f}%)")

            # 4. 3-Week Tight Close
            recent = df['Close'].iloc[-15:]
            if recent.max() / recent.min() <= 1.02 and volume < avg_vol_50 * 0.8:
                results["3-Week Tight Close"].append(f"• {ticker.replace('.HK','')}   ${price:.2f}")

            # 5. All-Time High + Volume Surge
            ath = df['High'].max()
            if abs(latest['High'] - ath) / ath < 0.03 and volume >= 2 * avg_vol_10:
                results["All-Time High + Volume Surge"].append(f"• {ticker.replace('.HK','')}   ${price:.2f}  (+{change_pct:.1f}%)")

            # 6. CANSLIM simplified (use info dict, not fast_info)
            try:
                info = yf.Ticker(ticker).info
                eps = info.get('earningsQuarterlyGrowth', 0)
                if eps > 0.25 and price > sma_30w:
                    results["IBD 50-style CANSLIM"].append(f"• {ticker.replace('.HK','')}   ${price:.2f}  EPS↑{eps:.0%}")
            except:
                pass

        except Exception as e:
            print(f"Ticker {ticker} error: {e}")
            continue

    # Build message
    lines = [f"{hk_time} 今日自動掃描結果 (US+HK 全市場 ~1600 stocks)\n"]
    for name, sigs in results.items():
        if sigs:
            lines.append(f"\n{name} ({len(sigs)})")
            lines.extend(sigs[:20])  # max 20 per category

    msg = "\n".join(lines)
    if len(msg) > 3000:
        msg = msg[:2900] + "\n... (truncated)"
    send_whatsapp(msg)
    print("Scan complete – message sent!")

if __name__ == "__main__":
    print("Starting HK/US Stock Screener...")
    get_signals()
    print("Script finished.")
