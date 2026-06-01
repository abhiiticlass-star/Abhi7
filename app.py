from flask import Flask, jsonify
from flask_cors import CORS

import requests
import os
import time
from datetime import datetime
import pytz

app = Flask(__name__)
CORS(app)

# ==========================
# CONFIG
# ==========================

API_KEY = os.getenv("TWELVE_DATA_API_KEY")

ASSETS = {
    "EURUSD": "EUR/USD",
    "GBPUSD": "GBP/USD",
    "USDJPY": "USD/JPY",
    "AUDUSD": "AUD/USD"
}

# ==========================
# CACHE
# ==========================

cache = {}

def get_cache(key):

    if key not in cache:
        return None

    item = cache[key]

    if time.time() > item["expiry"]:
        return None

    return item["value"]


def set_cache(key, value, ttl=60):

    cache[key] = {
        "value": value,
        "expiry": time.time() + ttl
    }

# ==========================
# MARKET STATUS
# ==========================

def market_open():

    india = pytz.timezone("Asia/Kolkata")

    now = datetime.now(india)

    if now.weekday() == 5:
        return False

    if now.weekday() == 6:
        return False

    return True

# ==========================
# TWELVE DATA FETCHER
# ==========================

def get_candles(symbol, interval):

    cache_key = f"{symbol}_{interval}"

    cached = get_cache(cache_key)

    if cached:
        return cached

    url = "https://api.twelvedata.com/time_series"

    params = {
        "symbol": symbol,
        "interval": interval,
        "outputsize": 200,
        "apikey": API_KEY,
        "format": "JSON"
    }

    try:

        response = requests.get(
            url,
            params=params,
            timeout=20
        )

        data = response.json()

        if "values" not in data:
            return None

        candles = []

        for row in reversed(data["values"]):

            candles.append({

                "datetime": row["datetime"],

                "open": float(row["open"]),

                "high": float(row["high"]),

                "low": float(row["low"]),

                "close": float(row["close"])

            })

        set_cache(
            cache_key,
            candles,
            ttl=60
        )

        return candles

    except:
        return None
    # ==========================
# INDICATORS
# ==========================

def calculate_ema(prices, period):

    if len(prices) < period:
        return prices[-1]

    multiplier = 2 / (period + 1)

    ema = sum(prices[:period]) / period

    for price in prices[period:]:

        ema = (
            (price - ema) * multiplier
        ) + ema

    return ema


def calculate_rsi(prices, period=14):

    if len(prices) < period + 1:
        return 50

    gains = []
    losses = []

    for i in range(1, len(prices)):

        change = prices[i] - prices[i - 1]

        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))

    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period

    if avg_loss == 0:
        return 100

    rs = avg_gain / avg_loss

    return 100 - (100 / (1 + rs))


def calculate_macd(prices):

    ema12 = calculate_ema(prices, 12)

    ema26 = calculate_ema(prices, 26)

    return ema12 - ema26

# ==========================
# CANDLE PATTERNS
# ==========================

def bullish_engulfing(candles):

    if len(candles) < 2:
        return False

    prev = candles[-2]
    curr = candles[-1]

    return (
        prev["close"] < prev["open"]
        and curr["close"] > curr["open"]
        and curr["open"] < prev["close"]
        and curr["close"] > prev["open"]
    )


def bearish_engulfing(candles):

    if len(candles) < 2:
        return False

    prev = candles[-2]
    curr = candles[-1]

    return (
        prev["close"] > prev["open"]
        and curr["close"] < curr["open"]
        and curr["open"] > prev["close"]
        and curr["close"] < prev["open"]
    )


def hammer(candle):

    body = abs(
        candle["close"] - candle["open"]
    )

    lower_shadow = min(
        candle["open"],
        candle["close"]
    ) - candle["low"]

    return lower_shadow > body * 2


def shooting_star(candle):

    body = abs(
        candle["close"] - candle["open"]
    )

    upper_shadow = candle["high"] - max(
        candle["open"],
        candle["close"]
    )

    return upper_shadow > body * 2


def doji(candle):

    body = abs(
        candle["close"] - candle["open"]
    )

    full_range = (
        candle["high"] - candle["low"]
    )

    if full_range == 0:
        return False

    return body <= full_range * 0.1
  # ==========================
# SUPPORT / RESISTANCE
# ==========================

def get_support_resistance(candles):

    recent = candles[-50:]

    highs = [c["high"] for c in recent]
    lows = [c["low"] for c in recent]

    support = min(lows)
    resistance = max(highs)

    return support, resistance

# ==========================
# BREAKOUT DETECTION
# ==========================

def breakout_signal(price, support, resistance):

    if price > resistance:
        return "UP"

    if price < support:
        return "DOWN"

    return None

# ==========================
# TREND ENGINE
# ==========================

def detect_trend(closes):

    ema20 = calculate_ema(closes, 20)
    ema50 = calculate_ema(closes, 50)
    ema200 = calculate_ema(closes, 200)

    if ema20 > ema50 > ema200:
        return "Bullish"

    if ema20 < ema50 < ema200:
        return "Bearish"

    return "Neutral"

# ==========================
# SIGNAL ENGINE
# ==========================

def generate_signal(candles):

    closes = [c["close"] for c in candles]

    current_price = closes[-1]

    ema20 = calculate_ema(closes, 20)
    ema50 = calculate_ema(closes, 50)
    ema200 = calculate_ema(closes, 200)

    rsi = calculate_rsi(closes)

    macd = calculate_macd(closes)

    support, resistance = get_support_resistance(
        candles
    )

    breakout = breakout_signal(
        current_price,
        support,
        resistance
    )

    bullish_score = 0
    bearish_score = 0

    reasons = []

    # EMA Trend

    if ema20 > ema50 > ema200:

        bullish_score += 2

        reasons.append(
            "EMA Bullish Trend"
        )

    if ema20 < ema50 < ema200:

        bearish_score += 2

        reasons.append(
            "EMA Bearish Trend"
        )

    # RSI

    if rsi > 55:

        bullish_score += 1

        reasons.append(
            "RSI Bullish"
        )

    if rsi < 45:

        bearish_score += 1

        reasons.append(
            "RSI Bearish"
        )

    # MACD

    if macd > 0:

        bullish_score += 1

        reasons.append(
            "MACD Positive"
        )

    if macd < 0:

        bearish_score += 1

        reasons.append(
            "MACD Negative"
        )

    # Candlestick Patterns

    if bullish_engulfing(candles):

        bullish_score += 2

        reasons.append(
            "Bullish Engulfing"
        )

    if bearish_engulfing(candles):

        bearish_score += 2

        reasons.append(
            "Bearish Engulfing"
        )

    if hammer(candles[-1]):

        bullish_score += 1

        reasons.append(
            "Hammer Pattern"
        )

    if shooting_star(candles[-1]):

        bearish_score += 1

        reasons.append(
            "Shooting Star"
        )

    # Breakout

    if breakout == "UP":

        bullish_score += 2

        reasons.append(
            "Resistance Breakout"
        )

    if breakout == "DOWN":

        bearish_score += 2

        reasons.append(
            "Support Breakdown"
        )

    # Final Signal

    if bullish_score >= 5:

        signal = "UP"

    elif bearish_score >= 5:

        signal = "DOWN"

    else:

        signal = "AVOID"

    total = bullish_score + bearish_score

    if total == 0:

        call_pct = 50
        put_pct = 50

    else:

        call_pct = round(
            bullish_score / total * 100
        )

        put_pct = 100 - call_pct

    trend = detect_trend(closes)

    return {

        "signal": signal,

        "trend": trend,

        "callPct": call_pct,

        "putPct": put_pct,

        "support": round(
            support, 5
        ),

        "resistance": round(
            resistance, 5
        ),

        "rsi": round(
            rsi, 2
        ),

        "macd": round(
            macd, 5
        ),

        "reasons": reasons[:5]
}
  # ==========================
# HISTORY
# ==========================

signal_history = []

def add_history(asset, tf, signal):

    now = datetime.now(
        pytz.timezone("Asia/Kolkata")
    )

    signal_history.insert(0, {

        "time": now.strftime(
            "%H:%M:%S"
        ),

        "asset": asset,

        "tf": tf,

        "type": signal,

        "result": "PENDING"

    })

    if len(signal_history) > 10:

        signal_history.pop()

# ==========================
# API
# ==========================

@app.route("/")
def home():

    return jsonify({
        "status": "online",
        "engine": "ABHI ALGO V10 PRO"
    })

@app.route("/api/signals")
def get_signals():

    try:

        if not market_open():

            return jsonify({

                "market": "closed",

                "signal": "MARKET_CLOSED",

                "history": signal_history

            })

        response = {

            "market": "open",

            "signals": {
                "1m": {},
                "5m": {}
            },

            "metrics": {},

            "history": signal_history

        }

        for asset, symbol in ASSETS.items():

            # 1 MINUTE

            candles1 = get_candles(
                symbol,
                "1min"
            )

            if candles1:

                result1 = generate_signal(
                    candles1
                )

                response["signals"]["1m"][asset] = \
                    result1["signal"]

                response["metrics"].setdefault(
                    asset, {}
                )

                response["metrics"][asset]["1m"] = \
                    result1

            # 5 MINUTE

            candles5 = get_candles(
                symbol,
                "5min"
            )

            if candles5:

                result5 = generate_signal(
                    candles5
                )

                response["signals"]["5m"][asset] = \
                    result5["signal"]

                response["metrics"].setdefault(
                    asset, {}
                )

                response["metrics"][asset]["5m"] = \
                    result5

        return jsonify(response)

    except Exception as e:

        return jsonify({

            "market": "error",

            "signal": "SERVER_ISSUE",

            "message": str(e)

        })

# ==========================
# START SERVER
# ==========================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000
  )
