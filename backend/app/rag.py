import json
import math
from typing import List, Dict, Any
from sqlalchemy import text

SEED_KNOWLEDGE_BASE = [
    {
        "category": "Valuation & DCF",
        "topic": "Discounted Cash Flow (DCF) Valuation",
        "content": (
            "Discounted Cash Flow (DCF) valuation calculates the intrinsic value of a company based on estimated future cash flows, "
            "discounted back to present value using the Weighted Average Cost of Capital (WACC). "
            "Key parameters include Terminal Growth Rate (typically 2-3%), Free Cash Flow to Firm (FCFF), and Beta for risk premium."
        ),
        "keywords": "dcf discounted cash flow intrinsic value wacc terminal growth fcf valuation target price"
    },
    {
        "category": "Valuation & DCF",
        "topic": "P/E, Forward P/E, and PEG Ratio Benchmarks",
        "content": (
            "The Price-to-Earnings (P/E) ratio measures current share price relative to per-share earnings. "
            "Forward P/E projects future 12-month earnings. The PEG ratio (P/E divided by annual EPS growth rate) adjusts for growth: "
            "a PEG below 1.0 suggests an undervalued stock relative to its earnings growth rate, while PEG above 2.0 indicates premium valuation."
        ),
        "keywords": "pe ratio forward pe peg ratio earnings multiple valuation growth rate eps undervalue overvalue"
    },
    {
        "category": "Fixed Income & Bonds",
        "topic": "US Treasury Yield Curve & Inversion Indicator",
        "content": (
            "The US Treasury Yield Curve plots yields of Treasury bonds across maturities (3-month, 2-year, 10-year, 30-year). "
            "A normal curve slopes upward. An inverted yield curve (where 2-year or 3-month yields exceed 10-year yields, e.g. 10Y-2Y spread < 0) "
            "has historically preceded US economic recessions by 6 to 18 months, signaling tightening credit conditions."
        ),
        "keywords": "bond yield treasury 10y 2y inversion inverted yield curve recession indicator interest rates fed spread"
    },
    {
        "category": "Fixed Income & Bonds",
        "topic": "Fed Interest Rate Cycles & Bond Prices",
        "content": (
            "Bond prices move inversely to market interest rates and Federal Reserve policy rates. "
            "When the Fed cuts interest rates, bond yields drop and existing bond prices rise (benefiting bond ETFs like TLT, AGG, BND). "
            "High duration long-term bonds (e.g. 20+ Year Treasuries) exhibit higher price sensitivity (volatility) to interest rate shifts than short duration bills."
        ),
        "keywords": "fed rate interest rates federal reserve duration bond prices rate cuts rate hikes tlt agg bnd yield"
    },
    {
        "category": "ETFs & Asset Allocation",
        "topic": "ETF Expense Ratios, Tracking Error, and Holdings Structure",
        "content": (
            "Exchange Traded Funds (ETFs) pool investor funds to track benchmark indices (e.g., SPY for S&P 500, QQQ for Nasdaq 100). "
            "Critical ETF metrics include: Net Asset Value (NAV), Expense Ratio (annual management fee percentage), Top 10 Holdings concentration percentage, "
            "and Tracking Error (variance between ETF performance and benchmark index)."
        ),
        "keywords": "etf holdings spy qqq expense ratio tracking error asset allocation nav portfolio sector weighting index"
    },
    {
        "category": "Financial Statement Analysis",
        "topic": "SEC 10-K & 10-Q Quarterly Report Metrics",
        "content": (
            "Public companies file Annual 10-K and Quarterly 10-Q reports with the US SEC. "
            "Key financial balance sheet indicators to assess solvency include: Net Debt / EBITDA ratio (leverage), Gross Profit Margins, Operating Profit Margin, "
            "Free Cash Flow Conversion, and Working Capital ratio. Red flags include rising accounts receivable relative to revenue growth."
        ),
        "keywords": "sec 10k 10q earnings report balance sheet debt ebitda profit margin gross margin cash flow solvency leverage"
    },
    {
        "category": "Macroeconomics & Markets",
        "topic": "Inflation (CPI/PCE) and Monetary Policy Impact",
        "content": (
            "The Federal Reserve targets a 2% annual inflation rate measured by Core PCE (Personal Consumption Expenditures). "
            "Elevated CPI/PCE inflation leads central banks to raise interest rates, suppressing stock valuation multiples (especially high-growth tech stocks) "
            "due to higher discount rates applied to future earnings."
        ),
        "keywords": "inflation cpi pce federal reserve monetary policy interest rates discount rate tech stocks growth valuation"
    }
]

def seed_market_knowledge(engine):
    """Seed default market knowledge into database if empty."""
    try:
        with engine.begin() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM market_knowledge")).scalar()
            if result == 0:
                for item in SEED_KNOWLEDGE_BASE:
                    conn.execute(
                        text("""
                        INSERT INTO market_knowledge (category, topic, content, keywords)
                        VALUES (:category, :topic, :content, :keywords)
                        """),
                        item
                    )
    except Exception as e:
        print(f"Error seeding market knowledge RAG database: {e}")

def simple_token_score(query: str, text_corpus: str) -> float:
    """Calculate token overlap and keyword match score for pure Python RAG ranking."""
    query_tokens = set(query.lower().split())
    if not query_tokens:
        return 0.0
        
    corpus_words = text_corpus.lower().split()
    corpus_set = set(corpus_words)
    
    matches = query_tokens.intersection(corpus_set)
    match_score = len(matches) / math.sqrt(len(query_tokens) * (len(corpus_set) + 1))
    
    # Exact substring boost
    for token in query_tokens:
        if len(token) > 2 and token in text_corpus.lower():
            match_score += 0.25
            
    return match_score

def retrieve_market_context(engine, query: str, top_k: int = 3) -> str:
    """
    RAG pipeline: Query NeonDB/SQLite market knowledge base and return relevant external knowledge context.
    """
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text("SELECT id, category, topic, content, keywords FROM market_knowledge")
            ).mappings().all()
            
        scored_rows = []
        for r in rows:
            combined = f"{r['category']} {r['topic']} {r['keywords']} {r['content']}"
            score = simple_token_score(query, combined)
            scored_rows.append((score, r))
            
        scored_rows.sort(key=lambda x: x[0], reverse=True)
        top_matches = [r for score, r in scored_rows[:top_k] if score > 0.05]
        
        if not top_matches:
            top_matches = [r for score, r in scored_rows[:top_k]]
            
        formatted_snippets = []
        for idx, match in enumerate(top_matches):
            formatted_snippets.append(
                f"### Knowledge Match {idx+1}: {match['topic']} [{match['category']}]\n"
                f"{match['content']}\n"
            )
            
        return "### External Market & Financial Knowledge (RAG Pipeline Context):\n\n" + "\n".join(formatted_snippets)
    except Exception as e:
        return f"RAG Retrieval Notice: Knowledge base query returned: {str(e)}"

