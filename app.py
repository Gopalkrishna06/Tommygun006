import requests
import yfinance as yf
import os
from datetime import datetime

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID   = os.environ.get("CHAT_ID")
SYMBOL    = "^NSEI"

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"})

def get_nifty_data():
    df = yf.download(SYMBOL, period="5d", interval="5m", progress=False)
    return df

def calculate_signals(df):
    close = df["Close"].squeeze()
    delta = close.diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    rs    = gain / loss
    rsi   = 100 - (100 / (1 + rs))
    ema12 = close.ewm(span=12).mean()
    ema26 = close.ewm(span=26).mean()
    macd  = ema12 - ema26
    signal_line = macd.ewm(span=9).mean()
    rsi_val    = float(rsi.iloc[-1])
    macd_val   = float(macd.iloc[-1])
    signal_val = float(signal_line.iloc[-1])
    ltp_val    = float(close.iloc[-1])
    return rsi_val, macd_val, signal_val, ltp_val

def generate_signal():
    df  = get_nifty_data()
    rsi, macd, signal_line, ltp = calculate_signals(df)
    ltp    = round(ltp, 2)
    strike = round(ltp / 50) * 50
    now    = datetime.now().strftime("%d-%b-%Y %H:%M")

    if rsi < 40 and macd > signal_line:
        direction = "CE 📈 (BULLISH)"
        action    = "BUY"
    elif rsi > 60 and macd < signal_line:
        direction = "PE 📉 (BEARISH)"
        action    = "BUY"
    else:
        send_telegram(f"⏳ <b>No clear signal</b> at {now}\nNifty LTP: {ltp}")
        return

    msg = f"""
🚨 <b>NIFTY SIGNAL ALERT</b> 🚨

📅 Time     : {now}
💰 Nifty LTP: {ltp}
🎯 Strike   : {strike}
📊 Signal   : {action} {direction}
📉 RSI      : {round(rsi, 2)}

⚠️ Trade at your own risk!
"""
    send_telegram(msg)
    print(f"Signal sent: {action} {direction}")

if __name__ == "__main__":
    send_telegram("✅ <b>Bot is working! Ready for Monday market!</b>")
    generate_signal()
