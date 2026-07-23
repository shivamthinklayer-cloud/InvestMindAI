# ⚡ InvestMind — AI Stock Analyzer

> **7 AI Models. Real Market Data. One Clear Verdict.**

InvestMind is an intelligent stock analysis engine that combines news sentiment, technical analysis, fundamental data, and 4 investment strategies to give you a clear, actionable verdict on any NSE-listed Indian stock.

---

## 🚀 Live Demo

**[https://investmind-ai.onrender.com](https://investmind-ai.onrender.com)**

---

## 📸 What It Does

You enter a stock name → InvestMind runs a full 8-step AI pipeline → You get a complete analysis report in ~60 seconds.

```
Input: TCS.NS + "Want to buy"
         ↓
[Step 1] Fetch stock data (Screener.in) + news (Google News RSS) + 5yr CSV (Yahoo Finance)
         ↓
[Step 2] News Sentiment Analysis        → Groq (Llama 3.1)
         ↓
[Step 3] Technical + Fundamental Analysis → Gemini 2.0 Flash + stock_data.csv
         ↓
[Step 4] Conservative Strategy          → Gemini 2.5 Flash Lite
[Step 5] Growth Strategy                → Gemini 2.5 Flash Lite
[Step 6] Emotional/Momentum Strategy    → Gemini 2.5 Flash Lite
[Step 7] Value Strategy                 → Gemini 2.5 Flash Lite
         ↓
[Step 8] Final Verdict                  → Groq (DeepSeek R1)
         ↓
Output: STRONG BUY / BUY / HOLD / SELL / STRONG SELL
```

---

## 🧠 AI Pipeline Architecture

| API | Task | Model | Platform |
|-----|------|-------|----------|
| API 1 | News Sentiment Analysis | Llama 3.1 8B | Groq |
| API 2 | Technical + Fundamental Analysis | Gemini 2.0 Flash | Google AI Studio |
| API 3 | Conservative Strategy | Gemini 2.5 Flash Lite | Google AI Studio |
| API 4 | Growth Strategy | Gemini 2.5 Flash Lite | Google AI Studio |
| API 5 | Emotional/Momentum Strategy | Gemini 2.5 Flash Lite | Google AI Studio |
| API 6 | Value Strategy | Gemini 2.5 Flash Lite | Google AI Studio |
| API 7 | Final Verdict | DeepSeek R1 | Groq |

---

## 📊 Data Sources

| Source | Data | Cost |
|--------|------|------|
| **Screener.in** | PE, ROE, ROCE, Debt/Equity, Quarterly results, Pros/Cons | Free |
| **Yahoo Finance** | 5 years daily OHLCV → saved as `stock_data.csv` | Free |
| **Google News RSS** | Latest 10-15 news articles | Free |

---

## 🔬 Technical Indicators Calculated

From `stock_data.csv` (pure Python, no TA library needed):

- **Moving Averages** — MA20, MA50, MA200, EMA12, EMA26
- **Momentum** — RSI(14), MACD, Stochastic %K/%D
- **Volatility** — Bollinger Bands(20,2), ATR(14)
- **Volume** — OBV, Avg Volume 20d/50d, Volume Signal
- **Trend** — Golden Cross / Death Cross detection
- **Support & Resistance** — 20-day levels
- **Returns** — 1M, 3M, 6M, 1Y, 3Y, 5Y %

---

## 📈 Investment Strategies

| Strategy | Focus | Investor Type |
|----------|-------|--------------|
| **Conservative** | Safety, dividends, low debt | Risk-averse, retirees |
| **Growth** | Revenue growth, earnings expansion | Young investors, 3-5yr horizon |
| **Emotional/Momentum** | RSI, MACD, news sentiment | Short-term traders |
| **Value** | PE/PB ratios, intrinsic value, margin of safety | Patient, long-term |

---

## 🛠️ Tech Stack

```
Backend   → Python + Flask
AI Models → Groq API + Google Gemini API
Data      → Screener.in + Yahoo Finance + Google News RSS
Frontend  → HTML + CSS + Vanilla JavaScript
Hosting   → Render (free tier)
```

---

## 📁 Project Structure

```
InvestMind/
├── render.yaml               # Render deployment config
└── backend/
    ├── main.py               # Flask server (serves frontend + API)
    ├── pipeline.py           # Master pipeline connecting all APIs
    ├── data_fetch.py         # Data fetching (Screener + Yahoo + News)
    ├── api1_sentiment.py     # News sentiment analysis (Groq)
    ├── api2_fundamental.py   # Technical + fundamental analysis (Gemini)
    ├── api3_6_strategy.py    # 4 strategy analyses (Gemini)
    ├── api7_verdict.py       # Final verdict (Groq DeepSeek R1)
    ├── index.html            # Frontend UI
    ├── requirements.txt      # Python dependencies
    └── .env                  # API keys (never commit this!)
```

---

## ⚙️ Local Setup

### 1. Clone the repo
```bash
git clone https://github.com/kashif-kairo/InvestMind_AI.git
cd InvestMind_AI/backend
```

### 2. Create virtual environment
```bash
python -m venv myenv
myenv\Scripts\activate        # Windows
source myenv/bin/activate     # Mac/Linux
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Create `.env` file in `backend/`
```env
GROQ_API_KEY=your_groq_api_key
GEMINI_API_KEY=your_gemini_api_key
OPENROUTER_API_KEY=your_openrouter_api_key
```

### 5. Get free API keys

| Platform | Link | Free Limit |
|----------|------|------------|
| Groq | [console.groq.com](https://console.groq.com) | 14,400 req/day |
| Google AI Studio | [aistudio.google.com](https://aistudio.google.com) | 1,500 req/day |
| OpenRouter | [openrouter.ai](https://openrouter.ai) | Free credits |

### 6. Run
```bash
python main.py
```

Browser opens automatically at **http://localhost:5000** 🚀

---

## 🌐 Deployment (Render)

1. Push code to GitHub
2. Go to [render.com](https://render.com) → New Web Service
3. Connect GitHub repo
4. Set:
   - **Root Directory**: `backend`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn main:app --bind 0.0.0.0:$PORT --timeout 300 --workers 1`
5. Add environment variables (API keys)
6. Deploy ✅

---

## 📱 Frontend Features

- 🔍 Stock input with quick-pick chips (RELIANCE, INFY, HDFCBANK...)
- ⏳ Live loading with step-by-step pipeline progress
- 🎯 Color-coded verdict banner (STRONG BUY → STRONG SELL)
- 📊 Strategy votes from all 4 AI strategies
- 📈 Historical returns (1M, 3M, 6M, 1Y, 3Y, 5Y)
- 🎯 Price targets (short-term, long-term, stop loss)
- 🐂 Bull case vs Bear case
- ⚠️ Key catalysts and key risks
- 📉 Technical indicators display
- 💰 Fundamental ratios

---

## 🎯 Sentiment Scoring System

```
Score 7-10 / 10  →  GOOD     (positive news dominates)
Score 4-6  / 10  →  NEUTRAL  (mixed sentiment)
Score 0-3  / 10  →  BAD      (negative news dominates)
```

---

## ⚖️ Final Verdict Weighting

```
Value Strategy       → 30%
Conservative         → 25%
Growth               → 25%
Emotional/Momentum   → 20%
Sentiment Adjustment → ±0.5 bonus/penalty
```

---

## ⚠️ Disclaimer

> InvestMind is an educational AI project. It does **not** provide financial advice. Always do your own research and consult a SEBI-registered financial advisor before investing. Past performance does not guarantee future returns.

---

## 👨‍💻 Developer

**Kashif** — Built as a Final year Colleage project.

- GitHub: [@kashif-kairo](https://github.com/kashif-kairo)

---

## 📄 License

MIT License — free to use, modify, and distribute.

---

*Built with ❤️ using Python, Flask, and 7 free AI models*
