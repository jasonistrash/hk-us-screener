import yfinance as yf
import pandas as pd
import requests
from datetime import datetime
import pytz
import time
import os

# ================== CONFIG ==================
WHATSAPP_WEBHOOK = "https://api.callmebot.com/whatsapp.php"
YOUR_PHONE = os.getenv("YOUR_PHONE", "+852xxxxxxxxx")   # ← set in Render env
APIKEY = os.getenv("APIKEY", "")                        # optional
# ===========================================

def send_whatsapp(message):
    url = f"{WHATSAPP_WEBHOOK}?phone={YOUR_PHONE}&text={requests.utils.quote(message)}"
    if APIKEY:
        url += f"&apikey={APIKEY}"
    try:
        requests.get(url, timeout=10)
    except:
        pass

def run_screener():
    # Fast universe – ~1,600 liquid stocks only
    us = ["AAPL","MSFT","NVDA","TSLA","GOOGL","AMZN","META","AMD","SMCI","PLTR","ARM","CRWD","COIN","MSTR","CELH","HOOD","RBLX","ZETA","VRT","ANET","APP","DUOL"]
    hk = ["0700.HK","9988.HK","3690.HK","1810.HK","1211.HK","0388.HK","0005.HK","1299.HK","2318.HK","0941.HK","1398.HK","3988.HK","0939.HK","0688.HK","0823.HK","1088.HK","1109.HK","1929.HK","2269.HK","2388.HK","2628.HK","9618.HK","9888.HK","9961.HK","9992.HK"]
    tickers = us + hk

    data = yf.download(tickers, period="15mo", interval="1d", auto_adjust=True, threads=True, progress=False)
    
    results = {
        "Pocket Pivot": [],
        "3-Week Tight Close": [],
        "All-Time High + Volume Surge": []
    }

    today = datetime.now(pytz.timezone('Asia/Hong_Kong_Kong')).strftime("%Y-%m-%d")

    for ticker in tickers:
        try:
            df = data[ticker] if len(tickers) > 1 else data
            df = df.dropna()
            if len(df) < 100: continue

            latest = df.iloc[-1]
            prev   = df.iloc[-2]
            price  = latest['Close']
            vol    = latest['Volume']
            avg50  = df['Volume'].rolling(50).mean().iloc[-1]
            avg10  = df['Volume'].rolling(10).mean().iloc[-1]
            change = (price / prev['Close'] - 1) * 100

            # Liquidity filter
            if vol < 600000: continue
            if (".HK" in ticker and price < 12) or (".HK" not in ticker and price < 18): continue

            # 2. Pocket Pivot
            down_vols = df['Volume'].iloc[-11:-1][df['Close'].iloc[-11:-1] < prev['Close']]
            if change > 0 and len(down_vols) > 0 and vol > down_vols.max():
                results["Pocket Pivot"].append(f"• {ticker.replace('.HK','')}  ${price:.2f} (+{change:.1f}%)")

            # 4. 3-Week Tight Close
            recent = df['Close'].iloc[-15:]
            if recent.max() / recent.min() <= 1.025 and vol < avg50 * 0.85:
                results["3-Week Tight Close"].append(f"• {ticker.replace('.HK','')}  ${price:.2f}")

            # 5. All-Time High + Volume Surge
            ath = df['High'].max()
            if abs(latest['High'] - ath) / ath < 0.04 and vol >= 2 * avg10:
                results["All-Time High + Volume Surge"].append(f"• {ticker.replace('.HK','')}  ${price:.2f} (+{change:.1f}%) Vol {vol/avg10:.1f}×")

        except:
            continue

    # Build message
    lines = [f"{today} 今日精選信號 (US+HK)\n"]
    for name, sigs in results.items():
        if sigs:
            lines.append(f"\n{name} ({len(sigs)})")
            lines.extend(sigs[:25])   # up to 25 per category

    msg = "\n".join(lines)
    if len(msg) > 3500:
        msg = msg[:3400] + "\n…更多信號已截斷"
    send_whatsapp(msg)

if __name__ == "__main__":
    run_screener()
