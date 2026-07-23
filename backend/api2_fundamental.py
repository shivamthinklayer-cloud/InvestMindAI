import os
import json
import csv
import math
import requests
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"



# ─────────────────────────────────────────
# GEMINI CALL HELPER
# ─────────────────────────────────────────

def call_gemini(prompt: str, max_tokens: int = 1500) -> str:
    """Calls Gemini 1.5 Flash (free tier)."""
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature":     0.2,
            "maxOutputTokens": max_tokens,
        },
    }
    url  = f"{GEMINI_URL}?key={GEMINI_API_KEY}"
    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()


# ─────────────────────────────────────────
# 1. LOAD & PARSE stock_data.csv
# ─────────────────────────────────────────

def load_csv(csv_path: str = "stock_data.csv") -> list:
    """Loads stock_data.csv and returns list of OHLCV dicts."""
    records = []
    try:
        with open(csv_path, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    records.append({
                        "date":   row["Date"],
                        "open":   float(row["Open"]),
                        "high":   float(row["High"]),
                        "low":    float(row["Low"]),
                        "close":  float(row["Close"]),
                        "volume": int(float(row["Volume"])) if row.get("Volume") else 0,
                    })
                except (ValueError, KeyError):
                    continue
        print(f"[Technical] Loaded {len(records)} rows from {csv_path}")
    except FileNotFoundError:
        print(f"[Technical] ❌ {csv_path} not found. Run data_fetch.py first.")
    return records


# ─────────────────────────────────────────
# 2. TECHNICAL INDICATORS (from CSV)
# ─────────────────────────────────────────

def calculate_technicals(records: list) -> dict:
    """
    Calculates all technical indicators from OHLCV data.
    No external library needed — pure Python.
    """
    if not records:
        return {"status": "error", "message": "No data to calculate"}

    closes  = [r["close"]  for r in records]
    highs   = [r["high"]   for r in records]
    lows    = [r["low"]    for r in records]
    volumes = [r["volume"] for r in records]
    dates   = [r["date"]   for r in records]

    # ── Moving Averages ──
    def ma(data, w):
        return round(sum(data[-w:]) / w, 2) if len(data) >= w else None

    # ── EMA ──
    def ema(data, w):
        if len(data) < w:
            return None
        k = 2 / (w + 1)
        ema_val = sum(data[:w]) / w
        for price in data[w:]:
            ema_val = price * k + ema_val * (1 - k)
        return round(ema_val, 2)

    # ── RSI (14) ──
    def calc_rsi(closes, period=14):
        if len(closes) < period + 1:
            return None
        deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        gains  = [d if d > 0 else 0 for d in deltas[-period:]]
        losses = [-d if d < 0 else 0 for d in deltas[-period:]]
        avg_g  = sum(gains) / period
        avg_l  = sum(losses) / period
        if avg_l == 0:
            return 100.0
        rs = avg_g / avg_l
        return round(100 - (100 / (1 + rs)), 2)

    # ── MACD ──
    def calc_macd(closes):
        e12 = ema(closes, 12)
        e26 = ema(closes, 26)
        if e12 is None or e26 is None:
            return None, None, None
        macd_line = round(e12 - e26, 2)
        # Signal line = 9-day EMA of MACD (simplified)
        macd_values = []
        for i in range(26, len(closes)):
            e12_i = ema(closes[:i], 12)
            e26_i = ema(closes[:i], 26)
            if e12_i and e26_i:
                macd_values.append(e12_i - e26_i)
        signal = round(ema(macd_values, 9), 2) if len(macd_values) >= 9 else None
        histogram = round(macd_line - signal, 2) if signal else None
        return macd_line, signal, histogram

    # ── Bollinger Bands (20, 2) ──
    def calc_bollinger(closes, w=20, num_std=2):
        if len(closes) < w:
            return None, None, None
        recent = closes[-w:]
        mid    = sum(recent) / w
        std    = math.sqrt(sum((x - mid) ** 2 for x in recent) / w)
        return round(mid + num_std * std, 2), round(mid, 2), round(mid - num_std * std, 2)

    # ── ATR (14) — Average True Range ──
    def calc_atr(highs, lows, closes, period=14):
        if len(closes) < period + 1:
            return None
        true_ranges = []
        for i in range(1, len(closes)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i-1]),
                abs(lows[i]  - closes[i-1])
            )
            true_ranges.append(tr)
        return round(sum(true_ranges[-period:]) / period, 2)

    # ── Stochastic Oscillator (14) ──
    def calc_stochastic(highs, lows, closes, period=14):
        if len(closes) < period:
            return None, None
        h14 = max(highs[-period:])
        l14 = min(lows[-period:])
        if h14 == l14:
            return 50.0, 50.0
        k = round(((closes[-1] - l14) / (h14 - l14)) * 100, 2)
        # %D = 3-period MA of %K (simplified)
        k_values = []
        for i in range(period, len(closes)):
            h = max(highs[i-period:i])
            l = min(lows[i-period:i])
            if h != l:
                k_values.append(((closes[i] - l) / (h - l)) * 100)
        d = round(sum(k_values[-3:]) / 3, 2) if len(k_values) >= 3 else k
        return k, d

    # ── Support & Resistance ──
    def calc_support_resistance(closes, highs, lows):
        recent_c = closes[-20:]
        recent_h = highs[-20:]
        recent_l = lows[-20:]
        resistance = round(max(recent_h), 2)
        support    = round(min(recent_l), 2)
        return support, resistance

    # ── Volume Analysis ──
    def volume_analysis(volumes, closes):
        avg_vol_20 = int(sum(volumes[-20:]) / min(20, len(volumes)))
        avg_vol_50 = int(sum(volumes[-50:]) / min(50, len(volumes)))
        last_vol   = volumes[-1]
        vol_signal = "HIGH" if last_vol > avg_vol_20 * 1.5 else "LOW" if last_vol < avg_vol_20 * 0.5 else "NORMAL"

        # OBV (On Balance Volume)
        obv = 0
        for i in range(1, len(closes)):
            if closes[i] > closes[i-1]:
                obv += volumes[i]
            elif closes[i] < closes[i-1]:
                obv -= volumes[i]
        return avg_vol_20, avg_vol_50, vol_signal, obv

    # ── Price Returns ──
    def ret(data, days):
        if len(data) > days:
            return round(((data[-1] - data[-days]) / data[-days]) * 100, 2)
        return None

    # ── Yearly Summary ──
    def yearly_summary(records):
        yearly = {}
        for r in records:
            yr = r["date"][:4]
            if yr not in yearly:
                yearly[yr] = {"open": r["open"], "high": r["high"],
                              "low": r["low"],   "close": r["close"],
                              "trading_days": 0}
            yearly[yr]["high"]  = max(yearly[yr]["high"], r["high"])
            yearly[yr]["low"]   = min(yearly[yr]["low"],  r["low"])
            yearly[yr]["close"] = r["close"]
            yearly[yr]["trading_days"] += 1

        yrs = sorted(yearly.keys())
        for i, yr in enumerate(yrs):
            if i > 0:
                prev = yearly[yrs[i-1]]["close"]
                curr = yearly[yr]["close"]
                yearly[yr]["annual_return_%"] = round(((curr - prev) / prev) * 100, 2)
            else:
                yearly[yr]["annual_return_%"] = "N/A"
        return yearly

    # ── Trend Detection ──
    def detect_trend(closes):
        ma50  = ma(closes, 50)
        ma200 = ma(closes, 200)
        price = closes[-1]
        if ma50 and ma200:
            if price > ma50 > ma200:
                return "STRONG UPTREND"
            elif price > ma50 and ma50 < ma200:
                return "WEAK UPTREND"
            elif price < ma50 < ma200:
                return "STRONG DOWNTREND"
            elif price < ma50 and ma50 > ma200:
                return "WEAK DOWNTREND"
        return "SIDEWAYS"

    # ── Golden/Death Cross ──
    def cross_signal(closes):
        ma50  = ma(closes, 50)
        ma200 = ma(closes, 200)
        prev_ma50  = ma(closes[:-5], 50)  # 5 days ago
        prev_ma200 = ma(closes[:-5], 200)
        if ma50 and ma200 and prev_ma50 and prev_ma200:
            if ma50 > ma200 and prev_ma50 <= prev_ma200:
                return "GOLDEN CROSS (Bullish)"
            elif ma50 < ma200 and prev_ma50 >= prev_ma200:
                return "DEATH CROSS (Bearish)"
        if ma50 and ma200:
            return "GOLDEN CROSS active" if ma50 > ma200 else "DEATH CROSS active"
        return "N/A"

    # ── Run all calculations ──
    ma20  = ma(closes, 20)
    ma50  = ma(closes, 50)
    ma200 = ma(closes, 200)
    ema12 = ema(closes, 12)
    ema26 = ema(closes, 26)
    rsi   = calc_rsi(closes)
    macd_line, macd_signal, macd_hist = calc_macd(closes)
    bb_upper, bb_mid, bb_lower = calc_bollinger(closes)
    atr   = calc_atr(highs, lows, closes)
    stoch_k, stoch_d = calc_stochastic(highs, lows, closes)
    support, resistance = calc_support_resistance(closes, highs, lows)
    avg_vol_20, avg_vol_50, vol_signal, obv = volume_analysis(volumes, closes)
    last_252 = closes[-252:] if len(closes) >= 252 else closes
    trend  = detect_trend(closes)
    cross  = cross_signal(closes)

    # ── Signal Interpretation ──
    signals = []
    if rsi:
        if rsi > 70:   signals.append("RSI: OVERBOUGHT (consider selling)")
        elif rsi < 30: signals.append("RSI: OVERSOLD (consider buying)")
        else:          signals.append(f"RSI: NEUTRAL ({rsi})")

    if macd_line and macd_signal:
        if macd_line > macd_signal: signals.append("MACD: BULLISH crossover")
        else:                        signals.append("MACD: BEARISH crossover")

    if bb_upper and bb_lower:
        price = closes[-1]
        if price > bb_upper:   signals.append("Bollinger: Price ABOVE upper band (overbought)")
        elif price < bb_lower: signals.append("Bollinger: Price BELOW lower band (oversold)")
        else:                  signals.append("Bollinger: Price within bands (normal)")

    if ma50 and ma200:
        if ma50 > ma200: signals.append("MA: Golden Cross zone (bullish)")
        else:            signals.append("MA: Death Cross zone (bearish)")

    return {
        "status":        "success",
        "total_records": len(records),
        "date_range":    {"from": dates[0], "to": dates[-1]},

        "price_data": {
            "current_price":   closes[-1],
            "52_week_high":    round(max(last_252), 2),
            "52_week_low":     round(min(last_252), 2),
            "5yr_high":        round(max(closes), 2),
            "5yr_low":         round(min(closes), 2),
            "day_change_%":    ret(closes, 1),
        },

        "moving_averages": {
            "ma_20":  ma20,
            "ma_50":  ma50,
            "ma_200": ma200,
            "ema_12": ema12,
            "ema_26": ema26,
            "price_vs_ma20":  "above" if ma20  and closes[-1] > ma20  else "below",
            "price_vs_ma50":  "above" if ma50  and closes[-1] > ma50  else "below",
            "price_vs_ma200": "above" if ma200 and closes[-1] > ma200 else "below",
        },

        "momentum_indicators": {
            "rsi_14":         rsi,
            "rsi_signal":     "OVERBOUGHT" if rsi and rsi > 70 else "OVERSOLD" if rsi and rsi < 30 else "NEUTRAL",
            "macd_line":      macd_line,
            "macd_signal":    macd_signal,
            "macd_histogram": macd_hist,
            "macd_trend":     "BULLISH" if macd_line and macd_signal and macd_line > macd_signal else "BEARISH",
            "stoch_k":        stoch_k,
            "stoch_d":        stoch_d,
            "stoch_signal":   "OVERBOUGHT" if stoch_k and stoch_k > 80 else "OVERSOLD" if stoch_k and stoch_k < 20 else "NEUTRAL",
        },

        "volatility": {
            "bollinger_upper": bb_upper,
            "bollinger_mid":   bb_mid,
            "bollinger_lower": bb_lower,
            "atr_14":          atr,
            "bb_signal":       "OVERBOUGHT" if bb_upper and closes[-1] > bb_upper else "OVERSOLD" if bb_lower and closes[-1] < bb_lower else "NORMAL",
        },

        "volume_analysis": {
            "last_volume":    volumes[-1],
            "avg_volume_20d": avg_vol_20,
            "avg_volume_50d": avg_vol_50,
            "volume_signal":  vol_signal,
            "obv":            obv,
        },

        "support_resistance": {
            "support_20d":    support,
            "resistance_20d": resistance,
            "current_price":  closes[-1],
        },

        "trend_analysis": {
            "overall_trend":    trend,
            "ma_cross_signal":  cross,
            "golden_death_cross": cross,
        },

        "returns": {
            "1_month_%":  ret(closes, 21),
            "3_month_%":  ret(closes, 63),
            "6_month_%":  ret(closes, 126),
            "1_year_%":   ret(closes, 252),
            "3_year_%":   ret(closes, 756),
            "5_year_%":   ret(closes, 1260),
        },

        "yearly_summary": yearly_summary(records),
        "key_signals":    signals,
    }


# ─────────────────────────────────────────
# 3. FUNDAMENTAL ANALYSIS (Gemini)
# ─────────────────────────────────────────

def run_fundamental_analysis(shared_context: dict, technicals: dict) -> str:
    """
    Uses Gemini to analyze fundamentals + technicals together.
    Returns a detailed analysis report as text.
    """
    stock_name   = shared_context.get("stock_name", "Unknown")
    screener     = shared_context.get("stock_data", {})
    key_ratios   = screener.get("key_ratios", {})
    quarterly    = screener.get("quarterly_results", [])
    annual       = screener.get("annual_pl", [])
    pros         = screener.get("pros", [])
    cons         = screener.get("cons", [])

    # Format quarterly data
    quarterly_text = ""
    for q in quarterly[:4]:
        quarterly_text += f"\n  {q['metric']}: {' | '.join(q['values'][:4])}"

    # Format annual data
    annual_text = ""
    for a in annual[:5]:
        annual_text += f"\n  {a['metric']}: {' | '.join(a['values'][-5:])}"

    prompt = f"""You are a professional stock analyst specializing in Indian markets (NSE/BSE).
Analyze {stock_name} stock comprehensively based on the following data.

═══ FUNDAMENTAL DATA (Screener.in) ═══
Key Ratios:
  PE Ratio        : {key_ratios.get('stock p/e', key_ratios.get('p/e', 'N/A'))}
  PB Ratio        : {key_ratios.get('price to book value', key_ratios.get('p/b', 'N/A'))}
  ROE             : {key_ratios.get('return on equity', key_ratios.get('roe', 'N/A'))}%
  ROCE            : {key_ratios.get('roce', 'N/A')}%
  Debt/Equity     : {key_ratios.get('debt to equity', 'N/A')}
  Dividend Yield  : {key_ratios.get('dividend yield', 'N/A')}%
  EPS             : {key_ratios.get('eps', 'N/A')}
  Market Cap      : {key_ratios.get('market cap', 'N/A')} Cr

Quarterly Results (last 4 quarters): {quarterly_text}
Annual P&L (last 5 years): {annual_text}

Screener Pros: {', '.join(pros) if pros else 'N/A'}
Screener Cons: {', '.join(cons) if cons else 'N/A'}

═══ TECHNICAL DATA (from stock_data.csv) ═══
Current Price    : ₹{technicals['price_data']['current_price']}
52W High / Low   : ₹{technicals['price_data']['52_week_high']} / ₹{technicals['price_data']['52_week_low']}

Moving Averages:
  MA20 / MA50 / MA200 : {technicals['moving_averages']['ma_20']} / {technicals['moving_averages']['ma_50']} / {technicals['moving_averages']['ma_200']}
  Price vs MA50       : {technicals['moving_averages']['price_vs_ma50']}
  Price vs MA200      : {technicals['moving_averages']['price_vs_ma200']}

Momentum:
  RSI (14)    : {technicals['momentum_indicators']['rsi_14']} → {technicals['momentum_indicators']['rsi_signal']}
  MACD        : {technicals['momentum_indicators']['macd_line']} | Signal: {technicals['momentum_indicators']['macd_signal']} → {technicals['momentum_indicators']['macd_trend']}
  Stochastic  : K={technicals['momentum_indicators']['stoch_k']} D={technicals['momentum_indicators']['stoch_d']} → {technicals['momentum_indicators']['stoch_signal']}

Volatility:
  Bollinger Bands : {technicals['volatility']['bollinger_lower']} | {technicals['volatility']['bollinger_mid']} | {technicals['volatility']['bollinger_upper']}
  ATR (14)        : {technicals['volatility']['atr_14']}
  BB Signal       : {technicals['volatility']['bb_signal']}

Volume:
  Last Volume   : {technicals['volume_analysis']['last_volume']:,}
  Avg Vol (20d) : {technicals['volume_analysis']['avg_volume_20d']:,}
  Volume Signal : {technicals['volume_analysis']['volume_signal']}

Trend:
  Overall Trend  : {technicals['trend_analysis']['overall_trend']}
  MA Cross       : {technicals['trend_analysis']['ma_cross_signal']}

Support / Resistance (20d):
  Support    : ₹{technicals['support_resistance']['support_20d']}
  Resistance : ₹{technicals['support_resistance']['resistance_20d']}

Returns:
  1M / 3M / 6M : {technicals['returns']['1_month_%']}% / {technicals['returns']['3_month_%']}% / {technicals['returns']['6_month_%']}%
  1Y / 3Y / 5Y : {technicals['returns']['1_year_%']}% / {technicals['returns']['3_year_%']}% / {technicals['returns']['5_year_%']}%

Key Signals: {', '.join(technicals['key_signals'])}

═══ YOUR ANALYSIS TASK ═══
Write a detailed professional analysis report with these sections:

1. FUNDAMENTAL HEALTH (3-4 sentences on valuation, profitability, debt)
2. TECHNICAL PICTURE (3-4 sentences on trend, momentum, support/resistance)
3. STRENGTHS (2-3 bullet points)
4. WEAKNESSES / RISKS (2-3 bullet points)
5. OVERALL ASSESSMENT (2-3 sentences — is the stock fundamentally strong? technically weak/strong?)
6. SCORES:
   - Fundamental Score: X/10
   - Technical Score: X/10
   - Combined Score: X/10

Be specific, use the numbers provided, and write like a professional analyst report."""

    return call_gemini(prompt, max_tokens=1500)


# ─────────────────────────────────────────
# 4. MAIN FUNCTION
# ─────────────────────────────────────────

def run_data_analysis(shared_context: dict, csv_path: str = "stock_data.csv") -> dict:
    """
    Main entry point for API 2.
    Reads stock_data.csv → calculates all technicals → Gemini analysis.
    """
    stock_name = shared_context.get("stock_name", "Unknown Stock")
    print(f"\n[API2] Starting Data + Fundamental Analysis for {stock_name}...")

    # Step 1: Load CSV
    records = load_csv(csv_path)
    if not records:
        return {"status": "error", "message": f"Could not load {csv_path}"}

    # Step 2: Calculate all technicals
    print(f"[API2] Calculating technical indicators from {len(records)} days of data...")
    technicals = calculate_technicals(records)

    if technicals.get("status") == "error":
        return {"status": "error", "message": technicals["message"]}

    # Step 3: Gemini fundamental + technical analysis
    print(f"[API2] Running Gemini analysis...")
    analysis_report = "Gemini API key not set — skipping AI analysis."
    if GEMINI_API_KEY:
        try:
            analysis_report = run_fundamental_analysis(shared_context, technicals)
        except Exception as e:
            analysis_report = f"Gemini analysis failed: {str(e)}"
    else:
        print("[API2] ⚠️  GEMINI_API_KEY not set in .env — skipping AI report")

    result = {
        "status":          "success",
        "api":             "API2 - Data & Fundamental Analysis",
        "stock":           stock_name,
        "csv_used":        csv_path,
        "technicals":      technicals,
        "analysis_report": analysis_report,
    }

    print(f"\n[API2] ✅ Done!")
    print(f"  Trend        : {technicals['trend_analysis']['overall_trend']}")
    print(f"  RSI          : {technicals['momentum_indicators']['rsi_14']} ({technicals['momentum_indicators']['rsi_signal']})")
    print(f"  MACD         : {technicals['momentum_indicators']['macd_trend']}")
    print(f"  MA Cross     : {technicals['trend_analysis']['ma_cross_signal']}")
    print(f"  1Y Return    : {technicals['returns']['1_year_%']}%")
    print(f"  5Y Return    : {technicals['returns']['5_year_%']}%")
    print(f"  Key Signals  : {', '.join(technicals['key_signals'])}")

    return result


# ─────────────────────────────────────────
# TEST
# ─────────────────────────────────────────

if __name__ == "__main__":
    try:
        with open("test_output.json", "r") as f:
            shared_context = json.load(f)
        print("✅ Loaded test_output.json")
    except FileNotFoundError:
        print("❌ test_output.json not found. Run data_fetch.py first!")
        exit(1)

    result = run_data_analysis(shared_context, csv_path="stock_data.csv")

    with open("api2_output.json", "w") as f:
        json.dump(result, f, indent=2)

    print("\n✅ Saved to api2_output.json")
    if result.get("analysis_report"):
        print("\n─── AI ANALYSIS REPORT ───")
        print(result["analysis_report"])