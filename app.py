from fastapi import FastAPI, Query,Body, HTTPException
from typing import Optional
import uvicorn
from pathlib import Path

from fastapi.middleware.cors import CORSMiddleware



# Import your existing earnings scraper
from scrapers.earnings_scraper import AlphaStreetScraper

# Import the new financial scraper
from scrapers.financial_scraper import YahooFinanceScraper

import logging

import asyncio
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor()

async def run_scraper_in_thread(scraper, ticker, force_scrape=False):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        executor,
        lambda: scraper.scrape_financial_reports(ticker, force_scrape)
    )

async def run_market_data_in_thread(scraper, ticker, force_scrape=False):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        executor,
        lambda: scraper.get_market_data(ticker, force_scrape)
    )

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

app = FastAPI(title="Combined Financial API", description="Earnings Calls + Financial Reports")


origins = [
    "http://localhost:3000",  # Next.js frontend
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,        # or ["*"] for dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Initialize scrapers
earnings_scraper = AlphaStreetScraper()
financial_scraper = YahooFinanceScraper(cache_dir="data/financials")


# ==================== Earnings Call Endpoints (Your existing ones) ====================

# ==================== API Endpoints ====================

@app.get("/")
async def root():
    return {
        "status": "AlphaStreet Transcript Scraper API running 🚀",
        "version": "3.0.0",
        "endpoints": {
            "GET /scrape/{ticker}/{year}/{quarter}": "Find and scrape transcript by ticker, year, and quarter",
            "GET /scrape": "Scrape a transcript by URL (provide url param)",
            "POST /scrape": "Scrape a transcript by URL (POST with body)",
            "POST /scrape/batch": "Scrape multiple transcripts by ticker/year/quarter",
            "GET /search": "Search for transcript URL without scraping",
            "GET /health": "Health check"
        }
    }


@app.get("/scrape/{ticker}/{year}/{quarter}")
async def scrape_by_ticker_quarter(
    ticker: str,
    year: int,
    quarter: str
):
    """
    Find and scrape transcript by ticker, year, and quarter
    
    Example: /scrape/aapl/2026/Q1
    """
    try:
        result = earnings_scraper.scrape_by_ticker_quarter(ticker, year, quarter)
        
        if result.get('success'):
            data = result.get('data', {})
            
            return {
                "success": True,
                "url": result.get('url'),
                "stats": {
                    "presentation_speeches": len(data.get('presentation', [])),
                    "qa_speeches": len(data.get('qa_session', []))
                },
                "presentation": data.get('presentation', []),
                "qa_session": data.get('qa_session', []),
                "participants": data.get('participants', {}),
                "metadata": {
                    "title": data.get('title'),
                    "company": data.get('company'),
                    "ticker": data.get('ticker'),
                    "quarter": data.get('quarter'),
                    "year": data.get('year'),
                    "date": data.get('date'),
                    "transcript_type": data.get('transcript_type')
                }
            }
        else:
            raise HTTPException(status_code=404, detail=result.get('error', 'Transcript not found'))
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/scrape")
async def scrape_by_url(url: str = Query(..., description="Direct URL of the AlphaStreet transcript")):
    """Scrape a transcript by direct URL"""
    try:
        data = earnings_scraper.scrape_from_url(url)

        if not data:
            return {"success": False, "error": "Scraping failed - check if URL is valid"}

        return {
            "success": True,
            "presentation": data.get('presentation', []),
            "qa_session": data.get('qa_session', []),
            "participants": data.get('participants', {}),
            "metadata": {
                "title": data.get('title'),
                "company": data.get('company'),
                "ticker": data.get('ticker'),
                "quarter": data.get('quarter'),
                "year": data.get('year'),
                "date": data.get('date'),
                "transcript_type": data.get('transcript_type')
            }
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/scrape")
async def scrape_post(payload: dict = Body(...)):
    """Scrape a transcript by URL (POST method)"""
    url = payload.get("url")
    
    if not url:
        return {"success": False, "error": "URL is required"}
    
    return await scrape_by_url(url)


@app.post("/scrape/batch")
async def scrape_batch(payload: dict = Body(...)):
    """
    Scrape multiple transcripts by ticker/year/quarter
    """
    transcripts = payload.get("transcripts", [])
    
    if not transcripts:
        return {"success": False, "error": "No transcripts provided"}
    
    results = []
    for transcript in transcripts:
        ticker = transcript.get("ticker")
        year = transcript.get("year")
        quarter = transcript.get("quarter")
        
        if not all([ticker, year, quarter]):
            results.append({
                "ticker": ticker,
                "quarter": quarter,
                "year": year,
                "success": False,
                "error": "Missing required fields (ticker, year, quarter)"
            })
            continue
        
        result = earnings_scraper.scrape_by_ticker_quarter(ticker, year, quarter)
        results.append(result)
    
    return {
        "success": True,
        "total": len(results),
        "successful": len([r for r in results if r.get('success')]),
        "failed": len([r for r in results if not r.get('success')]),
        "results": results
    }


@app.get("/search")
async def search_transcripts(
    ticker: str = Query(..., description="Stock ticker symbol"),
    year: int = Query(..., description="Year (e.g., 2026)"),
    quarter: str = Query(..., description="Quarter (Q1, Q2, Q3, Q4)")
):
    """Search for a transcript URL without scraping it"""
    try:
        transcript_url = earnings_scraper.find_transcript_url(ticker, year, quarter)
        
        if transcript_url:
            return {
                "success": True,
                "ticker": ticker,
                "year": year,
                "quarter": quarter,
                "url": transcript_url
            }
        else:
            raise HTTPException(status_code=404, detail=f"No transcript found for {ticker} {quarter} {year}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/transcripts")
async def list_transcripts(
    ticker: str = Query(..., description="Stock ticker symbol (e.g., AAPL)"),
    year: Optional[int] = Query(None, description="Year (e.g., 2026)"),
    quarter: Optional[str] = Query(None, description="Quarter (Q1, Q2, Q3, Q4)")
):
    """
    Get list of available transcripts for a ticker
    
    Examples:
    /transcripts?ticker=AAPL
    /transcripts?ticker=AAPL&year=2026
    /transcripts?ticker=AAPL&year=2026&quarter=Q1
    """
    try:
        transcripts = earnings_scraper.list_transcripts(
            ticker=ticker,
            year=year,
            quarter=quarter
        )

        if not transcripts:
            return {
                "success": False,
                "message": "No transcripts found",
                "ticker": ticker.upper(),
                "year": year,
                "quarter": quarter,
                "count": 0,
                "data": []
            }

        return {
            "success": True,
            "ticker": ticker.upper(),
            "year": year,
            "quarter": quarter,
            "count": len(transcripts),
            "data": transcripts
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== New Financial Report Endpoints ====================



@app.get("/financials/{ticker}")
async def get_financial_reports(ticker: str, force_scrape: bool = False):
    try:
        result = await run_scraper_in_thread(financial_scraper, ticker, force_scrape)
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@app.get("/market-data/{ticker}")
async def get_market_data(ticker: str, force_scrape: bool = False):
    """
    Get stock prices + key metrics + earnings (Yahoo Finance)

    Example:
    /market-data/AAPL
    /market-data/MS?force_scrape=true
    """
    try:
        result = await run_market_data_in_thread(
            financial_scraper, ticker, force_scrape
        )

        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])

        return {
            "success": True,
            "ticker": ticker.upper(),
            "data": result
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    
    
@app.get("/financials/{ticker}/{statement}")
async def get_financial_statement(
    ticker: str,
    statement: str,
    period: str = Query("annual", description="annual or quarterly")
):
    """
    Get specific financial statement
    
    Statements: income, balance, cash
    Example: /financials/AAPL/income?period=annual
    Example: /financials/MSFT/balance?period=quarterly
    """
    statement_map = {
        "income": "income_statement",
        "balance": "balance_sheet",
        "cash": "cash_flow"
    }
    
    if statement not in statement_map:
        raise HTTPException(status_code=400, detail="Invalid statement. Use: income, balance, cash")
    
    try:
        result = await financial_scraper.scrape_financial_reports(ticker, force_scrape=False)
        statement_key = statement_map[statement]
        
        if period == "quarterly" and "quarterly" in result.get(statement_key, {}):
            data = result[statement_key]["quarterly"]
        else:
            data = result[statement_key].get("annual", {})
        
        return {
            "success": True,
            "ticker": ticker.upper(),
            "statement": statement,
            "period": period,
            "data": data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Combined Endpoint ====================

@app.get("/company/{ticker}")
async def get_company_data(
    ticker: str,
    year: Optional[int] = None,
    quarter: Optional[str] = None,
    include_financials: bool = Query(True, description="Include financial reports"),
    include_transcript: bool = Query(False, description="Include earnings transcript"),
    force_scrape: bool = Query(False, description="Force fresh scrape")
):
    """
    Get combined company data (financials + earnings transcript)
    
    Example: /company/AAPL?include_financials=true&include_transcript=true&year=2026&quarter=Q1
    """
    result = {
        "success": True,
        "ticker": ticker.upper(),
        "data": {}
    }
    
    # Get financial reports
    if include_financials:
        try:
            financials = await financial_scraper.scrape_financial_reports(ticker, force_scrape)
            result["data"]["financials"] = financials
        except Exception as e:
            result["data"]["financials"] = {"error": str(e)}
    
    # Get earnings transcript
    if include_transcript and year and quarter:
        try:
            transcript = earnings_scraper.scrape_by_ticker_quarter(ticker, year, quarter)
            if transcript.get('success'):
                result["data"]["earnings_call"] = {
                    "url": transcript.get('url'),
                    "stats": transcript.get('data', {}).get('stats', {}),
                    "presentation": transcript.get('data', {}).get('presentation', []),
                    "qa_session": transcript.get('data', {}).get('qa_session', [])
                }
            else:
                result["data"]["earnings_call"] = {"error": transcript.get('error')}
        except Exception as e:
            result["data"]["earnings_call"] = {"error": str(e)}
    
    return result


@app.get("/health")
async def health_check():
    logger.info("API HIT → /health")
    return {
        "status": "healthy",
        "services": ["earnings_calls", "financial_reports"],
        "timestamp": __import__('datetime').datetime.now().isoformat()
    }


if __name__ == "__main__":
    print("🚀 Starting Combined Financial API...")
    print("📍 Earnings Call: http://localhost:8000/scrape/AAPL/2026/Q1")
    print("📍 Financial Reports: http://localhost:8000/financials/AAPL")
    print("📍 Combined: http://localhost:8000/company/AAPL?include_financials=true&include_transcript=true&year=2026&quarter=Q1")
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)