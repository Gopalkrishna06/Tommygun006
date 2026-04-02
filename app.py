import requests
import yfinance as yf
import os
import pytz
from datetime import datetime
import pandas as pd

# Configs
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
SYMBOL = "^NSEI"
IST = pytz.timezone("Asia/Kolkata")

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"})

def get_nifty_data():
    df = yf.download(SYMBOL, period="5d", interval="5m", progress=False)
    return df

def get_option_chain(ltp):
    strikes = [round(ltp / 50) * 50 + i*50 for i in range(-5, 6)]
    return strikes

def calculate_signals(df):
    delta = df["Close"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    
    ema12 = df["Close"].ewm(span=12).mean()
    ema26 = df["Close"].ewm(span=26).mean()
    macd = ema12 - ema26
    signal_line = macd.ewm(span=9).mean()
    
    atr = (df["High"] - df["Low"]).rolling(14).mean()
    hl2 = (df["High"] + df["Low"]) / 2
    upper = hl2 + (2 * atr)
    lower = hl2 - (2 * atr)
    supertrend = []
    for i in range(len(df)):
        if i == 0:
            supertrend.append(None)
            continue
        prev_close = df["Close"].iloc[i-1]
        prev_upper = upper.iloc[i-1]
        if prev_close <= prev_upper:
            supertrend.append(upper.iloc[i])
        else:
            supertrend.append(lower.iloc[i])
    df['Supertrend'] = supertrend
    
    return rsi.iloc[-1], macd.iloc[-1], signal_line.iloc[-1], df['Supertrend'].iloc[-1], df["Close"].iloc[-1]

def generate_signal():
    df = get_nifty_data()
    rsi, macd, signal_line, supertrend, ltp = calculate_signals(df)
    now = datetime.now(IST).strftime("%d-%b-%Y %H:%M IST")
    strikes = get_option_chain(ltp)
    
    if rsi < 40 and macd > signal_line and ltp > supertrend:
        direction = "CE 📈 (BULLISH)"
        action = "BUY"
        strike = min([s for s in strikes if s > ltp])  
        sl = ltp * 0.995  
        tp = ltp * 1.01   
    elif rsi > 60 and macd < signal_line and ltp < supertrend:
        direction = "PE 📉 (BEARISH)"
        action = "BUY"
        strike = max([s for s in strikes if s < ltp])  
        sl = ltp * 1.005
        tp = ltp * 0.99
    else:
        return
    
    msg = f""" 🚨 <b>NIFTY SIGNAL ALERT</b> 🚨
📅 Time : {now}
💰 Nifty LTP: {ltp}
🎯 Strike : {strike}
📊 Signal : {action} {direction}
📉 RSI : {round(rsi, 2)}
🛑 SL: {round(sl, 2)}
🎯 TP: {round(tp, 2)}
⚠️ Trade at your own risk! """
    send_telegram(msg)
    print(f"Signal sent: {action} {direction}")

if __name__ == "__main__":
    generate_signal()
