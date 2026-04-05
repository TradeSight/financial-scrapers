import yfinance as yf
import json
import pandas as pd
from pathlib import Path
from typing import Dict, Any
from datetime import datetime

class YahooFinanceScraper:
    """Simple financial scraper using yfinance library - no browser needed"""
    
    def __init__(self, cache_dir: str = "data/financials"):
        """Initialize the scraper with cache directory"""
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    async def scrape_financial_reports(self, ticker: str, force_scrape: bool = False) -> Dict[str, Any]:
        """Get financial data using yfinance"""
        
        ticker_upper = ticker.upper()
        cache_path = self.cache_dir / f"{ticker_upper}.json"
        
        # Check cache
        if not force_scrape and cache_path.exists():
            print(f"📂 Using cached financial data for {ticker_upper}")
            with open(cache_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        try:
            stock = yf.Ticker(ticker_upper)
            
            result = {
                "ticker": ticker_upper,
                "source": "yfinance",
                "fetched_at": datetime.now().isoformat(),
                "income_statement": {
                    "annual": self._df_to_dict(stock.financials),
                    "quarterly": self._df_to_dict(stock.quarterly_financials)
                },
                "balance_sheet": {
                    "annual": self._df_to_dict(stock.balance_sheet),
                    "quarterly": self._df_to_dict(stock.quarterly_balance_sheet)
                },
                "cash_flow": {
                    "annual": self._df_to_dict(stock.cashflow),
                    "quarterly": self._df_to_dict(stock.quarterly_cashflow)
                },
                "info": {
                    "sector": stock.info.get('sector'),
                    "industry": stock.info.get('industry'),
                    "market_cap": stock.info.get('marketCap'),
                    "pe_ratio": stock.info.get('trailingPE'),
                    "eps": stock.info.get('trailingEps')
                }
            }
            
            # Save to cache
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, default=str)
            
            return result
            
        except Exception as e:
            print(f"Error fetching financials for {ticker_upper}: {e}")
            return {"error": str(e), "ticker": ticker_upper}
    
    def _df_to_dict(self, df):
        """Convert pandas DataFrame to serializable dictionary"""
        if df is None or df.empty:
            return {}
        
        result = {}
        for col in df.columns:
            date_str = col.strftime('%Y-%m-%d') if hasattr(col, 'strftime') else str(col)
            result[date_str] = {}
            for idx in df.index:
                value = df.loc[idx, col]
                if pd.isna(value):
                    result[date_str][idx] = None
                else:
                    result[date_str][idx] = float(value) if isinstance(value, (int, float)) else str(value)
        
        return result