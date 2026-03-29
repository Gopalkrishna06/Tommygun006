import requests
import yfinance as yf
import pandas as pd
import time
from datetime import datetime

# ── CONFIG ──────────────────────────────────────
BOT_TOKEN = "8432404167:AAEEeoZS_Tq65aCCB0VvtfFJkU5EHXK7up8"
CHAT_ID   = "834396362"
SYMBOL    = "^NSEI"
INTERVAL  = 300  # check every 5 minutes

# ── SEND TELEGRAM MESSAGE ───────────────────────
def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"})

# ── FETCH NIFTY DATA ────────────────────────────
def get_nifty_data():
    df = yf.download(SYMBOL, period="5d", interval="5m", progress=False)
    return df

# ── CALCULATE SIGNALS ───────────────────────────
def calculate_signals(df):
    close = df["Close"]

    # RSI
    delta = close.diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    rs    = gain / loss
    rsi   = 100 - (100 / (1 + rs))

    # MACD
    ema12 = close.ewm(span=12).mean()
    ema26 = close.ewm(span=26).mean()
    macd  = ema12 - ema26
    signal_line = macd.ewm(span=9).mean()

    return rsi.iloc[-1], macd.iloc[-1], signal_line.iloc[-1], close.iloc[-1]

# ── GENERATE SIGNAL ─────────────────────────────
def generate_signal():
    df  = get_nifty_data()
    rsi, macd, signal_line, ltp = calculate_signals(df)

    ltp        = round(float(ltp), 2)
    strike     = round(ltp / 50) * 50
    now        = datetime.now().strftime("%d-%b-%Y %H:%M")

    if rsi < 40 and macd > signal_line:
        direction = "CE 📈 (BULLISH)"
        action    = "BUY"
    elif rsi > 60 and macd < signal_line:
        direction = "PE 📉 (BEARISH)"
        action    = "BUY"
    else:
        return  # No clear signal

    msg = f"""
🚨 <b>NIFTY SIGNAL ALERT</b> 🚨

📅 Time     : {now}
💰 Nifty LTP: {ltp}
🎯 Strike   : {strike}
📊 Signal   : {action} {direction}
📉 RSI      : {round(float(rsi), 2)}

⚠️ Trade at your own risk!
"""
    send_telegram(msg)
    print(f"Signal sent: {action} {direction}")

# ── MAIN LOOP ───────────────────────────────────
if _name_ == "_main_":
    print("✅ Nifty Signal Bot Started!")
    send_telegram("✅ <b>Nifty Signal Bot is LIVE!</b> Monitoring market...")
    while True:
        try:
            generate_signal()
        except Exception as e:
            print(f"Error: {e}")
        time.sleep(INTERVAL)
