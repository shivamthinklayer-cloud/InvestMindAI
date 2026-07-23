import os
import json
import time
import requests
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_URL     = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL   = "deepseek-r1-distill-llama-70b"  # Best free reasoning model on Groq


# ─────────────────────────────────────────
# GROQ CALL HELPER
# ─────────────────────────────────────────

def call_groq(system_prompt: str, user_prompt: str, max_tokens: int = 2000) -> str:
    """Calls Groq API with retry on rate limit."""
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type":  "application/json",
    }
    payload = {
        "model":       GROQ_MODEL,
        "max_tokens":  max_tokens,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
    }

    for attempt in range(3):
        try:
            resp = requests.post(GROQ_URL, headers=headers, json=payload, timeout=60)
            if resp.status_code == 429:
                wait = 20 * (attempt + 1)
                print(f"  [Groq] Rate limited. Waiting {wait}s (attempt {attempt+1}/3)...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"].strip()
            # Clean thinking tags if present
            if "<think>" in content:
                content = content.split("</think>")[-1].strip()
            return content
        except Exception as e:
            if attempt == 2:
                raise e
            time.sleep(10)

    raise Exception("Groq API failed after 3 retries")


# ─────────────────────────────────────────
# BUILD FULL SUMMARY FOR API 7
# ─────────────────────────────────────────

def build_full_summary(
    shared_context: dict,
    api1_output:    dict,
    api2_output:    dict,
    api3_6_output:  dict,
    user_option:    str,
) -> str:
    """
    Builds a complete summary of all previous API outputs
    to pass to API 7 for final verdict.
    """
    stock_name = shared_context.get("stock_name", "Unknown")

    # ── Sentiment (API 1) ──
    sentiment    = api1_output.get("overall", {})
    sent_score   = sentiment.get("overall_score", "N/A")
    sent_label   = sentiment.get("overall_sentiment", "N/A")
    sent_summary = sentiment.get("summary", "N/A")
    sent_breakdown = sentiment.get("score_breakdown", {})

    # ── Technicals (API 2) ──
    tech     = api2_output.get("technicals", {})
    price    = tech.get("price_data", {})
    ma       = tech.get("moving_averages", {})
    momentum = tech.get("momentum_indicators", {})
    trend    = tech.get("trend_analysis", {})
    returns  = tech.get("returns", {})
    signals  = tech.get("key_signals", [])
    sr       = tech.get("support_resistance", {})
    ai_report = api2_output.get("analysis_report", "N/A")

    # ── Fundamentals ──
    screener = shared_context.get("stock_data", {})
    ratios   = screener.get("key_ratios", {})
    pros     = screener.get("pros", [])
    cons     = screener.get("cons", [])

    # ── Strategies (API 3-6) ──
    strategies = api3_6_output.get("strategies", {})
    summary    = api3_6_output.get("summary", {})

    conservative = strategies.get("conservative", {})
    growth       = strategies.get("growth", {})
    emotional    = strategies.get("emotional", {})
    value        = strategies.get("value", {})

    return f"""
STOCK: {stock_name}
USER INTENT: {user_option}

════════════════════════════════════════
1. NEWS SENTIMENT ANALYSIS (API 1)
════════════════════════════════════════
Overall Score     : {sent_score}/10
Overall Sentiment : {sent_label}
Good/Neutral/Bad  : {sent_breakdown.get('good_articles','?')} / {sent_breakdown.get('neutral_articles','?')} / {sent_breakdown.get('bad_articles','?')} articles
Summary           : {sent_summary}

════════════════════════════════════════
2. FUNDAMENTAL DATA (Screener.in)
════════════════════════════════════════
PE Ratio       : {ratios.get('stock p/e', 'N/A')}
PB Ratio       : {ratios.get('price to book value', 'N/A')}
ROE            : {ratios.get('return on equity', 'N/A')}%
ROCE           : {ratios.get('roce', 'N/A')}%
Debt/Equity    : {ratios.get('debt to equity', 'N/A')}
Dividend Yield : {ratios.get('dividend yield', 'N/A')}%
Market Cap     : {ratios.get('market cap', 'N/A')} Cr
Pros           : {', '.join(pros[:4]) if pros else 'N/A'}
Cons           : {', '.join(cons[:4]) if cons else 'N/A'}

════════════════════════════════════════
3. TECHNICAL ANALYSIS (API 2 - stock_data.csv)
════════════════════════════════════════
Current Price  : ₹{price.get('current_price', 'N/A')}
52W High/Low   : ₹{price.get('52_week_high', 'N/A')} / ₹{price.get('52_week_low', 'N/A')}
MA20/50/200    : {ma.get('ma_20')} / {ma.get('ma_50')} / {ma.get('ma_200')}
vs MA50/200    : {ma.get('price_vs_ma50')} / {ma.get('price_vs_ma200')}
RSI (14)       : {momentum.get('rsi_14')} → {momentum.get('rsi_signal')}
MACD           : {momentum.get('macd_line')} → {momentum.get('macd_trend')}
Trend          : {trend.get('overall_trend')}
MA Cross       : {trend.get('ma_cross_signal')}
Support/Resist : ₹{sr.get('support_20d')} / ₹{sr.get('resistance_20d')}
1M/3M/6M Ret   : {returns.get('1_month_%')}% / {returns.get('3_month_%')}% / {returns.get('6_month_%')}%
1Y/3Y/5Y Ret   : {returns.get('1_year_%')}% / {returns.get('3_year_%')}% / {returns.get('5_year_%')}%
Key Signals    : {', '.join(signals)}

AI Technical Report:
{ai_report[:500] if ai_report != 'N/A' else 'Not available'}...

════════════════════════════════════════
4. STRATEGY RECOMMENDATIONS (API 3-6)
════════════════════════════════════════
CONSERVATIVE  : {summary.get('conservative', 'N/A')} (Confidence: {conservative.get('confidence','?')}/10)
  Reasoning   : {conservative.get('reasoning', 'N/A')[:200]}
  Risk Level  : {conservative.get('risk_level', 'N/A')}
  Target      : {conservative.get('target_price', 'N/A')}
  Stop Loss   : {conservative.get('stop_loss', 'N/A')}

GROWTH        : {summary.get('growth', 'N/A')} (Confidence: {growth.get('confidence','?')}/10)
  Reasoning   : {growth.get('reasoning', 'N/A')[:200]}
  Outlook     : {growth.get('growth_outlook', 'N/A')}
  Target      : {growth.get('target_price', 'N/A')}
  Horizon     : {growth.get('time_horizon', 'N/A')}

EMOTIONAL     : {summary.get('emotional', 'N/A')} (Confidence: {emotional.get('confidence','?')}/10)
  Reasoning   : {emotional.get('reasoning', 'N/A')[:200]}
  Momentum    : {emotional.get('momentum_signal', 'N/A')}
  Entry/Exit  : {emotional.get('entry_point', 'N/A')} / {emotional.get('exit_point', 'N/A')}
  Stop Loss   : {emotional.get('stop_loss', 'N/A')}

VALUE         : {summary.get('value', 'N/A')} (Confidence: {value.get('confidence','?')}/10)
  Reasoning   : {value.get('reasoning', 'N/A')[:200]}
  Valuation   : {value.get('valuation', 'N/A')}
  Margin Safe : {value.get('margin_of_safety', 'N/A')}
  Fair Value  : {value.get('intrinsic_value_estimate', 'N/A')}
  Buy Zone    : {value.get('buy_zone', 'N/A')}
""".strip()


# ─────────────────────────────────────────
# WEIGHTED VOTE CALCULATOR
# ─────────────────────────────────────────

def calculate_weighted_vote(api1_output: dict, api3_6_output: dict) -> dict:
    """
    Calculates a weighted vote from all strategies + sentiment.
    Weights: Value(30%) + Conservative(25%) + Growth(25%) + Emotional(20%)
    """
    score_map = {
        "STRONG BUY":  5,
        "BUY":         4,
        "HOLD":        3,
        "SELL":        2,
        "STRONG SELL": 1,
    }
    reverse_map = {5: "STRONG BUY", 4: "BUY", 3: "HOLD", 2: "SELL", 1: "STRONG SELL"}

    weights = {
        "value":        0.30,
        "conservative": 0.25,
        "growth":       0.25,
        "emotional":    0.20,
    }

    strategies  = api3_6_output.get("strategies", {})
    total_score = 0.0
    total_weight = 0.0

    breakdown = {}
    for name, weight in weights.items():
        rec = strategies.get(name, {}).get("recommendation", "HOLD")
        score = score_map.get(rec, 3)
        weighted = score * weight
        total_score  += weighted
        total_weight += weight
        breakdown[name] = {"recommendation": rec, "score": score, "weight": f"{int(weight*100)}%"}

    # Sentiment adjustment (-0.5 to +0.5)
    sent_score = api1_output.get("overall", {}).get("overall_score", 5)
    sent_adj   = (sent_score - 5) * 0.1  # ±0.5 max
    final_score = (total_score / total_weight) + sent_adj
    final_score = max(1, min(5, final_score))

    # Round to nearest recommendation
    rounded = round(final_score)
    final_rec = reverse_map.get(rounded, "HOLD")

    return {
        "final_recommendation": final_rec,
        "weighted_score":       round(final_score, 2),
        "max_score":            5,
        "strategy_breakdown":   breakdown,
        "sentiment_adjustment": round(sent_adj, 2),
    }


# ─────────────────────────────────────────
# MAIN VERDICT FUNCTION
# ─────────────────────────────────────────

def run_final_verdict(
    shared_context: dict,
    api1_output:    dict,
    api2_output:    dict,
    api3_6_output:  dict,
    user_option:    str = "Want to buy",
) -> dict:
    """
    Main entry point for API 7.
    Combines all outputs → generates final verdict.
    """
    stock_name = shared_context.get("stock_name", "Unknown Stock")

    print(f"\n[API7] Generating Final Verdict for {stock_name}...")
    print(f"  User Intent: {user_option}")

    if not GROQ_API_KEY:
        return {"status": "error", "message": "GROQ_API_KEY not set in .env"}

    # Step 1: Calculate weighted vote
    print(f"  [1/2] Calculating weighted vote from all strategies...")
    weighted = calculate_weighted_vote(api1_output, api3_6_output)
    print(f"  Weighted Score : {weighted['weighted_score']}/5")
    print(f"  Pre-AI Verdict : {weighted['final_recommendation']}")

    # Step 2: Build full summary
    full_summary = build_full_summary(
        shared_context, api1_output, api2_output, api3_6_output, user_option
    )

    # Step 3: Groq DeepSeek R1 — Final Verdict
    print(f"  [2/2] Running DeepSeek R1 final analysis...")

    system_prompt = """You are a senior Indian stock market analyst with 20 years of experience.
You have received analysis from 6 different AI systems about a stock.
Your job is to synthesize everything and give ONE clear, actionable final verdict.

Rules:
- Be direct and decisive — no vague answers
- Consider the user's specific intent (buy/hold/sell)
- Back every claim with data from the analysis provided
- Write like a professional analyst report
- Consider Indian market context (NSE/BSE, Indian economy, sector trends)

Respond in this EXACT JSON format only:
{
  "final_verdict": "<STRONG BUY | BUY | HOLD | SELL | STRONG SELL>",
  "confidence": <1-10>,
  "one_line_summary": "<single powerful sentence summarizing the verdict>",
  "detailed_reasoning": "<4-5 sentences combining all analysis — sentiment, technicals, fundamentals, strategies>",
  "bull_case": "<2-3 sentences on why it could go up>",
  "bear_case": "<2-3 sentences on why it could go down>",
  "action_for_user": "<specific action based on user intent — buy/already bought/sell>",
  "price_targets": {
    "target_1": "<short term 3-6 month target in INR>",
    "target_2": "<long term 1-2 year target in INR>",
    "stop_loss": "<stop loss price in INR>"
  },
  "risk_rating": "<LOW | MEDIUM | HIGH | VERY HIGH>",
  "time_horizon": "<recommended holding period>",
  "key_catalysts": ["<catalyst1>", "<catalyst2>", "<catalyst3>"],
  "key_risks":     ["<risk1>", "<risk2>", "<risk3>"],
  "scores": {
    "sentiment_score":    <1-10>,
    "fundamental_score":  <1-10>,
    "technical_score":    <1-10>,
    "overall_score":      <1-10>
  }
}"""

    user_prompt = f"""Here is the complete analysis from all 6 AI systems:

{full_summary}

Pre-calculated weighted vote: {weighted['final_recommendation']} (score: {weighted['weighted_score']}/5)

Strategy votes:
- Conservative : {weighted['strategy_breakdown'].get('conservative', {}).get('recommendation', 'N/A')}
- Growth       : {weighted['strategy_breakdown'].get('growth', {}).get('recommendation', 'N/A')}
- Emotional    : {weighted['strategy_breakdown'].get('emotional', {}).get('recommendation', 'N/A')}
- Value        : {weighted['strategy_breakdown'].get('value', {}).get('recommendation', 'N/A')}

Now give the FINAL VERDICT as a senior analyst.
User's intent: {user_option}

Return JSON only."""

    try:
        raw = call_groq(system_prompt, user_prompt, max_tokens=2000)

        # Parse JSON
        if "```" in raw:
            parts = raw.split("```")
            for part in parts:
                if part.startswith("json"):
                    raw = part[4:].strip()
                    break
                elif "{" in part:
                    raw = part.strip()
                    break
        start = raw.find("{")
        end   = raw.rfind("}") + 1
        if start != -1 and end > start:
            raw = raw[start:end]

        verdict = json.loads(raw)

    except Exception as e:
        print(f"  [API7] ⚠️ Groq parsing failed: {e}. Using weighted vote as fallback.")
        verdict = {
            "final_verdict":      weighted["final_recommendation"],
            "confidence":         6,
            "one_line_summary":   f"Based on weighted analysis: {weighted['final_recommendation']}",
            "detailed_reasoning": "AI synthesis unavailable. Based on weighted strategy votes.",
            "bull_case":          "See individual strategy reports.",
            "bear_case":          "See individual strategy reports.",
            "action_for_user":    f"Based on {user_option}: {weighted['final_recommendation']}",
            "risk_rating":        "MEDIUM",
            "time_horizon":       "1-2 years",
            "key_catalysts":      [],
            "key_risks":          [],
            "scores": {
                "sentiment_score":   int(api1_output.get("overall", {}).get("overall_score", 5)),
                "fundamental_score": 6,
                "technical_score":   5,
                "overall_score":     int(weighted["weighted_score"] * 2),
            },
        }

    # Build final result
    result = {
        "status":          "success",
        "api":             "API7 - Final Verdict",
        "model":           GROQ_MODEL,
        "stock":           stock_name,
        "user_option":     user_option,
        "weighted_vote":   weighted,
        "verdict":         verdict,
    }

    # Print summary
    print(f"\n{'='*50}")
    print(f"  FINAL VERDICT : {verdict.get('final_verdict', 'N/A')}")
    print(f"  Confidence    : {verdict.get('confidence', 'N/A')}/10")
    print(f"  Risk Rating   : {verdict.get('risk_rating', 'N/A')}")
    print(f"  Summary       : {verdict.get('one_line_summary', 'N/A')}")
    print(f"  Action        : {verdict.get('action_for_user', 'N/A')}")
    print(f"  Scores        : Sentiment={verdict.get('scores',{}).get('sentiment_score','?')} | Fundamental={verdict.get('scores',{}).get('fundamental_score','?')} | Technical={verdict.get('scores',{}).get('technical_score','?')} | Overall={verdict.get('scores',{}).get('overall_score','?')}")
    print(f"{'='*50}")

    return result


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
        with open("api1_output.json", "r") as f:
            api1_output = json.load(f)
        print("✅ Loaded api1_output.json")
    except FileNotFoundError:
        print("❌ api1_output.json not found. Run api1_sentiment.py first!")
        exit(1)

    try:
        with open("api2_output.json", "r") as f:
            api2_output = json.load(f)
        print("✅ Loaded api2_output.json")
    except FileNotFoundError:
        print("❌ api2_output.json not found. Run api2_fundamental.py first!")
        exit(1)

    try:
        with open("api3_6_output.json", "r") as f:
            api3_6_output = json.load(f)
        print("✅ Loaded api3_6_output.json")
    except FileNotFoundError:
        print("❌ api3_6_output.json not found. Run api3_6_strategy.py first!")
        exit(1)

    result = run_final_verdict(
        shared_context,
        api1_output,
        api2_output,
        api3_6_output,
        user_option="Want to buy",
    )

    with open("api7_output.json", "w") as f:
        json.dump(result, f, indent=2)

    print("\n✅ Saved to api7_output.json")