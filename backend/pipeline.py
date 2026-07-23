import json
import time
import os
from datetime import datetime

# Import all APIs
from data_fetch       import fetch_all
from api1_sentiment   import run_sentiment_analysis
from api2_fundamental import run_data_analysis
from api3_6_strategy  import run_all_strategies
from api7_verdict     import run_final_verdict


# ─────────────────────────────────────────
# PIPELINE PROGRESS TRACKER
# ─────────────────────────────────────────

class Pipeline:
    def __init__(self):
        self.steps = [
            "Fetching stock data & news",
            "Analyzing news sentiment",
            "Running technical & fundamental analysis",
            "Running strategy analysis (Conservative)",
            "Running strategy analysis (Growth)",
            "Running strategy analysis (Emotional)",
            "Running strategy analysis (Value)",
            "Generating final verdict",
        ]
        self.current_step  = 0
        self.total_steps   = len(self.steps)
        self.start_time    = None
        self.errors        = []
        self.progress_log  = []

    def start(self):
        self.start_time = datetime.now()
        print(f"\n{'='*60}")
        print(f"  STOCK ANALYZER PIPELINE STARTED")
        print(f"  Time: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}\n")

    def step(self, step_name: str):
        self.current_step += 1
        progress = int((self.current_step / self.total_steps) * 100)
        elapsed  = round((datetime.now() - self.start_time).total_seconds(), 1)
        log = f"[{self.current_step}/{self.total_steps}] ({progress}%) {step_name} | {elapsed}s elapsed"
        print(log)
        self.progress_log.append({
            "step":     self.current_step,
            "name":     step_name,
            "progress": progress,
            "elapsed":  elapsed,
        })

    def error(self, step_name: str, error: str):
        self.errors.append({"step": step_name, "error": error})
        print(f"  ⚠️  WARNING: {step_name} failed — {error}")
        print(f"      Pipeline will continue with available data...")

    def done(self):
        elapsed = round((datetime.now() - self.start_time).total_seconds(), 1)
        print(f"\n{'='*60}")
        print(f"  PIPELINE COMPLETE in {elapsed}s")
        if self.errors:
            print(f"  ⚠️  {len(self.errors)} step(s) had errors (non-critical)")
        print(f"{'='*60}\n")
        return elapsed


# ─────────────────────────────────────────
# MAIN PIPELINE FUNCTION
# ─────────────────────────────────────────

def run_pipeline(
    ticker:      str,
    stock_name:  str,
    user_option: str,
    csv_path:    str = "stock_data.csv",
) -> dict:
    """
    Master pipeline — runs all 7 APIs in sequence.

    Args:
        ticker:      NSE ticker e.g. "TCS.NS"
        stock_name:  Full company name e.g. "Tata Consultancy Services"
        user_option: "Want to buy" | "Already bought" | "Want to sell"
        csv_path:    Path to save/read historical CSV

    Returns:
        Complete result dict with all analysis + final verdict
    """

    pipe = Pipeline()
    pipe.start()

    result = {
        "status":      "running",
        "ticker":      ticker,
        "stock_name":  stock_name,
        "user_option": user_option,
        "started_at":  datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "pipeline_log": [],
        "errors":      [],

        # API outputs
        "data":         None,
        "sentiment":    None,
        "technical":    None,
        "strategies":   None,
        "verdict":      None,
    }

    # ─────────────────────────────────────
    # STEP 1 — Data Fetch
    # ─────────────────────────────────────
    pipe.step("Fetching stock data & news")
    try:
        shared_context = fetch_all(ticker, stock_name, csv_path=csv_path)

        if shared_context["stock_data"]["status"] == "error":
            pipe.error("Data Fetch - Stock Data", shared_context["stock_data"]["message"])
        if shared_context["news_data"]["total_articles"] == 0:
            pipe.error("Data Fetch - News", "No news articles found")

        result["data"] = {
            "stock_data":  shared_context["stock_data"],
            "news_data":   shared_context["news_data"],
            "csv_saved":   csv_path,
        }

    except Exception as e:
        pipe.error("Data Fetch", str(e))
        result["status"] = "error"
        result["message"] = f"Critical: Data fetch failed — {str(e)}"
        result["errors"] = pipe.errors
        return result

    # ─────────────────────────────────────
    # STEP 2 — Sentiment Analysis (API 1)
    # ─────────────────────────────────────
    pipe.step("Analyzing news sentiment (API 1 - Groq)")
    try:
        api1_output = run_sentiment_analysis(shared_context)
        shared_context["_sentiment"] = api1_output
        result["sentiment"] = api1_output

        overall = api1_output.get("overall", {})
        print(f"    Score: {overall.get('overall_score','?')}/10 | {overall.get('overall_sentiment','?')}")

    except Exception as e:
        pipe.error("API1 Sentiment", str(e))
        api1_output = {
            "status": "error",
            "overall": {"overall_score": 5, "overall_sentiment": "NEUTRAL", "summary": "Sentiment analysis failed"},
        }
        result["sentiment"] = api1_output

    # ─────────────────────────────────────
    # STEP 3 — Technical + Fundamental (API 2)
    # ─────────────────────────────────────
    pipe.step("Running technical & fundamental analysis (API 2 - Gemini)")
    try:
        api2_output = run_data_analysis(shared_context, csv_path=csv_path)
        result["technical"] = api2_output

        tech = api2_output.get("technicals", {})
        trend = tech.get("trend_analysis", {}).get("overall_trend", "?")
        rsi   = tech.get("momentum_indicators", {}).get("rsi_14", "?")
        print(f"    Trend: {trend} | RSI: {rsi}")

    except Exception as e:
        pipe.error("API2 Technical", str(e))
        api2_output = {"status": "error", "technicals": {}, "analysis_report": "Technical analysis failed"}
        result["technical"] = api2_output

    # ─────────────────────────────────────
    # STEP 4-7 — Strategy Analysis (API 3-6)
    # ─────────────────────────────────────
    pipe.step("Running 4 strategy analyses (API 3-6 - Gemini)")
    try:
        api3_6_output = run_all_strategies(shared_context, api2_output, user_option)
        result["strategies"] = api3_6_output

        summary = api3_6_output.get("summary", {})
        print(f"    Conservative: {summary.get('conservative','?')} | Growth: {summary.get('growth','?')} | Emotional: {summary.get('emotional','?')} | Value: {summary.get('value','?')}")

    except Exception as e:
        pipe.error("API3-6 Strategies", str(e))
        api3_6_output = {
            "status": "error",
            "strategies": {},
            "summary": {"conservative": "N/A", "growth": "N/A", "emotional": "N/A", "value": "N/A"},
        }
        result["strategies"] = api3_6_output

    # ─────────────────────────────────────
    # STEP 8 — Final Verdict (API 7)
    # ─────────────────────────────────────
    pipe.step("Generating final verdict (API 7 - DeepSeek R1)")
    try:
        api7_output = run_final_verdict(
            shared_context,
            api1_output,
            api2_output,
            api3_6_output,
            user_option,
        )
        result["verdict"] = api7_output

        verdict = api7_output.get("verdict", {})
        print(f"    VERDICT: {verdict.get('final_verdict','?')} | Confidence: {verdict.get('confidence','?')}/10")
        print(f"    {verdict.get('one_line_summary','')}")

    except Exception as e:
        pipe.error("API7 Verdict", str(e))
        result["verdict"] = {"status": "error", "message": str(e)}

    # ─────────────────────────────────────
    # FINALIZE
    # ─────────────────────────────────────
    elapsed = pipe.done()

    result["status"]       = "success" if not pipe.errors else "partial"
    result["completed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    result["total_time_s"] = elapsed
    result["pipeline_log"] = pipe.progress_log
    result["errors"]       = pipe.errors

    # ── Clean output for frontend ──
    result["output"] = build_frontend_output(result)

    return result


# ─────────────────────────────────────────
# BUILD CLEAN FRONTEND OUTPUT
# ─────────────────────────────────────────

def build_frontend_output(result: dict) -> dict:
    """
    Extracts only what frontend needs.
    Clean, flat structure — easy to render in HTML/JS.
    """
    verdict    = result.get("verdict", {}).get("verdict", {})
    sentiment  = result.get("sentiment", {}).get("overall", {})
    technical  = result.get("technical", {}).get("technicals", {})
    strategies = result.get("strategies", {}).get("summary", {})
    weighted   = result.get("verdict", {}).get("weighted_vote", {})
    price      = technical.get("price_data", {})
    returns    = technical.get("returns", {})
    momentum   = technical.get("momentum_indicators", {})
    trend      = technical.get("trend_analysis", {})
    screener   = result.get("data", {}).get("stock_data", {})
    ratios     = screener.get("key_ratios", {}) if screener else {}

    return {
        # ── Header ──
        "stock_name":   result.get("stock_name"),
        "ticker":       result.get("ticker"),
        "user_option":  result.get("user_option"),
        "analyzed_at":  result.get("completed_at"),

        # ── Final Verdict ──
        "final_verdict":     verdict.get("final_verdict", "N/A"),
        "confidence":        verdict.get("confidence", "N/A"),
        "one_line_summary":  verdict.get("one_line_summary", "N/A"),
        "detailed_reasoning":verdict.get("detailed_reasoning", "N/A"),
        "action_for_user":   verdict.get("action_for_user", "N/A"),
        "bull_case":         verdict.get("bull_case", "N/A"),
        "bear_case":         verdict.get("bear_case", "N/A"),
        "risk_rating":       verdict.get("risk_rating", "N/A"),
        "time_horizon":      verdict.get("time_horizon", "N/A"),
        "key_catalysts":     verdict.get("key_catalysts", []),
        "key_risks":         verdict.get("key_risks", []),

        # ── Price Targets ──
        "price_targets": verdict.get("price_targets", {}),

        # ── Scores ──
        "scores": verdict.get("scores", {}),

        # ── Strategy Votes ──
        "strategy_votes": {
            "conservative": strategies.get("conservative", "N/A"),
            "growth":       strategies.get("growth",       "N/A"),
            "emotional":    strategies.get("emotional",    "N/A"),
            "value":        strategies.get("value",        "N/A"),
        },
        "weighted_score": weighted.get("weighted_score", "N/A"),

        # ── Sentiment ──
        "sentiment": {
            "score":     sentiment.get("overall_score", "N/A"),
            "label":     sentiment.get("overall_sentiment", "N/A"),
            "summary":   sentiment.get("summary", "N/A"),
            "breakdown": sentiment.get("score_breakdown", {}),
        },

        # ── Price & Technicals ──
        "price": {
            "current":      price.get("current_price", "N/A"),
            "week52_high":  price.get("52_week_high", "N/A"),
            "week52_low":   price.get("52_week_low", "N/A"),
        },
        "technicals": {
            "rsi":          momentum.get("rsi_14", "N/A"),
            "rsi_signal":   momentum.get("rsi_signal", "N/A"),
            "macd_trend":   momentum.get("macd_trend", "N/A"),
            "trend":        trend.get("overall_trend", "N/A"),
            "ma_cross":     trend.get("ma_cross_signal", "N/A"),
        },
        "returns": {
            "1_month":  returns.get("1_month_%", "N/A"),
            "3_month":  returns.get("3_month_%", "N/A"),
            "6_month":  returns.get("6_month_%", "N/A"),
            "1_year":   returns.get("1_year_%", "N/A"),
            "3_year":   returns.get("3_year_%", "N/A"),
            "5_year":   returns.get("5_year_%", "N/A"),
        },

        # ── Fundamentals ──
        "fundamentals": {
            "pe_ratio":      ratios.get("stock p/e", "N/A"),
            "pb_ratio":      ratios.get("price to book value", "N/A"),
            "roe":           ratios.get("return on equity", "N/A"),
            "roce":          ratios.get("roce", "N/A"),
            "debt_equity":   ratios.get("debt to equity", "N/A"),
            "dividend_yield":ratios.get("dividend yield", "N/A"),
            "market_cap":    ratios.get("market cap", "N/A"),
        },

        # ── Pipeline Info ──
        "pipeline_time_s": result.get("total_time_s", "N/A"),
        "pipeline_errors": len(result.get("errors", [])),
    }


# ─────────────────────────────────────────
# TEST
# ─────────────────────────────────────────

if __name__ == "__main__":
    # Full end-to-end test
    result = run_pipeline(
        ticker      = "TCS.NS",
        stock_name  = "Tata Consultancy Services",
        user_option = "Want to buy",
        csv_path    = "stock_data.csv",
    )

    # Save full result
    with open("pipeline_output.json", "w") as f:
        json.dump(result, f, indent=2)
    print("✅ Full pipeline output saved to pipeline_output.json")

    # Save clean frontend output separately
    with open("frontend_output.json", "w") as f:
        json.dump(result["output"], f, indent=2)
    print("✅ Clean frontend output saved to frontend_output.json")

    # Print final verdict
    out = result["output"]
    print(f"\n{'='*50}")
    print(f"  STOCK        : {out['stock_name']} ({out['ticker']})")
    print(f"  VERDICT      : {out['final_verdict']}")
    print(f"  CONFIDENCE   : {out['confidence']}/10")
    print(f"  RISK         : {out['risk_rating']}")
    print(f"  SUMMARY      : {out['one_line_summary']}")
    print(f"  ACTION       : {out['action_for_user']}")
    print(f"  TIME TAKEN   : {out['pipeline_time_s']}s")
    print(f"{'='*50}")