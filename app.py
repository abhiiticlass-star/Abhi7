from flask import Flask, jsonify
from flask_cors import CORS

import requests
import time
import json
import os

from datetime import datetime
import pytz

app = Flask(__name__)
CORS(app)

# ==================================
# CONFIG
# ==================================

API_KEY = os.getenv(
    "TWELVE_DATA_API_KEY"
)

ASSETS = {

    "EURUSD": "EUR/USD",

    "GBPUSD": "GBP/USD",

    "USDJPY": "USD/JPY",

    "AUDUSD": "AUD/USD"
}

# ==================================
# CACHE
# ==================================

cache = {}

def get_cache(key):

    if key not in cache:
        return None

    item = cache[key]

    if time.time() > item["expiry"]:
        return None

    return item["value"]


def set_cache(
    key,
    value,
    ttl=60
):

    cache[key] = {

        "value": value,

        "expiry": time.time() + ttl
    }

# ==================================
# HISTORY FILE
# ==================================

HISTORY_FILE = "signals.json"


def load_history():

    try:

        if not os.path.exists(
            HISTORY_FILE
        ):

            return []

        with open(
            HISTORY_FILE,
            "r"
        ) as f:

            data = json.load(f)

        return data.get(
            "history",
            []
        )

    except:

        return []


def save_history(history):

    try:

        with open(
            HISTORY_FILE,
            "w"
        ) as f:

            json.dump(

                {
                    "history": history
                },

                f,

                indent=4
            )

    except:
        pass

# ==================================
# MARKET STATUS
# ==================================

def market_open():

    india = pytz.timezone(
        "Asia/Kolkata"
    )

    now = datetime.now(india)

    # Saturday

    if now.weekday() == 5:
        return False

    # Sunday

    if now.weekday() == 6:
        return False

    return True

# ==================================
# CANDLE FETCHER
# ==================================

def get_candles(
    symbol,
    interval
):

    cache_key = (
        f"{symbol}_{interval}"
    )

    cached = get_cache(
        cache_key
    )

    if cached:
        return cached

    try:

        url = (
            "https://api.twelvedata.com/"
            "time_series"
        )

        params = {

            "symbol": symbol,

            "interval": interval,

            "outputsize": 200,

            "apikey": API_KEY
        }

        r = requests.get(
            url,
            params=params,
            timeout=20
        )

        data = r.json()

        if "values" not in data:
            return None

        candles = []

        for row in reversed(
            data["values"]
        ):

            candles.append({

                "datetime":
                row["datetime"],

                "open":
                float(row["open"]),

                "high":
                float(row["high"]),

                "low":
                float(row["low"]),

                "close":
                float(row["close"])
            })

        set_cache(
            cache_key,
            candles,
            60
        )

        return candles

    except:

        return None
        # ==================================
# EMA
# ==================================

def calculate_ema(
    prices,
    period
):

    if len(prices) < period:

        return prices[-1]

    multiplier = (
        2 / (period + 1)
    )

    ema = (
        sum(prices[:period])
        / period
    )

    for price in prices[period:]:

        ema = (
            (price - ema)
            * multiplier
        ) + ema

    return ema

# ==================================
# RSI
# ==================================

def calculate_rsi(
    prices,
    period=14
):

    if len(prices) < (
        period + 1
    ):
        return 50

    gains = []
    losses = []

    for i in range(
        1,
        len(prices)
    ):

        diff = (
            prices[i]
            - prices[i - 1]
        )

        if diff > 0:

            gains.append(diff)
            losses.append(0)

        else:

            gains.append(0)
            losses.append(
                abs(diff)
            )

    avg_gain = (
        sum(gains[-period:])
        / period
    )

    avg_loss = (
        sum(losses[-period:])
        / period
    )

    if avg_loss == 0:
        return 100

    rs = (
        avg_gain
        / avg_loss
    )

    rsi = (
        100
        - (
            100
            / (1 + rs)
        )
    )

    return rsi

# ==================================
# MACD
# ==================================

def calculate_macd(
    prices
):

    ema12 = calculate_ema(
        prices,
        12
    )

    ema26 = calculate_ema(
        prices,
        26
    )

    return ema12 - ema26

# ==================================
# CANDLE PATTERNS
# ==================================

def bullish_engulfing(
    candles
):

    if len(candles) < 2:
        return False

    prev = candles[-2]
    curr = candles[-1]

    return (

        prev["close"]
        < prev["open"]

        and

        curr["close"]
        > curr["open"]

        and

        curr["open"]
        < prev["close"]

        and

        curr["close"]
        > prev["open"]
    )

# ==================================
# BEARISH ENGULFING
# ==================================

def bearish_engulfing(
    candles
):

    if len(candles) < 2:
        return False

    prev = candles[-2]
    curr = candles[-1]

    return (

        prev["close"]
        > prev["open"]

        and

        curr["close"]
        < curr["open"]

        and

        curr["open"]
        > prev["close"]

        and

        curr["close"]
        < prev["open"]
    )

# ==================================
# HAMMER
# ==================================

def hammer(
    candle
):

    body = abs(

        candle["close"]
        - candle["open"]

    )

    lower_shadow = (

        min(
            candle["open"],
            candle["close"]
        )

        - candle["low"]

    )

    return (

        lower_shadow
        > body * 2
    )

# ==================================
# SHOOTING STAR
# ==================================

def shooting_star(
    candle
):

    body = abs(

        candle["close"]
        - candle["open"]

    )

    upper_shadow = (

        candle["high"]

        -

        max(
            candle["open"],
            candle["close"]
        )

    )

    return (

        upper_shadow
        > body * 2
    )

# ==================================
# DOJI
# ==================================

def doji(
    candle
):

    body = abs(

        candle["close"]

        -

        candle["open"]

    )

    rng = (

        candle["high"]

        -

        candle["low"]

    )

    if rng == 0:
        return False

    return (

        body
        <= rng * 0.1
    )

# ==================================
# TREND ENGINE
# ==================================

def detect_trend(
    closes
):

    ema20 = calculate_ema(
        closes,
        20
    )

    ema50 = calculate_ema(
        closes,
        50
    )

    ema200 = calculate_ema(
        closes,
        200
    )

    if (

        ema20
        > ema50

        and

        ema50
        > ema200

    ):

        return "Bullish"

    if (

        ema20
        < ema50

        and

        ema50
        < ema200

    ):

        return "Bearish"

    return "Neutral"
    # ==================================
# SWING HIGH / LOW DETECTION
# ==================================

def find_swing_highs(candles):

    swings = []

    for i in range(2, len(candles)-2):

        high = candles[i]["high"]

        if (

            high > candles[i-1]["high"]

            and

            high > candles[i-2]["high"]

            and

            high > candles[i+1]["high"]

            and

            high > candles[i+2]["high"]

        ):

            swings.append(high)

    return swings


def find_swing_lows(candles):

    swings = []

    for i in range(2, len(candles)-2):

        low = candles[i]["low"]

        if (

            low < candles[i-1]["low"]

            and

            low < candles[i-2]["low"]

            and

            low < candles[i+1]["low"]

            and

            low < candles[i+2]["low"]

        ):

            swings.append(low)

    return swings

# ==================================
# MULTI TOUCH ZONES
# ==================================

def count_zone_touches(
    candles,
    level,
    tolerance
):

    touches = 0

    for candle in candles:

        if abs(
            candle["high"] - level
        ) <= tolerance:

            touches += 1

        elif abs(
            candle["low"] - level
        ) <= tolerance:

            touches += 1

    return touches

# ==================================
# INSTITUTIONAL SUPPORT RESISTANCE
# ==================================

def get_support_resistance(
    candles
):

    swing_highs = find_swing_highs(
        candles
    )

    swing_lows = find_swing_lows(
        candles
    )

    if len(swing_highs) == 0:

        resistance = max(
            c["high"]
            for c in candles[-50:]
        )

    else:

        resistance = swing_highs[-1]

    if len(swing_lows) == 0:

        support = min(
            c["low"]
            for c in candles[-50:]
        )

    else:

        support = swing_lows[-1]

    tolerance = (
        abs(
            resistance - support
        ) * 0.02
    )

    resistance_strength = (
        count_zone_touches(
            candles[-100:],
            resistance,
            tolerance
        )
    )

    support_strength = (
        count_zone_touches(
            candles[-100:],
            support,
            tolerance
        )
    )

    return {

        "support":
        support,

        "resistance":
        resistance,

        "support_strength":
        support_strength,

        "resistance_strength":
        resistance_strength
    }

# ==================================
# BREAKOUT CONFIRMATION
# ==================================

def breakout_confirmation(
    candles,
    resistance,
    support
):

    last = candles[-1]

    close = last["close"]

    open_price = last["open"]

    body = abs(
        close - open_price
    )

    candle_range = (

        last["high"]

        -

        last["low"]

    )

    if candle_range == 0:
        return None

    body_ratio = (
        body / candle_range
    )

    # Strong Bullish Breakout

    if (

        close > resistance

        and

        body_ratio > 0.60

    ):

        return "UP"

    # Strong Bearish Breakdown

    if (

        close < support

        and

        body_ratio > 0.60

    ):

        return "DOWN"

    return None

# ==================================
# FAKE BREAKOUT FILTER
# ==================================

def fake_breakout_filter(
    candles,
    resistance,
    support
):

    last = candles[-1]

    # Resistance fake break

    if (

        last["high"] > resistance

        and

        last["close"] < resistance

    ):

        return True

    # Support fake break

    if (

        last["low"] < support

        and

        last["close"] > support

    ):

        return True

    return False

# ==================================
# LIQUIDITY REJECTION
# ==================================

def liquidity_rejection(
    candle
):

    body = abs(

        candle["close"]

        -

        candle["open"]

    )

    upper_wick = (

        candle["high"]

        -

        max(
            candle["open"],
            candle["close"]
        )

    )

    lower_wick = (

        min(
            candle["open"],
            candle["close"]
        )

        -

        candle["low"]

    )

    if upper_wick > body * 2:
        return "SELL_REJECTION"

    if lower_wick > body * 2:
        return "BUY_REJECTION"

    return None
    # ==================================
# CONFLUENCE SIGNAL ENGINE
# ==================================

def generate_signal(candles):

    closes = [
        c["close"]
        for c in candles
    ]

    current_price = closes[-1]

    ema20 = calculate_ema(
        closes,
        20
    )

    ema50 = calculate_ema(
        closes,
        50
    )

    ema200 = calculate_ema(
        closes,
        200
    )

    rsi = calculate_rsi(
        closes
    )

    macd = calculate_macd(
        closes
    )

    sr = get_support_resistance(
        candles
    )

    support = sr["support"]

    resistance = sr["resistance"]

    support_strength = sr[
        "support_strength"
    ]

    resistance_strength = sr[
        "resistance_strength"
    ]

    bullish = 0
    bearish = 0

    reasons = []

    # =====================
    # EMA
    # =====================

    if ema20 > ema50 > ema200:

        bullish += 3

        reasons.append(
            "EMA Bullish"
        )

    elif ema20 < ema50 < ema200:

        bearish += 3

        reasons.append(
            "EMA Bearish"
        )

    # =====================
    # RSI
    # =====================

    if rsi > 60:

        bullish += 2

        reasons.append(
            "RSI Strong Buy"
        )

    elif rsi < 40:

        bearish += 2

        reasons.append(
            "RSI Strong Sell"
        )

    # =====================
    # MACD
    # =====================

    if macd > 0:

        bullish += 2

        reasons.append(
            "MACD Positive"
        )

    elif macd < 0:

        bearish += 2

        reasons.append(
            "MACD Negative"
        )

    # =====================
    # CANDLE PATTERNS
    # =====================

    if bullish_engulfing(
        candles
    ):

        bullish += 3

        reasons.append(
            "Bullish Engulfing"
        )

    if bearish_engulfing(
        candles
    ):

        bearish += 3

        reasons.append(
            "Bearish Engulfing"
        )

    if hammer(
        candles[-1]
    ):

        bullish += 1

        reasons.append(
            "Hammer"
        )

    if shooting_star(
        candles[-1]
    ):

        bearish += 1

        reasons.append(
            "Shooting Star"
        )

    # =====================
    # S/R STRENGTH
    # =====================

    if support_strength >= 3:

        bullish += 1

    if resistance_strength >= 3:

        bearish += 1

    # =====================
    # BREAKOUT
    # =====================

    breakout = breakout_confirmation(

        candles,

        resistance,

        support

    )

    if breakout == "UP":

        bullish += 4

        reasons.append(
            "Resistance Breakout"
        )

    elif breakout == "DOWN":

        bearish += 4

        reasons.append(
            "Support Breakdown"
        )

    # =====================
    # FAKE BREAKOUT
    # =====================

    if fake_breakout_filter(

        candles,

        resistance,

        support

    ):

        return {

            "signal": "AVOID",

            "trend":
            detect_trend(
                closes
            ),

            "callPct": 50,

            "putPct": 50,

            "support":
            round(
                support,
                5
            ),

            "resistance":
            round(
                resistance,
                5
            ),

            "confluence":
            "Fake Breakout Detected",

            "reasons":
            [
                "Fake Breakout"
            ]
        }

    # =====================
    # LIQUIDITY
    # =====================

    rejection = liquidity_rejection(

        candles[-1]
    )

    if rejection == "BUY_REJECTION":

        bullish += 2

    elif rejection == "SELL_REJECTION":

        bearish += 2

    # =====================
    # FINAL DECISION
    # =====================

    total = bullish + bearish

    if total == 0:

        call_pct = 50

        put_pct = 50

    else:

        call_pct = round(

            bullish
            /
            total
            *
            100

        )

        put_pct = (
            100
            -
            call_pct
        )

    if bullish >= 8:

        signal = "UP"

    elif bearish >= 8:

        signal = "DOWN"

    else:

        signal = "AVOID"

    return {

        "signal": signal,

        "trend":
        detect_trend(
            closes
        ),

        "callPct":
        call_pct,

        "putPct":
        put_pct,

        "support":
        round(
            support,
            5
        ),

        "resistance":
        round(
            resistance,
            5
        ),

        "rsi":
        round(
            rsi,
            2
        ),

        "macd":
        round(
            macd,
            5
        ),

        "confluence":
        " | ".join(
            reasons[:5]
        ),

        "reasons":
        reasons[:10]
    }
    # ==================================
# HISTORY + SIGNAL TRACKING
# ==================================

pending_signals = []


def add_pending_signal(
    asset,
    tf,
    signal,
    entry_price
):

    pending_signals.append({

        "asset": asset,

        "tf": tf,

        "signal": signal,

        "entry_price": entry_price,

        "created": time.time()
    })


def verify_signals():

    history = load_history()

    completed = []

    for trade in pending_signals:

        wait_time = 60

        interval = "1min"

        if trade["tf"] == "5m":

            wait_time = 300

            interval = "5min"

        if (
            time.time()
            -
            trade["created"]
            <
            wait_time
        ):
            continue

        symbol = ASSETS[
            trade["asset"]
        ]

        candles = get_candles(
            symbol,
            interval
        )

        if not candles:
            continue

        exit_price = candles[-1][
            "close"
        ]

        result = "LOSS"

        if (

            trade["signal"]
            ==
            "UP"

            and

            exit_price
            >
            trade["entry_price"]

        ):

            result = "WIN"

        elif (

            trade["signal"]
            ==
            "DOWN"

            and

            exit_price
            <
            trade["entry_price"]

        ):

            result = "WIN"

        india = pytz.timezone(
            "Asia/Kolkata"
        )

        history.insert(0, {

            "time":
            datetime.now(
                india
            ).strftime(
                "%H:%M:%S"
            ),

            "asset":
            trade["asset"],

            "tf":
            trade["tf"],

            "type":
            trade["signal"],

            "entry":
            round(
                trade["entry_price"],
                5
            ),

            "exit":
            round(
                exit_price,
                5
            ),

            "result":
            result
        })

        completed.append(
            trade
        )

    for trade in completed:

        pending_signals.remove(
            trade
        )

    history = history[:10]

    save_history(
        history
    )

# ==================================
# API ROUTES
# ==================================

@app.route("/")
def home():

    return jsonify({

        "status": "online",

        "engine":
        "ABHI ALGO V10 PRO",

        "version":
        "V10"
    })


@app.route("/api/signals")
def get_signals():

    try:

        verify_signals()

        if not market_open():

            return jsonify({

                "market":
                "closed",

                "signal":
                "MARKET_CLOSED",

                "history":
                load_history()
            })

        response = {

            "market":
            "open",

            "signals": {

                "1m": {},

                "5m": {}
            },

            "metrics": {},

            "history":
            load_history()
        }

        for asset in ASSETS:

            symbol = ASSETS[
                asset
            ]

            # ==================
            # 1 MINUTE
            # ==================

            candles1 = get_candles(
                symbol,
                "1min"
            )

            if candles1:

                result1 = (
                    generate_signal(
                        candles1
                    )
                )

                response[
                    "signals"
                ][
                    "1m"
                ][
                    asset
                ] = result1[
                    "signal"
                ]

                response[
                    "metrics"
                ].setdefault(
                    asset,
                    {}
                )

                response[
                    "metrics"
                ][
                    asset
                ][
                    "1m"
                ] = result1

                if result1[
                    "signal"
                ] in [
                    "UP",
                    "DOWN"
                ]:

                    add_pending_signal(

                        asset,

                        "1m",

                        result1[
                            "signal"
                        ],

                        candles1[-1][
                            "close"
                        ]
                    )

            # ==================
            # 5 MINUTE
            # ==================

            candles5 = get_candles(
                symbol,
                "5min"
            )

            if candles5:

                result5 = (
                    generate_signal(
                        candles5
                    )
                )

                response[
                    "signals"
                ][
                    "5m"
                ][
                    asset
                ] = result5[
                    "signal"
                ]

                response[
                    "metrics"
                ].setdefault(
                    asset,
                    {}
                )

                response[
                    "metrics"
                ][
                    asset
                ][
                    "5m"
                ] = result5

                if result5[
                    "signal"
                ] in [
                    "UP",
                    "DOWN"
                ]:

                    add_pending_signal(

                        asset,

                        "5m",

                        result5[
                            "signal"
                        ],

                        candles5[-1][
                            "close"
                        ]
                    )

        return jsonify(
            response
        )

    except Exception as e:

        return jsonify({

            "market":
            "error",

            "signal":
            "SERVER_ISSUE",

            "message":
            str(e)
        })

# ==================================
# RUN SERVER
# ==================================

if __name__ == "__main__":

    app.run(

        host="0.0.0.0",

        port=int(
            os.environ.get(
                "PORT",
                5000
            )
        )
    )
