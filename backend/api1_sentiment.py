import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_URL     = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL   = "llama-3.1-8b-instant"  # Free, fast on Groq


# ─────────────────────────────────────────
# GROQ CALL HELPER
# ─────────────────────────────────────────

def call_groq(system_prompt: str, user_prompt: str, max_tokens: int = 1000) -> str:
    """Calls Groq API and returns text response."""
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": GROQ_MODEL,
        "max_tokens": max_tokens,
        "temperature": 0.2,  # Low = more consistent, factual
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
    }
    resp = requests.post(GROQ_URL, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


# ─────────────────────────────────────────
# SENTIMENT SCORING — Per Article
# ─────────────────────────────────────────

def score_single_article(article: dict, stock_name: str) -> dict:
    """
    Scores a single news article for sentiment.
    Returns score 0-10 with reasoning.
    """
    system_prompt = """You are a financial news sentiment analyst specializing in Indian stock markets.
Your job is to score a news article's sentiment for a specific stock.

Scoring rules:
- Score 0-3  → BAD     (negative news: losses, fraud, regulatory issues, market crash, client losses)
- Score 4-6  → NEUTRAL (mixed news, general market updates, no direct impact)
- Score 7-10 → GOOD    (positive news: strong results, new contracts, growth, partnerships, analyst upgrades)

IMPORTANT:
- Only score based on impact on the STOCK, not general market
- Be strict — don't give 7+ unless clearly positive for the stock
- Respond ONLY in this exact JSON format, nothing else:
{
  "score": <number 0-10>,
  "sentiment": "<GOOD|NEUTRAL|BAD>",
  "reason": "<one sentence explanation>"
}"""

    user_prompt = f"""Stock: {stock_name}

Article Title: {article.get('title', 'N/A')}
Article Summary: {article.get('summary', 'N/A')[:300]}
Published: {article.get('published', 'N/A')}

Score this article's sentiment for {stock_name} stock."""

    try:
        raw = call_groq(system_prompt, user_prompt, max_tokens=200)

        # Clean and parse JSON
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        result = json.loads(raw)

        return {
            "title":     article.get("title", "N/A"),
            "published": article.get("published", "N/A"),
            "score":     int(result.get("score", 5)),
            "sentiment": result.get("sentiment", "NEUTRAL"),
            "reason":    result.get("reason", "N/A"),
        }

    except Exception as e:
        return {
            "title":     article.get("title", "N/A"),
            "published": article.get("published", "N/A"),
            "score":     5,
            "sentiment": "NEUTRAL",
            "reason":    f"Could not parse: {str(e)}",
        }


# ─────────────────────────────────────────
# OVERALL SENTIMENT — All Articles
# ─────────────────────────────────────────

def get_overall_sentiment(scored_articles: list, stock_name: str) -> dict:
    """
    Takes all scored articles and produces final overall sentiment.
    Uses your scoring system: 7-10=Good, 4-6=Neutral, 0-3=Bad
    """
    if not scored_articles:
        return {
            "overall_score":     5,
            "overall_sentiment": "NEUTRAL",
            "summary":           "No articles to analyze",
        }

    scores = [a["score"] for a in scored_articles]
    avg_score = round(sum(scores) / len(scores), 2)

    # Your scoring system from the diagram
    if avg_score >= 7:
        overall_sentiment = "GOOD"
    elif avg_score >= 4:
        overall_sentiment = "NEUTRAL"
    else:
        overall_sentiment = "BAD"

    # Count distribution
    good_count    = sum(1 for a in scored_articles if a["sentiment"] == "GOOD")
    neutral_count = sum(1 for a in scored_articles if a["sentiment"] == "NEUTRAL")
    bad_count     = sum(1 for a in scored_articles if a["sentiment"] == "BAD")

    # Ask Groq for a final summary paragraph
    system_prompt = """You are a financial sentiment analyst. 
Given scored news articles about a stock, write a brief 2-3 sentence summary 
of the overall news sentiment and what it means for the stock.
Be direct and factual. No fluff."""

    articles_text = "\n".join([
        f"- [{a['sentiment']} {a['score']}/10] {a['title']} | {a['reason']}"
        for a in scored_articles
    ])

    user_prompt = f"""Stock: {stock_name}
Overall Score: {avg_score}/10 ({overall_sentiment})

Scored Articles:
{articles_text}

Write a 2-3 sentence summary of the news sentiment for {stock_name}."""

    try:
        summary = call_groq(system_prompt, user_prompt, max_tokens=300)
    except Exception:
        summary = f"Overall news sentiment for {stock_name} is {overall_sentiment} with an average score of {avg_score}/10."

    return {
        "overall_score":     avg_score,
        "overall_sentiment": overall_sentiment,
        "score_breakdown": {
            "good_articles":    good_count,
            "neutral_articles": neutral_count,
            "bad_articles":     bad_count,
            "total_articles":   len(scored_articles),
        },
        "score_interpretation": (
            "7-10 = GOOD | 4-6 = NEUTRAL | 0-3 = BAD"
        ),
        "summary": summary,
    }


# ─────────────────────────────────────────
# MAIN FUNCTION — Run API 1
# ─────────────────────────────────────────

def run_sentiment_analysis(shared_context: dict) -> dict:
    """
    Main entry point for API 1.
    Takes shared_context from data_fetch.fetch_all()
    Returns sentiment analysis results.
    """
    stock_name = shared_context.get("stock_name", "Unknown Stock")
    articles   = shared_context.get("news_data", {}).get("articles", [])

    print(f"\n[API1 Sentiment] Analyzing {len(articles)} articles for {stock_name}...")

    if not articles:
        return {
            "status":  "error",
            "message": "No news articles to analyze",
        }

    if not GROQ_API_KEY:
        return {
            "status":  "error",
            "message": "GROQ_API_KEY not set in .env file",
        }

    # Score each article (use top 10 to save API calls)
    scored_articles = []
    articles_to_score = articles[:10]

    for i, article in enumerate(articles_to_score):
        print(f"  Scoring article {i+1}/{len(articles_to_score)}: {article['title'][:60]}...")
        scored = score_single_article(article, stock_name)
        scored_articles.append(scored)

    # Get overall sentiment
    print(f"  Calculating overall sentiment...")
    overall = get_overall_sentiment(scored_articles, stock_name)

    result = {
        "status":           "success",
        "api":              "API1 - News Sentiment Analysis",
        "model":            GROQ_MODEL,
        "stock":            stock_name,
        "scored_articles":  scored_articles,
        "overall":          overall,
    }

    print(f"\n[API1] ✅ Done!")
    print(f"  Overall Score     : {overall['overall_score']}/10")
    print(f"  Overall Sentiment : {overall['overall_sentiment']}")
    print(f"  Good/Neutral/Bad  : {overall['score_breakdown']['good_articles']} / {overall['score_breakdown']['neutral_articles']} / {overall['score_breakdown']['bad_articles']}")
    print(f"  Summary           : {overall['summary'][:100]}...")

    return result


# ─────────────────────────────────────────
# TEST
# ─────────────────────────────────────────

if __name__ == "__main__":
    # Load shared context from data_fetch output
    try:
        with open("test_output.json", "r") as f:
            shared_context = json.load(f)
        print("✅ Loaded test_output.json from data_fetch")
    except FileNotFoundError:
        print("❌ test_output.json not found. Run data_fetch.py first!")
        exit(1)

    result = run_sentiment_analysis(shared_context)

    # Save output
    with open("api1_output.json", "w") as f:
        json.dump(result, f, indent=2)

    print("\n✅ Saved to api1_output.json")