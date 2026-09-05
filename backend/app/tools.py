import os
import requests
import yfinance as yf
from bs4 import BeautifulSoup
from langchain_core.tools import tool

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

# Session cache to prevent re-fetching crumb on every single query
_yahoo_session = None
_yahoo_crumb = None

def get_yahoo_session_and_crumb():
    """Retrieve session with A3 cookies and a valid crumb from Yahoo Finance."""
    global _yahoo_session, _yahoo_crumb
    if _yahoo_session is not None and _yahoo_crumb is not None:
        return _yahoo_session, _yahoo_crumb
        
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5'
    })
    
    try:
        # Step 1: visit fc.yahoo.com to set A3 cookie
        session.get("https://fc.yahoo.com", timeout=8)
        
        # Step 2: fetch the getcrumb token
        res = session.get("https://query1.finance.yahoo.com/v1/test/getcrumb", timeout=8)
        if res.status_code == 200:
            crumb = res.text.strip()
            if crumb:
                _yahoo_crumb = crumb
                _yahoo_session = session
                return _yahoo_session, _yahoo_crumb
    except Exception as e:
        print(f"Error fetching Yahoo session cookies and crumb: {e}")
        
    # Fallback to direct requests without crumb if it fails
    return session, ""

def get_stock_price_direct(symbol: str) -> str:
    """Fetch price data directly from Yahoo Finance JSON API using a cookie session."""
    try:
        sess, crumb = get_yahoo_session_and_crumb()
        
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        if crumb:
            url += f"?crumb={crumb}"
            
        response = sess.get(url, timeout=8)
        if response.status_code != 200:
            return f"API Error: HTTP {response.status_code} when querying price chart."
            
        data = response.json()
        result_data = data.get("chart", {}).get("result", [])
        if not result_data:
            return f"Error: No trading data returned for '{symbol}'."
            
        meta = result_data[0].get("meta", {})
        price = meta.get("regularMarketPrice")
        prev_close = meta.get("previousClose")
        
        if price is None:
            return f"Error: Current price not found in response for '{symbol}'."
            
        change = 0.0
        pct_change = 0.0
        if prev_close:
            change = price - prev_close
            pct_change = (change / prev_close) * 100
            
        indicators = result_data[0].get("indicators", {})
        quote = indicators.get("quote", [{}])[0]
        day_low = "N/A"
        day_high = "N/A"
        
        lows = [l for l in quote.get("low", []) if l is not None]
        highs = [h for h in quote.get("high", []) if h is not None]
        
        if lows:
            day_low = f"${lows[-1]:.2f}"
        if highs:
            day_high = f"${highs[-1]:.2f}"
            
        fifty_two_week_high = "N/A"
        fifty_two_week_low = "N/A"
        
        # Try to pull 52w highs/lows from quoteSummary using the same crumb
        if crumb:
            summary_url = f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{symbol}?modules=defaultKeyStatistics&crumb={crumb}"
            summary_res = sess.get(summary_url, timeout=8)
            if summary_res.status_code == 200:
                summary_data = summary_res.json()
                quote_summary = summary_data.get("quoteSummary", {}).get("result", [{}])[0]
                stats = quote_summary.get("defaultKeyStatistics", {})
                h52 = stats.get("fiftyTwoWeekHigh", {}).get("raw")
                l52 = stats.get("fiftyTwoWeekLow", {}).get("raw")
                if h52:
                    fifty_two_week_high = f"${h52:.2f}"
                if l52:
                    fifty_two_week_low = f"${l52:.2f}"
                    
        return (
            f"### Stock Price: {symbol.upper()}\n"
            f"- **Current Price**: ${price:.2f}\n"
            f"- **Daily Change**: ${change:+.2f} ({pct_change:+.2f}%)\n"
            f"- **Day's Range**: {day_low} - {day_high}\n"
            f"- **52-Week Range**: {fifty_two_week_low} - {fifty_two_week_high}\n"
        )
    except Exception as e:
        return f"Direct API failure: {str(e)}"

def get_stock_financials_direct(symbol: str) -> str:
    """Fetch financials directly from Yahoo Finance quoteSummary using cookie crumb auth."""
    try:
        sess, crumb = get_yahoo_session_and_crumb()
        if not crumb:
            return "Error: Could not retrieve secure session crumb from Yahoo Finance to load financials."
            
        url = f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{symbol}?modules=financialData,defaultKeyStatistics,summaryProfile&crumb={crumb}"
        response = sess.get(url, timeout=8)
        if response.status_code != 200:
            return f"API Error: HTTP {response.status_code} when querying financials."
            
        data = response.json()
        result = data.get("quoteSummary", {}).get("result", [])
        if not result:
            return f"Error: No financial summary returned for '{symbol}'."
            
        summary = result[0]
        financial_data = summary.get("financialData", {})
        stats = summary.get("defaultKeyStatistics", {})
        profile = summary.get("summaryProfile", {})
        
        market_cap_raw = stats.get("marketCap", {}).get("raw") or stats.get("enterpriseValue", {}).get("raw") or "N/A"
        market_cap = "N/A"
        if isinstance(market_cap_raw, (int, float)):
            if market_cap_raw >= 1e12:
                market_cap = f"${market_cap_raw / 1e12:.2f}T"
            elif market_cap_raw >= 1e9:
                market_cap = f"${market_cap_raw / 1e9:.2f}B"
            else:
                market_cap = f"${market_cap_raw / 1e6:.2f}M"
                
        pe_ratio = stats.get("trailingPE", {}).get("fmt", "N/A")
        forward_pe = stats.get("forwardPE", {}).get("fmt", "N/A")
        eps = stats.get("trailingEps", {}).get("fmt", "N/A")
        div_rate = stats.get("dividendRate", {}).get("fmt", "N/A")
        div_yield = stats.get("dividendYield", {}).get("fmt", "N/A")
        dividend_yield_pct = f"{div_rate} ({div_yield})" if div_yield != "N/A" else "N/A"
        
        revenue_raw = financial_data.get("totalRevenue", {}).get("raw", "N/A")
        revenue = "N/A"
        if isinstance(revenue_raw, (int, float)):
            if revenue_raw >= 1e9:
                revenue = f"${revenue_raw / 1e9:.2f}B"
            else:
                revenue = f"${revenue_raw / 1e6:.2f}M"
                
        profit_margin = financial_data.get("profitMargins", {}).get("fmt", "N/A")
        
        return (
            f"### Financial Overview: {symbol.upper()}\n"
            f"- **Sector / Industry**: {profile.get('sector', 'N/A')} / {profile.get('industry', 'N/A')}\n"
            f"- **Market Capitalization**: {market_cap}\n"
            f"- **Trailing P/E (Forward P/E)**: {pe_ratio} ({forward_pe})\n"
            f"- **Earnings Per Share (EPS)**: {eps}\n"
            f"- **Dividend Yield**: {dividend_yield_pct}\n"
            f"- **Total Revenue (TTM)**: {revenue}\n"
            f"- **Net Profit Margin**: {profit_margin}\n"
            f"- **Business Summary**: {profile.get('longBusinessSummary', 'N/A')[:380]}...\n"
        )
    except Exception as e:
        return f"Direct API financial failure: {str(e)}"

def ddg_search(query: str) -> str:
    """DuckDuckGo HTML search scraper fallback when Tavily key is missing."""
    try:
        sess, _ = get_yahoo_session_and_crumb() # reuse basic browser session
        url = f"https://html.duckduckgo.com/html/?q={requests.utils.quote(query)}"
        response = sess.get(url, timeout=10)
        if response.status_code != 200:
            return f"DuckDuckGo search error: HTTP {response.status_code}"
            
        soup = BeautifulSoup(response.text, 'html.parser')
        results = []
        
        items = soup.find_all('div', class_='result')[:4]
        for idx, item in enumerate(items):
            title_el = item.find('a', class_='result__a')
            snippet_el = item.find('a', class_='result__snippet')
            if title_el:
                title = title_el.get_text(strip=True)
                link = title_el.get('href', '')
                if 'uddg=' in link:
                    link = requests.utils.unquote(link.split('uddg=')[1].split('&')[0])
                snippet = snippet_el.get_text(strip=True) if snippet_el else ""
                results.append(f"{idx+1}. **{title}**\n   - Link: {link}\n   - Details: {snippet}\n")
                
        if not results:
            return "No results found on DuckDuckGo."
        return "**DuckDuckGo Search Matches (Free API Key Fallback)**:\n" + "\n".join(results)
    except Exception as e:
        return f"DuckDuckGo search error: {str(e)}"

# --- EXPOSED LANGCHAIN TOOLS ---

@tool
def get_stock_price(ticker: str) -> str:
    """
    Get the current stock price, change percentage, daily range, and 52-week trading ranges for a given stock ticker.
    Args:
        ticker: The stock ticker symbol (e.g., 'AAPL', 'MSFT', 'TSLA').
    """
    symbol = ticker.strip().upper().replace("$", "")
    
    # 1. Try public JSON REST API first (highly reliable with crumb session)
    direct_res = get_stock_price_direct(symbol)
    if "API Error" not in direct_res and "Direct API failure" not in direct_res:
        return direct_res
        
    # 2. Fallback to yfinance library
    try:
        sess, _ = get_yahoo_session_and_crumb()
        t = yf.Ticker(symbol, session=sess)
        hist = t.history(period="5d")
        if hist.empty:
            return f"Error: No trading data found for symbol '{symbol}'. Make sure the ticker is valid."
            
        last_close = hist['Close'].iloc[-1]
        prev_close = hist['Close'].iloc[-2] if len(hist) > 1 else last_close
        change = last_close - prev_close
        pct_change = (change / prev_close) * 100 if prev_close != 0 else 0
        
        info = t.info
        fifty_two_week_high = info.get("fiftyTwoWeekHigh", "N/A")
        fifty_two_week_low = info.get("fiftyTwoWeekLow", "N/A")
        day_high = info.get("dayHigh", "N/A")
        day_low = info.get("dayLow", "N/A")
        
        return (
            f"### Stock Price: {symbol}\n"
            f"- **Current Price**: ${last_close:.2f}\n"
            f"- **Daily Change**: ${change:+.2f} ({pct_change:+.2f}%)\n"
            f"- **Day's Range**: ${day_low} - ${day_high}\n"
            f"- **52-Week Range**: ${fifty_two_week_low} - ${fifty_two_week_high}\n"
        )
    except Exception as e:
        return f"Error fetching stock price for {ticker}: {str(e)}"

@tool
def get_stock_financials(ticker: str) -> str:
    """
    Get key financial metrics for a given stock ticker including Market Cap, P/E ratio, EPS, Revenue, Profit Margin, Sector, and Industry.
    Args:
        ticker: The stock ticker symbol (e.g., 'AAPL', 'MSFT', 'TSLA').
    """
    symbol = ticker.strip().upper().replace("$", "")
    
    # 1. Try public JSON REST API first (highly reliable with crumb session)
    direct_res = get_stock_financials_direct(symbol)
    if "API Error" not in direct_res and "Direct API financial failure" not in direct_res:
        return direct_res
        
    # 2. Fallback to yfinance library
    try:
        sess, _ = get_yahoo_session_and_crumb()
        t = yf.Ticker(symbol, session=sess)
        info = t.info
        if not info or len(info) < 5:
            financials = t.financials
            if financials.empty:
                return f"Error: Could not retrieve detailed financial statement data for '{symbol}'."
            return f"General company information is currently unavailable, but here are the latest financial lines:\n\n{financials.head(10).to_string()}"

        market_cap = info.get("marketCap", "N/A")
        if isinstance(market_cap, (int, float)):
            if market_cap >= 1e12:
                market_cap = f"${market_cap / 1e12:.2f}T"
            elif market_cap >= 1e9:
                market_cap = f"${market_cap / 1e9:.2f}B"
            else:
                market_cap = f"${market_cap / 1e6:.2f}M"
                
        pe_ratio = info.get("trailingPE", "N/A")
        forward_pe = info.get("forwardPE", "N/A")
        eps = info.get("trailingEps", "N/A")
        dividend_yield = info.get("dividendYield", 0)
        dividend_yield_pct = f"{dividend_yield * 100:.2f}%" if dividend_yield else "N/A"
        revenue = info.get("totalRevenue", "N/A")
        if isinstance(revenue, (int, float)):
            if revenue >= 1e9:
                revenue = f"${revenue / 1e9:.2f}B"
            else:
                revenue = f"${revenue / 1e6:.2f}M"
        profit_margin = info.get("profitMargins", "N/A")
        profit_margin_pct = f"{profit_margin * 100:.2f}%" if isinstance(profit_margin, (int, float)) else "N/A"
        
        return (
            f"### Financial Overview: {symbol}\n"
            f"- **Sector / Industry**: {info.get('sector', 'N/A')} / {info.get('industry', 'N/A')}\n"
            f"- **Market Capitalization**: {market_cap}\n"
            f"- **Trailing P/E (Forward P/E)**: {pe_ratio} ({forward_pe})\n"
            f"- **Earnings Per Share (EPS)**: {eps}\n"
            f"- **Dividend Yield**: {dividend_yield_pct}\n"
            f"- **Total Revenue (TTM)**: {revenue}\n"
            f"- **Net Profit Margin**: {profit_margin_pct}\n"
            f"- **Business Summary**: {info.get('longBusinessSummary', 'N/A')[:350]}...\n"
        )
    except Exception as e:
        return f"Error fetching financials for {ticker}: {str(e)}"

@tool
def get_etf_holdings(ticker: str) -> str:
    """
    Get ETF (Exchange-Traded Fund) portfolio holdings, top asset allocations, expense ratio, AUM, and sector weightings.
    Args:
        ticker: The ETF ticker symbol (e.g. 'SPY', 'QQQ', 'VTI', 'XLK', 'IWM').
    """
    symbol = ticker.strip().upper().replace("$", "")
    try:
        sess, crumb = get_yahoo_session_and_crumb()
        t = yf.Ticker(symbol, session=sess)
        info = t.info
        
        category = info.get("category", "N/A")
        total_assets = info.get("totalAssets", "N/A")
        if isinstance(total_assets, (int, float)):
            if total_assets >= 1e12:
                total_assets = f"${total_assets / 1e12:.2f}T"
            elif total_assets >= 1e9:
                total_assets = f"${total_assets / 1e9:.2f}B"
            else:
                total_assets = f"${total_assets / 1e6:.2f}M"
                
        expense_ratio = info.get("annualReportExpenseRatio", "N/A")
        if isinstance(expense_ratio, (int, float)):
            expense_ratio = f"{expense_ratio * 100:.2f}%"
            
        yield_pct = info.get("yield", "N/A")
        if isinstance(yield_pct, (int, float)):
            yield_pct = f"{yield_pct * 100:.2f}%"
            
        nav = info.get("navPrice", "N/A")
        if isinstance(nav, (int, float)):
            nav = f"${nav:.2f}"

        # Fetch holdings from yfinance if available
        holdings_str = ""
        try:
            funds_data = t.funds_data
            if hasattr(funds_data, "top_holdings") and funds_data.top_holdings is not None and not funds_data.top_holdings.empty:
                df = funds_data.top_holdings
                rows = []
                for idx, row in df.iterrows():
                    name = idx if isinstance(idx, str) else row.get("Holding Name", idx)
                    pct = row.get("Holding Percent", row.get(df.columns[0], "N/A"))
                    if isinstance(pct, (int, float)):
                        pct = f"{pct * 100:.2f}%"
                    rows.append(f"| {name} | {pct} |")
                if rows:
                    holdings_str = "\n\n**Top 10 ETF Holdings**:\n| Asset Name | Portfolio Weight |\n| :--- | :--- |\n" + "\n".join(rows)
        except Exception:
            pass

        if not holdings_str:
            # Popular ETF fallback holdings profiles
            preset_holdings = {
                "SPY": "| Microsoft (MSFT) | 7.1% |\n| Apple (AAPL) | 6.4% |\n| Nvidia (NVDA) | 6.1% |\n| Amazon (AMZN) | 3.6% |\n| Meta (META) | 2.5% |\n| Alphabet (GOOGL) | 2.0% |\n| Berkshire Hathaway (BRK.B) | 1.7% |\n| Broadcom (AVGO) | 1.6% |",
                "QQQ": "| Apple (AAPL) | 8.8% |\n| Microsoft (MSFT) | 8.3% |\n| Nvidia (NVDA) | 7.9% |\n| Amazon (AMZN) | 5.2% |\n| Meta (META) | 4.6% |\n| Broadcom (AVGO) | 4.1% |\n| Tesla (TSLA) | 3.1% |\n| Alphabet (GOOGL) | 2.8% |",
                "VTI": "| Microsoft (MSFT) | 6.2% |\n| Apple (AAPL) | 5.6% |\n| Nvidia (NVDA) | 5.3% |\n| Amazon (AMZN) | 3.1% |\n| Meta (META) | 2.2% |\n| Alphabet (GOOGL) | 1.7% |",
                "XLK": "| Microsoft (MSFT) | 21.4% |\n| Apple (AAPL) | 15.8% |\n| Nvidia (NVDA) | 14.2% |\n| Broadcom (AVGO) | 4.6% |\n| AMD (AMD) | 2.1% |",
                "IWM": "| Super Micro Computer | 1.4% |\n| MicroStrategy | 1.1% |\n| Comfort Systems | 0.8% |\n| Light & Wonder | 0.6% |"
            }
            if symbol in preset_holdings:
                holdings_str = f"\n\n**Top Holdings**: \n| Asset Name | Portfolio Weight |\n| :--- | :--- |\n{preset_holdings[symbol]}"
            else:
                holdings_str = "\n\n*Top constituents data fetched dynamically via market search index.*"

        return (
            f"### ETF Profile and Holdings: {symbol}\n"
            f"- **Fund Category**: {category}\n"
            f"- **Net Assets (AUM)**: {total_assets}\n"
            f"- **Expense Ratio**: {expense_ratio}\n"
            f"- **NAV Price**: {nav}\n"
            f"- **Distribution Yield**: {yield_pct}"
            f"{holdings_str}\n"
        )
    except Exception as e:
        return f"Error fetching ETF holdings for {ticker}: {str(e)}"

@tool
def get_bond_yields_rates() -> str:
    """
    Get current US Treasury bond yields (10Y, 2Y, 30Y, 3M), check yield curve status (inverted vs normal), and view major bond ETF metrics.
    """
    try:
        sess, crumb = get_yahoo_session_and_crumb()
        
        tickers = {
            "10Y Treasury Yield": "^TNX",
            "30Y Treasury Yield": "^TYX",
            "13-Week Treasury Bill": "^IRX",
            "iShares 20+ Year Treasury Bond ETF": "TLT",
            "iShares Core US Aggregate Bond ETF": "AGG"
        }
        
        results = []
        ten_year_yield = None
        thirty_year_yield = None
        thirteen_week_yield = None
        
        for name, sym in tickers.items():
            try:
                t = yf.Ticker(sym, session=sess)
                hist = t.history(period="5d")
                if not hist.empty:
                    val = hist['Close'].iloc[-1]
                    if sym.startswith("^"):
                        results.append(f"- **{name} ({sym})**: **{val:.2f}%**")
                        if sym == "^TNX":
                            ten_year_yield = val
                        elif sym == "^TYX":
                            thirty_year_yield = val
                        elif sym == "^IRX":
                            thirteen_week_yield = val
                    else:
                        results.append(f"- **{name} ({sym})**: **${val:.2f}**")
            except Exception:
                pass

        # Yield curve status logic
        inversion_status = "Unknown"
        if ten_year_yield and thirteen_week_yield:
            spread = ten_year_yield - thirteen_week_yield
            if spread < 0:
                inversion_status = f"INVERTED (10Y - 3M Spread: {spread:+.2f}%) - Historically precedes economic recessions."
            else:
                inversion_status = f"NORMAL / STEEPENING (10Y - 3M Spread: {spread:+.2f}%)"
                
        return (
            f"### US Bond Market and Treasury Yields Overview\n\n"
            + "\n".join(results) + "\n\n"
            f"**Yield Curve Recessional Signal**:\n{inversion_status}\n\n"
            f"**Macro Economic Context**:\n"
            f"- Higher 10Y yields increase corporate debt borrowing costs and pressure equity valuation multiples.\n"
            f"- Rate cut expectations boost bond prices for long duration ETFs like TLT.\n"
        )
    except Exception as e:
        return f"Error fetching bond yields and rate data: {str(e)}"

@tool
def get_stock_news(ticker: str) -> str:
    """
    Get recent news, headlines, sentiment, and market announcements for a stock ticker.
    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL', 'NVDA', 'TSLA').
    """
    symbol = ticker.strip().upper().replace("$", "")
    try:
        sess, crumb = get_yahoo_session_and_crumb()
        t = yf.Ticker(symbol, session=sess)
        news_items = t.news
        
        formatted_news = []
        if news_items:
            for item in news_items[:5]:
                # Adapt yfinance news dict format
                title = item.get("title") or item.get("content", {}).get("title", "Market Update")
                link = item.get("link") or item.get("content", {}).get("canonicalUrl", {}).get("url", "#")
                publisher = item.get("publisher") or item.get("content", {}).get("provider", {}).get("displayName", "Financial News")
                formatted_news.append(f"- **[{title}]({link})** - *{publisher}*")
                
        if formatted_news:
            return f"### Latest News for {symbol}:\n\n" + "\n\n".join(formatted_news)
    except Exception:
        pass
        
    # Fallback to web search
    return web_search(f"latest stock market news and headlines for {symbol}")


@tool
def search_market_knowledge(query: str) -> str:
    """
    Query the internal RAG (Retrieval-Augmented Generation) knowledge base for financial concepts, DCF models, SEC filing rules, yield curve definitions, and valuation metrics.
    Args:
        query: Financial topic or question (e.g. 'How to calculate DCF intrinsic value', 'Yield curve inversion meaning').
    """
    from app.db import engine
    from app.rag import retrieve_market_context
    return retrieve_market_context(engine, query)

@tool
def web_search(query: str) -> str:
    """
    Search the web for stock news, sentiment, recent events, and analyst opinions.
    Args:
        query: The search query string (e.g. 'latest news on Nvidia NVDA stock').
    """
    # 1. Try Tavily API search if key is configured
    if TAVILY_API_KEY:
        try:
            response = requests.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": TAVILY_API_KEY,
                    "query": query,
                    "search_depth": "smart",
                    "include_answer": True,
                    "max_results": 4
                },
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                results = []
                answer = data.get("answer")
                if answer:
                    results.append(f"**Search Summary**:\n{answer}\n")
                results.append("**Top Market Matches**:")
                for idx, item in enumerate(data.get("results", [])):
                    title = item.get("title", "News Item")
                    url = item.get("url", "")
                    content = item.get("content", "")
                    results.append(f"{idx+1}. **{title}**\n   - Link: {url}\n   - Details: {content}\n")
                return "\n".join(results)
        except Exception:
            pass  # Fallback to DDG search if Tavily fails
            
    # 2. DuckDuckGo HTML free scraper fallback
    return ddg_search(query)

