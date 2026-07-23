import feedparser
import requests
import json
import csv
import time
import random
from datetime import datetime, timedelta
from urllib.parse import quote_plus
from bs4 import BeautifulSoup

# ─────────────────────────────────────────
# HEADERS
# ─────────────────────────────────────────

def get_headers(referer="https://www.screener.in/"):
    agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/17.0 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36",
    ]
    return {
        "User-Agent": random.choice(agents),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": referer,
        "Connection": "keep-alive",
    }


# ─────────────────────────────────────────
# 1. SCREENER.IN — Fundamentals
# ─────────────────────────────────────────

def get_screener_data(symbol: str) -> dict:
    """
    Scrapes complete fundamental data from Screener.in
    symbol: "TCS", "INFY", "RELIANCE"
    """
    try:
        session = requests.Session()
        urls = [
            f"https://www.screener.in/company/{symbol}/consolidated/",
            f"https://www.screener.in/company/{symbol}/",
        ]

        resp = None
        for url in urls:
            r = session.get(url, headers=get_headers(), timeout=15)
            if r.status_code == 200:
                resp = r
                break
            time.sleep(1)

        if not resp:
            return {"status": "error", "message": "Screener.in not accessible"}

        soup = BeautifulSoup(resp.text, "html.parser")

        # Company name
        name = "N/A"
        try:
            name = soup.find("h1").get_text(strip=True)
        except Exception:
            pass

        # Current price
        current_price = "N/A"
        try:
            price_tag = soup.find("div", class_="flex-column")
            if price_tag:
                current_price = price_tag.find("span").get_text(strip=True).replace("₹","").replace(",","").strip()
        except Exception:
            pass

        # Key ratios
        ratios = {}
        try:
            ratio_section = soup.find("div", id="top-ratios")
            if ratio_section:
                for item in ratio_section.find_all("li"):
                    spans = item.find_all("span")
                    if len(spans) >= 2:
                        label = spans[0].get_text(strip=True).lower()
                        value = spans[-1].get_text(strip=True).replace(",","").replace("%","").replace("₹","").strip()
                        ratios[label] = value
        except Exception:
            pass

        # Quarterly results
        quarterly = []
        try:
            q_section = soup.find("section", id="quarters")
            if q_section:
                table = q_section.find("table")
                if table:
                    hdrs = [th.get_text(strip=True) for th in table.find_all("th")]
                    for row in table.find_all("tr")[1:5]:
                        cells = row.find_all("td")
                        if cells:
                            quarterly.append({
                                "metric": cells[0].get_text(strip=True),
                                "values": [c.get_text(strip=True).replace(",","") for c in cells[1:]],
                                "periods": hdrs[1:],
                            })
        except Exception:
            pass

        # Annual P&L
        annual = []
        try:
            pl_section = soup.find("section", id="profit-loss")
            if pl_section:
                table = pl_section.find("table")
                if table:
                    hdrs = [th.get_text(strip=True) for th in table.find_all("th")]
                    for row in table.find_all("tr")[1:6]:
                        cells = row.find_all("td")
                        if cells:
                            annual.append({
                                "metric": cells[0].get_text(strip=True),
                                "values": [c.get_text(strip=True).replace(",","") for c in cells[1:]],
                                "periods": hdrs[1:],
                            })
        except Exception:
            pass

        # Balance sheet
        balance = []
        try:
            bs_section = soup.find("section", id="balance-sheet")
            if bs_section:
                table = bs_section.find("table")
                if table:
                    hdrs = [th.get_text(strip=True) for th in table.find_all("th")]
                    for row in table.find_all("tr")[1:5]:
                        cells = row.find_all("td")
                        if cells:
                            balance.append({
                                "metric": cells[0].get_text(strip=True),
                                "values": [c.get_text(strip=True).replace(",","") for c in cells[1:]],
                                "periods": hdrs[1:],
                            })
        except Exception:
            pass

        # Pros & Cons
        pros, cons = [], []
        try:
            p = soup.find("div", class_="pros")
            if p:
                pros = [li.get_text(strip=True) for li in p.find_all("li")]
        except Exception:
            pass
        try:
            c = soup.find("div", class_="cons")
            if c:
                cons = [li.get_text(strip=True) for li in c.find_all("li")]
        except Exception:
            pass

        # About
        about = "N/A"
        try:
            ab = soup.find("div", class_="about")
            if ab:
                about = ab.get_text(strip=True)[:500]
        except Exception:
            pass

        return {
            "status": "success",
            "source": "Screener.in",
            "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "basic": {"name": name, "symbol": symbol, "current_price": current_price},
            "key_ratios": ratios,
            "quarterly_results": quarterly,
            "annual_pl": annual,
            "balance_sheet": balance,
            "pros": pros,
            "cons": cons,
            "about": about,
        }

    except Exception as e:
        return {"status": "error", "source": "Screener.in", "message": str(e)}


# ─────────────────────────────────────────
# 2. HISTORICAL DATA — Yahoo Finance CSV
#    5 years daily OHLCV saved to stock_data.csv
# ─────────────────────────────────────────

def get_historical_data(symbol: str, csv_path: str = "stock_data.csv") -> dict:
    """
    Downloads 5 years of daily OHLCV from Yahoo Finance.
    Saves raw data to stock_data.csv.
    Also calculates technical indicators from the data.
    symbol: "TCS" (auto adds .NS for NSE)
    """
    try:
        end_date   = datetime.now()
        start_date = end_date - timedelta(days=5 * 365)

        period1 = int(start_date.timestamp())
        period2 = int(end_date.timestamp())

        ticker_yf = f"{symbol}.NS"

        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://finance.yahoo.com/",
        })

        # Step 1: Visit Yahoo Finance to get session cookies
        session.get("https://finance.yahoo.com", timeout=10)
        time.sleep(random.uniform(1, 2))

        # Step 2: Get crumb (Yahoo requires this for CSV download)
        crumb = None
        try:
            crumb_resp = session.get(
                "https://query2.finance.yahoo.com/v1/test/csrfToken",
                timeout=10
            )
            if crumb_resp.status_code == 200:
                crumb = crumb_resp.text.strip()
        except Exception:
            pass

        # Step 3: Build download URL
        csv_url = (
            f"https://query1.finance.yahoo.com/v7/finance/download/{ticker_yf}"
            f"?period1={period1}&period2={period2}&interval=1d&events=history"
        )
        if crumb:
            csv_url += f"&crumb={crumb}"

        # Step 4: Download CSV
        time.sleep(random.uniform(1, 2))
        resp = session.get(csv_url, timeout=15)

        # If 401/429, try alternate endpoint
        if resp.status_code in [401, 429, 403]:
            alt_url = (
                f"https://query2.finance.yahoo.com/v8/finance/chart/{ticker_yf}"
                f"?period1={period1}&period2={period2}&interval=1d"
            )
            resp = session.get(alt_url, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            # Parse chart API response
            chart = data["chart"]["result"][0]
            timestamps = chart["timestamp"]
            ohlcv = chart["indicators"]["quote"][0]

            records = []
            for i, ts in enumerate(timestamps):
                try:
                    records.append({
                        "Date":   datetime.fromtimestamp(ts).strftime("%Y-%m-%d"),
                        "Open":   round(ohlcv["open"][i], 2)   if ohlcv["open"][i]   else None,
                        "High":   round(ohlcv["high"][i], 2)   if ohlcv["high"][i]   else None,
                        "Low":    round(ohlcv["low"][i], 2)    if ohlcv["low"][i]    else None,
                        "Close":  round(ohlcv["close"][i], 2)  if ohlcv["close"][i]  else None,
                        "Volume": int(ohlcv["volume"][i])       if ohlcv["volume"][i] else 0,
                    })
                except (IndexError, TypeError):
                    continue

        else:
            resp.raise_for_status()
            content = resp.text.strip()

            if "Date" not in content or len(content.split("\n")) < 2:
                return {"status": "error", "message": "Yahoo Finance returned no data. Try again later."}

            # Parse CSV response
            records = []
            reader = csv.DictReader(content.splitlines())
            for row in reader:
                try:
                    if row.get("Close") in [None, "", "null"]:
                        continue
                    records.append({
                        "Date":   row["Date"],
                        "Open":   round(float(row["Open"]), 2),
                        "High":   round(float(row["High"]), 2),
                        "Low":    round(float(row["Low"]), 2),
                        "Close":  round(float(row["Close"]), 2),
                        "Volume": int(float(row["Volume"])) if row.get("Volume") else 0,
                    })
                except (ValueError, KeyError):
                    continue

        if not records:
            return {"status": "error", "message": "No records parsed from Yahoo Finance"}

        # ── Save to CSV ──
        csv_fields = ["Date", "Open", "High", "Low", "Close", "Volume"]
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=csv_fields)
            writer.writeheader()
            writer.writerows(records)
        print(f"[Historical] ✅ Saved {len(records)} rows to {csv_path}")

        # ── Calculate Indicators ──
        closes  = [r["Close"]  for r in records if r["Close"]]
        volumes = [r["Volume"] for r in records]

        def ma(data, w):
            return round(sum(data[-w:]) / w, 2) if len(data) >= w else None

        def ret(data, days):
            if len(data) > days:
                return round(((data[-1] - data[-days]) / data[-days]) * 100, 2)
            return None

        def calc_rsi(closes, period=14):
            try:
                deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
                gains  = [d if d > 0 else 0 for d in deltas[-period:]]
                losses = [-d if d < 0 else 0 for d in deltas[-period:]]
                avg_gain = sum(gains) / period
                avg_loss = sum(losses) / period
                if avg_loss == 0:
                    return 100.0
                rs = avg_gain / avg_loss
                return round(100 - (100 / (1 + rs)), 2)
            except Exception:
                return None

        last_252 = closes[-252:] if len(closes) >= 252 else closes

        # Yearly summary
        yearly = {}
        for r in records:
            yr = r["Date"][:4]
            if yr not in yearly:
                yearly[yr] = {
                    "open": r["Open"], "high": r["High"],
                    "low": r["Low"],   "close": r["Close"],
                    "trading_days": 0
                }
            if r["High"]:
                yearly[yr]["high"]  = max(yearly[yr]["high"], r["High"])
            if r["Low"]:
                yearly[yr]["low"]   = min(yearly[yr]["low"],  r["Low"])
            yearly[yr]["close"] = r["Close"]
            yearly[yr]["trading_days"] += 1

        yrs = sorted(yearly.keys())
        for i, yr in enumerate(yrs):
            if i > 0:
                prev = yearly[yrs[i-1]]["close"]
                curr = yearly[yr]["close"]
                yearly[yr]["annual_return_%"] = round(((curr - prev) / prev) * 100, 2)
            else:
                yearly[yr]["annual_return_%"] = "N/A"

        ma50  = ma(closes, 50)
        ma200 = ma(closes, 200)

        technical = {
            "current_price":      closes[-1],
            "ma_20":              ma(closes, 20),
            "ma_50":              ma50,
            "ma_200":             ma200,
            "rsi_14":             calc_rsi(closes),
            "52_week_high":       round(max(last_252), 2),
            "52_week_low":        round(min(last_252), 2),
            "5yr_high":           round(max(closes), 2),
            "5yr_low":            round(min(closes), 2),
            "return_1_month_%":   ret(closes, 21),
            "return_3_month_%":   ret(closes, 63),
            "return_6_month_%":   ret(closes, 126),
            "return_1_year_%":    ret(closes, 252),
            "return_3_year_%":    ret(closes, 756),
            "return_5_year_%":    ret(closes, 1260),
            "avg_volume_30d":     int(sum(volumes[-30:]) / min(30, len(volumes))) if volumes else "N/A",
            "price_vs_ma50":      "above" if ma50  and closes[-1] > ma50  else "below",
            "price_vs_ma200":     "above" if ma200 and closes[-1] > ma200 else "below",
        }

        return {
            "status":             "success",
            "source":             "Yahoo Finance",
            "csv_saved_to":       csv_path,
            "symbol":             ticker_yf,
            "total_trading_days": len(records),
            "date_range": {
                "from": records[0]["Date"],
                "to":   records[-1]["Date"],
            },
            "technical_indicators": technical,
            "yearly_summary":       yearly,
            "recent_60_days":       records[-60:],
        }

    except Exception as e:
        return {"status": "error", "source": "Yahoo Finance", "message": str(e)}


# ─────────────────────────────────────────
# 3. NEWS FETCH (Google News RSS)
# ─────────────────────────────────────────

def get_news(stock_name: str, ticker: str, max_articles: int = 10) -> dict:
    clean_ticker = ticker.replace(".NS", "").replace(".BO", "")

    search_queries = [
        f"{stock_name} stock NSE",
        f"{clean_ticker} share price results",
        f"{stock_name} quarterly earnings",
    ]

    relevant_keywords = [
        clean_ticker.lower(),
        stock_name.lower(),
        stock_name.split()[0].lower(),
    ]

    all_articles = []
    seen_titles = set()

    for query in search_queries:
        try:
            encoded = quote_plus(query)
            url = f"https://news.google.com/rss/search?q={encoded}&hl=en-IN&gl=IN&ceid=IN:en"
            feed = feedparser.parse(url)

            for entry in feed.entries[:8]:
                title   = entry.get("title", "")
                summary = entry.get("summary", "")
                if not title or title in seen_titles:
                    continue
                if any(kw in title.lower() or kw in summary.lower() for kw in relevant_keywords):
                    seen_titles.add(title)
                    all_articles.append({
                        "title":     title,
                        "summary":   summary[:400],
                        "published": entry.get("published", ""),
                        "link":      entry.get("link", ""),
                        "source":    "Google News",
                    })

            time.sleep(0.5)
            if len(all_articles) >= max_articles:
                break

        except Exception as e:
            print(f"[News Error] {e}")

    return {
        "status":         "success",
        "total_articles": len(all_articles),
        "fetched_at":     datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "articles":       all_articles[:max_articles],
    }


# ─────────────────────────────────────────
# 4. MASTER FETCH FUNCTION
# ─────────────────────────────────────────

def fetch_all(ticker: str, stock_name: str = None, csv_path: str = "stock_data.csv") -> dict:
    """
    Master function. Fetches everything and returns shared JSON context.
    ticker:     "TCS.NS" or "TCS"
    stock_name: "Tata Consultancy Services"
    csv_path:   Path to save historical CSV (default: stock_data.csv)
    """
    symbol = ticker.replace(".NS", "").replace(".BO", "").upper()

    print(f"[1/3] Fetching Screener.in fundamentals for {symbol}...")
    stock_data = get_screener_data(symbol)

    if not stock_name:
        stock_name = stock_data["basic"].get("name", ticker) if stock_data["status"] == "success" else ticker

    print(f"[2/3] Downloading 5yr historical data from Yahoo Finance → {csv_path}...")
    historical_data = get_historical_data(symbol, csv_path=csv_path)

    print(f"[3/3] Fetching news for: {stock_name}...")
    news_data = get_news(stock_name, ticker)

    shared_context = {
        "ticker":          ticker,
        "stock_name":      stock_name,
        "fetched_at":      datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "stock_data":      stock_data,
        "historical_data": historical_data,
        "news_data":       news_data,
    }

    print(f"\n✅ Fetch Complete!")
    print(f"   Fundamentals : {stock_data['status']}")
    print(f"   Historical   : {historical_data['status']} | CSV: {csv_path}")
    print(f"   News         : {news_data['total_articles']} articles")

    if historical_data["status"] == "success":
        tech = historical_data["technical_indicators"]
        print(f"\n── Technical Summary ──")
        print(f"   Price    : ₹{tech['current_price']}")
        print(f"   MA50/200 : {tech['ma_50']} / {tech['ma_200']}")
        print(f"   RSI(14)  : {tech['rsi_14']}")
        print(f"   1Y Ret   : {tech['return_1_year_%']}%")
        print(f"   5Y Ret   : {tech['return_5_year_%']}%")
        print(f"   vs MA50  : {tech['price_vs_ma50']}")
        print(f"   vs MA200 : {tech['price_vs_ma200']}")

    return shared_context


# ─────────────────────────────────────────
# 5. TEST
# ─────────────────────────────────────────

if __name__ == "__main__":
    result = fetch_all("TCS.NS", "Tata Consultancy Services", csv_path="stock_data.csv")

    # Save full JSON
    with open("test_output.json", "w") as f:
        json.dump(result, f, indent=2)
    print("\n✅ Full JSON saved to test_output.json")
    print("✅ Historical CSV saved to stock_data.csv")