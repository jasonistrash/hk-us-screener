import yfinance as yf
import pandas as pd
import requests
from datetime import datetime, timedelta
import pytz

# ================== CONFIGURATION ==================
# Your WhatsApp bot endpoint (change only if your provider uses a different URL)
WHATSAPP_WEBHOOK = "https://api.callmebot.com/whatsapp.php"  # Works for +34644872157

# Your phone number in international format (with +)
YOUR_PHONE = "+852xxxxxxxx"   # ← CHANGE THIS TO YOUR NUMBER

# Choose notification method: "callmebot" or "ultra-msg" or "custom"
# Most +34 Spanish bots use callmebot format
NOTIFY_METHOD = "callmebot"   # ← keep this if using +34644872157

# ===================================================

def send_whatsapp(message):
    if NOTIFY_METHOD == "callmebot":
        url = f"{WHATSAPP_WEBHOOK}?phone={YOUR_PHONE}&text={requests.utils.quote(message)}&apikey=123456"
        # ↑ replace 123456 with your real apikey if your bot requires one (many free ones don't)
        try:
            requests.get(url, timeout=10)
        except:
            pass
    else:
        # fallback for other providers
        payload = {"number": YOUR_PHONE, "message": message}
        try:
            requests.post(WHATSAPP_WEBHOOK, json=payload, timeout=10)
        except:
            pass

def get_signals():
    # Universe: big liquid US + HK stocks (FIXED: reliable HK tickers only – tested live Nov 28, 2025)
    us_tickers = ["NVDA","SMCI","PLTR","ARM","COIN","MSTR","CRWD","APP","CELH","LLY","META","TSLA","AMD","AVGO","MSFT","AAPL","AMZN","GOOGL"]
    hk_tickers = [
        "0700.HK",  # Tencent
        "9988.HK",  # Alibaba
        "3690.HK",  # Meituan
        "1810.HK",  # Xiaomi
        "1211.HK",  # BYD
        "0388.HK",  # HKEX
        "0005.HK",  # HSBC
        "1299.HK",  # AIA
        "9999.HK",  # Trip.com
        "2318.HK",  # Ping An
        "0941.HK",  # China Mobile
        "1398.HK",  # ICBC
        "3988.HK",  # Bank of China
        "0002.HK",  # CLP Holdings
        "0003.HK",  # HK & China Gas
        "0011.HK",  # Hang Seng Bank
        "0016.HK",  # SHK Properties
        "0017.HK",  # New World Dev
        "0066.HK",  # MTR Corp
        "0823.HK",  # Link REIT
        "1088.HK"   # China Shenhua
    ]

    all_tickers = us_tickers + hk_tickers
    data = yf.download(all_tickers, period="18mo", interval="1d", group_by="ticker", auto_adjust=True)

    results = {
        "Stage 2 Breakout": [],
        "Pocket Pivot": [],
        "Power Play": [],
        "3-Week Tight Close": [],
        "All-Time High + Volume Surge": [],
        "IBD 50-style CANSLIM": []
    }

    hk_time = datetime.now(pytz.timezone('Asia/Hong_Kong'))
    today_str = hk_time.strftime("%Y-%m-%d")

    for ticker in all_tickers:
        try:
            df = data[ticker].copy() if len(all_tickers) > 1 else data.copy()
            df = df.dropna()

            if len(df) < 300:
                continue

            latest = df.iloc[-1]
            prev = df.iloc[-2]
            price = latest['Close']
            volume = latest['Volume']
            avg_vol_50 = df['Volume'].rolling(50).mean().iloc[-1]
            avg_vol_10 = df['Volume'].rolling(10).mean().iloc[-1]

            # Basic filters
            if (".HK" in ticker and price < 10) or (".HK" not in ticker and price < 15):
                continue
            if volume < 500000:
                continue

            high_52w = df['High'].rolling(252).max().iloc[-1]
            low_52w = df['Low'].rolling(252).min().iloc[-1]
            sma_30w = df['Close'].rolling(150).mean().iloc[-1]  # ≈30 weeks

            rs = len([t for t in all_tickers if yf.Ticker(t).info.get('52WeekChange',0) < latest.get('52WeekChange',0)]) / len(all_tickers) * 100

            change_pct = (price / prev['Close'] - 1) * 100

            # 1. Stage 2 Breakout
            if price > sma_30w and latest['High'] >= high_52w and volume >= 1.5 * avg_vol_50 and rs >= 85:
                results["Stage 2 Breakout"].append(f"• {ticker.replace('.HK','')}   ${price:.2f}  ({change_pct:+.1f}%)  Vol {volume/avg_vol_50:.1f}×  RS {rs:.0f}")

            # 2. Pocket Pivot
            if change_pct > 0 and volume > max(df['Volume'].iloc[-10:-1][df['Close'].iloc[-10:-1] < prev['Close']]):
                results["Pocket Pivot"].append(f"• {ticker.replace('.HK','')}   ${price:.2f}  ({change_pct:+.1f}%)  Vol {volume/max(df['Volume'].iloc[-10:-1]):.1f}×")

            # 3. Power Play
            if latest['High'] >= high_52w * 0.95 and volume >= 2 * avg_vol_50:
                results["Power Play"].append(f"• {ticker.replace('.HK','')}   ${price:.2f}  ({change_pct:+.1f}%)  Vol {volume/avg_vol_50:.1f}×")

            # 4. 3-Week Tight Close
            recent_3w = df['Close'].iloc[-15:]
            if recent_3w.max() / recent_3w.min() <= 1.02 and volume < avg_vol_50 * 0.8:
                results["3-Week Tight Close"].append(f"• {ticker.replace('.HK','')}   ${price:.2f}  ({change_pct:+.1f}%)")

            # 5. All-Time High + Volume Surge
            all_time_high = df['High'].max()
            if abs(latest['High'] - all_time_high) / all_time_high < 0.03 and volume >= 2 * avg_vol_10:
                results["All-Time High + Volume Surge"].append(f"• {ticker.replace('.HK','')}   ${price:.2f}  ({change_pct:+.1f}%)  Vol {volume/avg_vol_10:.1f}×")

            # 6. IBD 50-style CANSLIM (simplified)
            info = yf.Ticker(ticker).info
            eps_growth = info.get("earningsQuarterlyGrowth", 0)
            if eps_growth > 0.25 and rs >= 80 and price > sma_30w:
                results["IBD 50-style CANSLIM"].append(f"• {ticker.replace('.HK','')}   ${price:.2f}  EPS↑{eps_growth:.0%}")

        except:
            continue

    # Build final message
    lines = [f"{today_str} 今日自動掃描結果 (US + HK)\n"]
    for name, signals in results.items():
        if signals:
            lines.append(f"\n{name} ({len(signals)})")
            lines.extend(signals[:15])  # max 15 per category to avoid message too long

    final_message = "\n".join(lines)
    if len(final_message) > 3000:
        final_message = final_message[:2900] + "\n... (truncated)"

    send_whatsapp(final_message)

if __name__ == "__main__":
    get_signals()
