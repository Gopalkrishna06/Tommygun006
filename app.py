import requests
import yfinance as yf
import os
import pytz
from datetime import datetime

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

def calculate_signals(df):
    close = df["Close"].squeeze()
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    ema12 = close.ewm(span=12).mean()
    ema26 = close.ewm(span=26).mean()
    macd = ema12 - ema26
    signal_line = macd.ewm(span=9).mean()
    
    hl2 = (df["High"] + df["Low"]) / 2
    atr = (df["High"] - df["Low"]).rolling(14).mean()
    upper = hl2 + (2 * atr)
    lower = hl2 - (2 * atr)
    supertrend = []
    for i in range(len(df)):
        if i < 14:  
            supertrend.append(None)
            continue
        if close.iloc[i-1] <= upper.iloc[i-1]:
            supertrend.append(upper.iloc[i])
        else:
            supertrend.append(lower.iloc[i])
    df['Supertrend'] = supertrend
    
    rsi_val = float(rsi.iloc[-1])
    macd_val = float(macd.iloc[-1])
    signal_val = float(signal_line.iloc[-1])
    ltp_val = float(close.iloc[-1])
    supertrend_val = df['Supertrend'].iloc[-1]
    
    return rsi_val, macd_val, signal_val, ltp_val, supertrend_val

def generate_signal():
    df = get_nifty_data()
    if len(df) < 15: return  
    rsi, macd, signal_line, ltp, supertrend = calculate_signals(df)
    if supertrend is None: return  
    
    strike = round(ltp / 50) * 50
    now = datetime.now(IST).strftime("%d-%b-%Y %H:%M IST")
    
    if rsi < 40 and macd > signal_line and ltp > supertrend:
        direction = "CE 📈 (BULLISH)"
        action = "BUY"
        sl = ltp * 0.995  
        tp = ltp * 1.01   
    elif rsi > 60 and macd < signal_line and ltp < supertrend:
        direction = "PE 📉 (BEARISH)"
        action = "BUY"
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
