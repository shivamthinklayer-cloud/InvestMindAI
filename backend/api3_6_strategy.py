import os
import json
import time
import requests
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_URL     = "https://openrouter.ai/api/v1/chat/completions"

# ── Verified free models on OpenRouter (March 2026) ──
MODELS = {
    "conservative": "google/gemini-2.5-flash-lite",
    "growth":       "google/gemini-2.5-flash-lite",
    "emotional":    "google/gemini-2.5-flash-lite",
    "value":        "google/gemini-2.5-flash-lite",
    "judge":        "google/gemini-2.5-flash-lite",
}

# ── Fallback — OpenRouter auto-picks any working free model ──
FALLBACK_MODEL = "openrouter/auto"


# ─────────────────────────────────────────
# OPENROUTER CALL HELPER
# ─────────────────────────────────────────

def call_openrouter(model: str, system_prompt: str, user_prompt: str, max_tokens: int = 1000) -> str:
    """
    Calls OpenRouter API.
    Auto-retries on rate limit.
    Falls back to FALLBACK_MODEL if primary model fails.
    """
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type":  "application/json",
        "HTTP-Referer":  "https://stock-analyzer.app",
        "X-Title":       "Stock Analyzer",
    }
    payload = {
        "model":       model,
        "max_tokens":  max_tokens,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
    }

    for attempt in range(3):
        try:
            resp = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=90)

            # Rate limit → wait and retry
            if resp.status_code == 429:
                wait = 20 * (attempt + 1)
                print(f"    [OpenRouter] Rate limited. Waiting {wait}s (attempt {attempt+1}/3)...")
                time.sleep(wait)
                continue

            # Model not found → switch to fallback immediately
            if resp.status_code == 404:
                print(f"    [OpenRouter] Model '{model}' not found. Switching to fallback...")
                payload["model"] = FALLBACK_MODEL
                resp = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=90)

            resp.raise_for_status()

            content = resp.json()["choices"][0]["message"]["content"].strip()

            # Clean DeepSeek R1 thinking tags
            if "<think>" in content:
                content = content.split("</think>")[-1].strip()

            return content

        except requests.exceptions.Timeout:
            print(f"    [OpenRouter] Timeout on attempt {attempt+1}. Retrying...")
            time.sleep(10)
            continue

        except Exception as e:
            if attempt == 2:
                # Last attempt — try fallback model
                print(f"    [OpenRouter] Trying fallback model: {FALLBACK_MODEL}")
                try:
                    payload["model"] = FALLBACK_MODEL
                    resp = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=90)
                    resp.raise_for_status()
                    content = resp.json()["choices"][0]["message"]["content"].strip()
                    if "<think>" in content:
                        content = content.split("</think>")[-1].strip()
                    return content
                except Exception as fe:
                    raise Exception(f"Primary failed: {e} | Fallback failed: {fe}")
            time.sleep(10)

    raise Exception(f"OpenRouter failed after 3 retries for model: {model}")


# ─────────────────────────────────────────
# PARSE JSON FROM MODEL RESPONSE
# ─────────────────────────────────────────

def parse_json_response(raw: str) -> dict:
    """Safely extracts JSON from model response."""
    # Remove markdown code blocks
    if "```" in raw:
        parts = raw.split("```")
        for part in parts:
            if part.startswith("json"):
                raw = part[4:].strip()
                break
            elif "{" in part:
                raw = part.strip()
                break

    # Find JSON object
    start = raw.find("{")
    end   = raw.rfind("}") + 1
    if start != -1 and end > start:
        raw = raw[start:end]

    return json.loads(raw)


# ─────────────────────────────────────────
# BUILD SHARED CONTEXT STRING
# ─────────────────────────────────────────

def build_context_string(shared_context: dict, api2_output: dict) -> str:
    """Builds compact context string passed to all 4 strategy APIs."""

    stock_name = shared_context.get("stock_name", "Unknown")
    screener   = shared_context.get("stock_data", {})
    ratios     = screener.get("key_ratios", {})
    pros       = screener.get("pros", [])
    cons       = screener.get("cons", [])

    tech       = api2_output.get("technicals", {})
    price      = tech.get("price_data", {})
    ma         = tech.get("moving_averages", {})
    momentum   = tech.get("momentum_indicators", {})
    volatility = tech.get("volatility", {})
    volume     = tech.get("volume_analysis", {})
    trend      = tech.get("trend_analysis", {})
    returns    = tech.get("returns", {})
    sr         = tech.get("support_resistance", {})
    signals    = tech.get("key_signals", [])
    sentiment  = shared_context.get("_sentiment", {})

    return f"""
STOCK: {stock_name}

── FUNDAMENTALS (Screener.in) ──
PE Ratio       : {ratios.get('stock p/e', ratios.get('p/e', 'N/A'))}
PB Ratio       : {ratios.get('price to book value', ratios.get('p/b', 'N/A'))}
ROE            : {ratios.get('return on equity', ratios.get('roe', 'N/A'))}%
ROCE           : {ratios.get('roce', 'N/A')}%
Debt/Equity    : {ratios.get('debt to equity', 'N/A')}
Dividend Yield : {ratios.get('dividend yield', 'N/A')}%
Market Cap     : {ratios.get('market cap', 'N/A')} Cr
Pros           : {', '.join(pros[:3]) if pros else 'N/A'}
Cons           : {', '.join(cons[:3]) if cons else 'N/A'}

── TECHNICALS (stock_data.csv) ──
Current Price  : ₹{price.get('current_price', 'N/A')}
52W High/Low   : ₹{price.get('52_week_high', 'N/A')} / ₹{price.get('52_week_low', 'N/A')}
MA20/50/200    : {ma.get('ma_20')} / {ma.get('ma_50')} / {ma.get('ma_200')}
vs MA50/200    : {ma.get('price_vs_ma50')} / {ma.get('price_vs_ma200')}
RSI (14)       : {momentum.get('rsi_14')} → {momentum.get('rsi_signal')}
MACD           : {momentum.get('macd_line')} | Signal: {momentum.get('macd_signal')} → {momentum.get('macd_trend')}
Stochastic     : K={momentum.get('stoch_k')} D={momentum.get('stoch_d')} → {momentum.get('stoch_signal')}
Bollinger      : {volatility.get('bollinger_lower')} | {volatility.get('bollinger_mid')} | {volatility.get('bollinger_upper')}
ATR (14)       : {volatility.get('atr_14')}
Volume Signal  : {volume.get('volume_signal')}
Trend          : {trend.get('overall_trend')}
MA Cross       : {trend.get('ma_cross_signal')}
Support/Resist : ₹{sr.get('support_20d')} / ₹{sr.get('resistance_20d')}

── RETURNS ──
1M / 3M / 6M  : {returns.get('1_month_%')}% / {returns.get('3_month_%')}% / {returns.get('6_month_%')}%
1Y / 3Y / 5Y  : {returns.get('1_year_%')}% / {returns.get('3_year_%')}% / {returns.get('5_year_%')}%

── NEWS SENTIMENT ──
Score          : {sentiment.get('overall', {}).get('overall_score', 'N/A')}/10
Sentiment      : {sentiment.get('overall', {}).get('overall_sentiment', 'N/A')}
Summary        : {str(sentiment.get('overall', {}).get('summary', 'N/A'))[:200]}

── KEY SIGNALS ──
{chr(10).join('• ' + s for s in signals)}
""".strip()


# ─────────────────────────────────────────
# API 3 — CONSERVATIVE STRATEGY
# ─────────────────────────────────────────

def run_conservative(context_str: str, stock_name: str, user_option: str) -> dict:
    system_prompt = """You are a conservative investment analyst for Indian stock markets.
Evaluate stocks for CONSERVATIVE investors who prioritize:
- Capital safety over high returns
- Low debt, stable dividends
- Strong consistent fundamentals
- 5-10 year long-term horizon
- Low volatility stocks

Respond ONLY in this exact JSON format, no other text:
{
  "strategy": "CONSERVATIVE",
  "recommendation": "<STRONG BUY | BUY | HOLD | SELL | STRONG SELL>",
  "confidence": <1-10>,
  "reasoning": "<3-4 sentences from conservative perspective>",
  "key_factors": ["<factor1>", "<factor2>", "<factor3>"],
  "risk_level": "<LOW | MEDIUM | HIGH>",
  "suggested_action": "<specific action>",
  "target_price": "<price or range in INR>",
  "stop_loss": "<stop loss price in INR>"
}"""

    user_prompt = f"""Analyze for a CONSERVATIVE investor.
User situation: {user_option}

{context_str}

Return JSON only."""

    try:
        raw    = call_openrouter(MODELS["conservative"], system_prompt, user_prompt)
        result = parse_json_response(raw)
        return {"status": "success", **result}
    except Exception as e:
        return {"status": "error", "strategy": "CONSERVATIVE", "message": str(e)}


# ─────────────────────────────────────────
# API 4 — GROWTH STRATEGY
# ─────────────────────────────────────────

def run_growth(context_str: str, stock_name: str, user_option: str) -> dict:
    system_prompt = """You are a growth investment analyst for Indian stock markets.
Evaluate stocks for GROWTH investors who prioritize:
- Revenue and earnings growth rate (YoY)
- Market share and industry expansion
- Future earnings potential
- 3-5 year horizon
- Willing to pay premium PE for strong growth

Respond ONLY in this exact JSON format, no other text:
{
  "strategy": "GROWTH",
  "recommendation": "<STRONG BUY | BUY | HOLD | SELL | STRONG SELL>",
  "confidence": <1-10>,
  "reasoning": "<3-4 sentences from growth perspective>",
  "key_factors": ["<factor1>", "<factor2>", "<factor3>"],
  "growth_outlook": "<BULLISH | NEUTRAL | BEARISH>",
  "suggested_action": "<specific action>",
  "target_price": "<price or range in INR>",
  "time_horizon": "<suggested holding period>"
}"""

    user_prompt = f"""Analyze for a GROWTH investor.
User situation: {user_option}

{context_str}

Return JSON only."""

    try:
        raw    = call_openrouter(MODELS["growth"], system_prompt, user_prompt)
        result = parse_json_response(raw)
        return {"status": "success", **result}
    except Exception as e:
        return {"status": "error", "strategy": "GROWTH", "message": str(e)}


# ─────────────────────────────────────────
# API 5 — EMOTIONAL / MOMENTUM STRATEGY
# ─────────────────────────────────────────

def run_emotional(context_str: str, stock_name: str, user_option: str) -> dict:
    system_prompt = """You are a momentum and sentiment trading analyst for Indian stock markets.
Evaluate stocks for MOMENTUM traders who prioritize:
- News sentiment and public buzz
- RSI, MACD, Stochastic signals
- Recent price momentum (1M, 3M returns)
- Volume spikes and breakouts
- Short-term market psychology (weeks to months)

Respond ONLY in this exact JSON format, no other text:
{
  "strategy": "EMOTIONAL_MOMENTUM",
  "recommendation": "<STRONG BUY | BUY | HOLD | SELL | STRONG SELL>",
  "confidence": <1-10>,
  "reasoning": "<3-4 sentences from momentum perspective>",
  "key_factors": ["<factor1>", "<factor2>", "<factor3>"],
  "momentum_signal": "<BULLISH | NEUTRAL | BEARISH>",
  "sentiment_impact": "<POSITIVE | NEUTRAL | NEGATIVE>",
  "suggested_action": "<specific short-term action>",
  "entry_point": "<price in INR>",
  "exit_point": "<price in INR>",
  "stop_loss": "<price in INR>"
}"""

    user_prompt = f"""Analyze for a MOMENTUM/EMOTIONAL trader.
User situation: {user_option}

{context_str}

Return JSON only."""

    try:
        raw    = call_openrouter(MODELS["emotional"], system_prompt, user_prompt)
        result = parse_json_response(raw)
        return {"status": "success", **result}
    except Exception as e:
        return {"status": "error", "strategy": "EMOTIONAL", "message": str(e)}


# ─────────────────────────────────────────
# API 6 — VALUE STRATEGY
# ─────────────────────────────────────────

def run_value(context_str: str, stock_name: str, user_option: str) -> dict:
    system_prompt = """You are a value investment analyst inspired by Warren Buffett and Benjamin Graham.
Evaluate stocks for VALUE investors who prioritize:
- Is the stock trading below intrinsic value?
- PE, PB ratios vs industry averages
- Strong competitive moat
- Consistent multi-year profitability
- Margin of safety before buying
- 5-10 year patient holding

Respond ONLY in this exact JSON format, no other text:
{
  "strategy": "VALUE",
  "recommendation": "<STRONG BUY | BUY | HOLD | SELL | STRONG SELL>",
  "confidence": <1-10>,
  "reasoning": "<3-4 sentences from value perspective>",
  "key_factors": ["<factor1>", "<factor2>", "<factor3>"],
  "valuation": "<UNDERVALUED | FAIRLY VALUED | OVERVALUED>",
  "margin_of_safety": "<HIGH | MEDIUM | LOW | NONE>",
  "suggested_action": "<specific action>",
  "intrinsic_value_estimate": "<estimated fair value range in INR>",
  "buy_zone": "<price range to accumulate in INR>"
}"""

    user_prompt = f"""Analyze for a VALUE investor.
User situation: {user_option}

{context_str}

Return JSON only."""

    try:
        raw    = call_openrouter(MODELS["value"], system_prompt, user_prompt)
        result = parse_json_response(raw)
        return {"status": "success", **result}
    except Exception as e:
        return {"status": "error", "strategy": "VALUE", "message": str(e)}


# ─────────────────────────────────────────
# MAIN FUNCTION — Run All 4 Strategies
# ─────────────────────────────────────────

def run_all_strategies(shared_context: dict, api2_output: dict, user_option: str = "Want to buy") -> dict:
    """
    Main entry point for API 3-6.
    user_option: "Want to buy" | "Already bought" | "Want to sell"
    """
    stock_name = shared_context.get("stock_name", "Unknown Stock")

    print(f"\n[API3-6] Running 4 Strategy Analyses for {stock_name}...")
    print(f"  User Option: {user_option}")

    if not OPENROUTER_API_KEY:
        return {"status": "error", "message": "OPENROUTER_API_KEY not set in .env file"}

    context_str = build_context_string(shared_context, api2_output)
    results     = {}

    # ── API 3: Conservative ──
    print(f"\n  [3/6] Running CONSERVATIVE strategy ({MODELS['conservative']})...")
    results["conservative"] = run_conservative(context_str, stock_name, user_option)
    print(f"    → {results['conservative'].get('recommendation', 'ERROR')} | Confidence: {results['conservative'].get('confidence', '?')}/10")
    time.sleep(3)

    # ── API 4: Growth ──
    print(f"  [4/6] Running GROWTH strategy ({MODELS['growth']})...")
    results["growth"] = run_growth(context_str, stock_name, user_option)
    print(f"    → {results['growth'].get('recommendation', 'ERROR')} | Confidence: {results['growth'].get('confidence', '?')}/10")
    time.sleep(3)

    # ── API 5: Emotional/Momentum ──
    print(f"  [5/6] Running EMOTIONAL/MOMENTUM strategy ({MODELS['emotional']})...")
    results["emotional"] = run_emotional(context_str, stock_name, user_option)
    print(f"    → {results['emotional'].get('recommendation', 'ERROR')} | Confidence: {results['emotional'].get('confidence', '?')}/10")
    time.sleep(3)

    # ── API 6: Value ──
    print(f"  [6/6] Running VALUE strategy ({MODELS['value']})...")
    results["value"] = run_value(context_str, stock_name, user_option)
    print(f"    → {results['value'].get('recommendation', 'ERROR')} | Confidence: {results['value'].get('confidence', '?')}/10")

    # ── Summary ──
    recommendations = {
        k: v.get("recommendation", "N/A")
        for k, v in results.items()
        if v.get("status") == "success"
    }

    final = {
        "status":      "success",
        "api":         "API3-6 - Strategy Analysis",
        "stock":       stock_name,
        "user_option": user_option,
        "strategies":  results,
        "summary": {
            "conservative": recommendations.get("conservative", "N/A"),
            "growth":       recommendations.get("growth",       "N/A"),
            "emotional":    recommendations.get("emotional",    "N/A"),
            "value":        recommendations.get("value",        "N/A"),
        },
    }

    print(f"\n[API3-6] ✅ All strategies done!")
    print(f"  Conservative : {recommendations.get('conservative', 'N/A')}")
    print(f"  Growth       : {recommendations.get('growth',       'N/A')}")
    print(f"  Emotional    : {recommendations.get('emotional',    'N/A')}")
    print(f"  Value        : {recommendations.get('value',        'N/A')}")

    return final


# ─────────────────────────────────────────
# TEST
# ─────────────────────────────────────────

if __name__ == "__main__":
    # Load all previous outputs
    try:
        with open("test_output.json", "r") as f:
            shared_context = json.load(f)
        print("✅ Loaded test_output.json")
    except FileNotFoundError:
        print("❌ test_output.json not found. Run data_fetch.py first!")
        exit(1)

    try:
        with open("api2_output.json", "r") as f:
            api2_output = json.load(f)
        print("✅ Loaded api2_output.json")
    except FileNotFoundError:
        print("❌ api2_output.json not found. Run api2_fundamental.py first!")
        exit(1)

    try:
        with open("api1_output.json", "r") as f:
            shared_context["_sentiment"] = json.load(f)
        print("✅ Loaded api1_output.json")
    except FileNotFoundError:
        print("⚠️  api1_output.json not found — sentiment will show N/A")

    result = run_all_strategies(
        shared_context,
        api2_output,
        user_option="Want to buy"
    )

    with open("api3_6_output.json", "w") as f:
        json.dump(result, f, indent=2)

    print("\n✅ Saved to api3_6_output.json")