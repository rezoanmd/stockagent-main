# AI-Powered Stock Research Agent

An agentic stock research platform built with Python, FastAPI, LangChain, LangGraph, Next.js, React, and NeonDB PostgreSQL.

---

## Key Features

- **Agentic Live Market Data Tools**:
  - **Stock Prices**: Current prices, daily ranges, 52-week ranges, daily volume and percentage changes.
  - **Financial Statements**: Market Cap, P/E ratios, Forward P/E, EPS, TTM Revenue, Net Profit Margins, Sector/Industry info.
  - **ETF Holdings**: Top 10 constituents, portfolio weightings, AUM, expense ratios, distribution yields.
  - **Bond Market and US Treasuries**: 10-Year, 2-Year, 30-Year, 13-Week Treasury yields, yield curve inversion detection (10Y-3M spread), and bond ETF tracking (TLT, AGG).
  - **Stock News and Sentiment**: Real-time ticker news and financial publisher headlines.
  - **Web Search**: Tavily and DuckDuckGo search fallbacks.

- **LangGraph Workflows and Dynamic Tool Selection**:
  - ReAct state graph architecture enabling multi-step analysis and autonomous reasoning.
  - Transparent execution tracing: visualizes tool invocation steps (`tool_steps`) in real-time.

- **Market Knowledge RAG Pipeline**:
  - Pre-populated financial domain knowledge base (DCF Valuation models, SEC 10-K/10-Q filing rules, P/E benchmarks, Yield Curve dynamics).
  - Hybrid keyword and semantic relevance ranking.

- **Full-Stack Architecture and Multi-User DB**:
  - **FastAPI** backend with async database connection pool for NeonDB / SQLite.
  - **Next.js (React)** frontend with dark mode glassmorphism design, live market marquee, interactive Markdown tables, and code syntax highlighting.
  - **Authentication**: JWT token authentication with PBKDF2 password hashing and guest session fallbacks.

---

## Deployment

- **Backend**: Deployed on Render (`render.yaml` provided).
- **Frontend**: Deployed on Vercel (`vercel.json` provided).
- **Database**: NeonDB serverless PostgreSQL.

---

## Local Setup

### 1. Backend (FastAPI)
```bash
cd backend
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate

pip install -r requirements.txt

# Create .env file with:
# GEMINI_API_KEY=your_gemini_api_key
# TAVILY_API_KEY=your_tavily_api_key (optional)
# DATABASE_URL=your_neon_db_postgresql_url (optional, falls back to SQLite)

uvicorn app.main:app --reload --port 8000
```

### 2. Frontend (Next.js)
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:3000` in your browser.