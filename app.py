import requests
import yfinance as yf
import os
import pytz
import pandas as pd
import numpy as np
from datetime import datetime

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID   = os.environ.get("CHAT_ID")
SYMBOL    = "^NSEI"
IST       = pytz.timezone("Asia/Kolkata")

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"})

def get_nifty_data():
    df = yf.download(SYMBOL, period="5d", interval="5m", progress=False)
    df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    return df

def calculate_rsi(close, period=14):
    delta = close.diff()
    gain  = delta.clip(lower=0).rolling(period).mean()
    loss  = (-delta.clip(upper=0)).rolling(period).mean()
    rs    = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_macd(close):
    ema12  = close.ewm(span=12).mean()
    ema26  = close.ewm(span=26).mean()
    macd   = ema12 - ema26
    signal = macd.ewm(span=9).mean()
    return macd, signal

def calculate_supertrend(df, period=10, multiplier=3):
    hl2 = (df['High'] + df['Low']) / 2
    tr  = pd.concat([
        df['High'] - df['Low'],
        (df['High'] - df['Close'].shift()).abs(),
        (df['Low']  - df['Close'].shift()).abs()
    ], axis=1).max(axis=1)
    atr   = tr.rolling(period).mean()
    upper = hl2 + multiplier * atr
    lower = hl2 - multiplier * atr
    direction = pd.Series(1, index=df.index)
    for i in range(1, len(df)):
        if df['Close'].iloc[i] > upper.iloc[i-1]:
            direction.iloc[i] = 1
        elif df['Close'].iloc[i] < lower.iloc[i-1]:
            direction.iloc[i] = -1
        else:
            direction.iloc[i] = direction.iloc[i-1]
    return int(direction.iloc[-1])

def detect_candle(df):
    o = float(df['Open'].iloc[-1])
    h = float(df['High'].iloc[-1])
    l = float(df['Low'].iloc[-1])
    c = float(df['Close'].iloc[-1])
    body       = abs(c - o)
    upper_wick = h - max(o, c)
    lower_wick = min(o, c) - l
    full_range = h - l
    if full_range == 0:
        return "NEUTRAL", "Doji ➡️"
    if lower_wick > 2 * body and upper_wick < body:
        return "BULLISH", "Hammer 🔨"
    if c > o and body > full_range * 0.6:
        return "BULLISH", "Bullish Candle 📈"
    if upper_wick > 2 * body and lower_wick < body:
        return "BEARISH", "Shooting Star ⭐"
    if c < o and body > full_range * 0.6:
        return "BEARISH", "Bearish Candle 📉"
    return "NEUTRAL", "Doji ➡️"

def get_oi_data(spot):
    try:
        session = requests.Session()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept": "*/*",
            "Referer": "https://www.nseindia.com"
        }
        session.get("https://www.nseindia.com", headers=headers, timeout=10)
        url  = "https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY"
        resp = session.get(url, headers=headers, timeout=10)
        data = resp.json()['records']['data']
        ce_oi = {}
        pe_oi = {}
        for rec in data:
            strike = rec['strikePrice']
            if abs(strike - spot) <= 500:
                if 'CE' in rec:
                    ce_oi[strike] = rec['CE'].get('openInterest', 0)
                if 'PE' in rec:
                    pe_oi[strike] = rec['PE'].get('openInterest', 0)
        max_ce = max(ce_oi, key=ce_oi.get) if ce_oi else round(spot/50)*50
        max_pe = max(pe_oi, key=pe_oi.get) if pe_oi else round(spot/50)*50
        return max_ce, max_pe
    except:
        atm = round(spot / 50) * 50
        return atm, atm

def generate_signal():
    df = get_nifty_data()
    if df.empty:
        return

    close  = df['Close'].squeeze()
    ltp    = round(float(close.iloc[-1]), 2)
    atm    = round(ltp / 50) * 50
    now    = datetime.now(IST).strftime("%d-%b-%Y %H:%M IST")

    rsi_series        = calculate_rsi(close)
    macd, signal_line = calculate_macd(close)
    rsi_val    = float(rsi_series.iloc[-1])
    macd_val   = float(macd.iloc[-1])
    signal_val = float(signal_line.iloc[-1])
    st_dir     = calculate_supertrend(df)
    candle_dir, candle_name = detect_candle(df)
    ce_oi_strike, pe_oi_strike = get_oi_data(ltp)

    bullish = 0
    bearish = 0

    if rsi_val < 40:          bullish += 1
    if rsi_val > 60:          bearish += 1
    if macd_val > signal_val: bullish += 1
    if macd_val < signal_val: bearish += 1
    if st_dir == 1:           bullish += 1
    if st_dir == -1:          bearish += 1
    if candle_dir == "BULLISH": bullish += 1
    if candle_dir == "BEARISH": bearish += 1

    if bullish >= 3:
        action    = "BUY"
        direction = "CE 📈 (BULLISH)"
        otm       = atm + 100
        itm       = atm - 50
        oi_note   = f"Max CE OI Strike: {ce_oi_strike}"
        sl        = round(ltp * 0.995, 2)
        target    = round(ltp * 1.01, 2)
        score     = bullish
    elif bearish >= 3:
        action    = "BUY"
        direction = "PE 📉 (BEARISH)"
        otm       = atm - 100
        itm       = atm + 50
        oi_note   = f"Max PE OI Strike: {pe_oi_strike}"
        sl        = round(ltp * 1.005, 2)
        target    = round(ltp * 0.99, 2)
        score     = bearish
    else:
        return

    msg = f"""
🚨 <b>NIFTY SIGNAL ALERT</b> 🚨

📅 Time       : {now}
💰 Nifty LTP  : {ltp}

🎯 <b>STRIKES</b>
• ATM  : {atm}
• OTM  : {otm}
• ITM  : {itm}
• {oi_note}

📊 <b>SIGNAL</b>  : {action} {direction}
🕯 <b>Candle</b>  : {candle_name}

📉 <b>INDICATORS</b>
• RSI         : {round(rsi_val, 2)}
• MACD        : {"↑" if macd_val > signal_val else "↓"}
• Supertrend  : {"↑ BULLISH" if st_dir == 1 else "↓ BEARISH"}
• Score       : {score}/4 confirmations ✅

🛑 Nifty SL   : {sl}
🎯 Nifty TGT  : {target}

⚠️ Trade at your own risk!
"""
    send_telegram(msg)
    print(f"Signal sent: {action} {direction} | Score: {score}/4")

if __name__ == "__main__":
    generate_signal()
