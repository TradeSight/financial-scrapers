from pathlib import Path
from datetime import datetime
import json
import yfinance as yf
from curl_cffi import requests
import pandas as pd

class YahooFinanceScraper:
    def __init__(self, cache_dir="data/financials"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        # Create a session that mimics a real Chrome browser
        self.session = requests.Session(impersonate="chrome")

    def scrape_financial_reports(self, ticker: str, force_scrape: bool = False):
        """
        Scrape Yahoo Finance financials using yfinance with curl_cffi session
        """
        ticker = ticker.upper()
        cache_path = self.cache_dir / f"{ticker}.json"

        if not force_scrape and cache_path.exists():
            print(f"📂 Using cached data for {ticker}")
            cache_data = json.loads(cache_path.read_text())
            cache_age = (datetime.now() - datetime.fromisoformat(cache_data['fetched_at'])).total_seconds()
            if cache_age < 86400:
                return cache_data

        try:
            print(f"📊 Fetching data for {ticker}...")
            
            # Inject the curl_cffi session into yfinance
            stock = yf.Ticker(ticker, session=self.session)
            
            # Get financial statements
            income_stmt = stock.financials
            balance_sheet = stock.balance_sheet
            cash_flow = stock.cashflow
            
            result = {
                "ticker": ticker,
                "fetched_at": datetime.now().isoformat(),
                "income_statement": self._dataframe_to_dict(income_stmt),
                "balance_sheet": self._dataframe_to_dict(balance_sheet),
                "cash_flow": self._dataframe_to_dict(cash_flow)
            }
            
            cache_path.write_text(json.dumps(result, indent=2, default=str))
            print(f"✅ Successfully fetched data for {ticker}")
            return result
            
        except Exception as e:
            print(f"❌ Error: {e}")
            return {"error": str(e)}
    
    def _dataframe_to_dict(self, df):
        """Convert pandas DataFrame to serializable dict"""
        if df is None or df.empty:
            return {}
        
        result = {}
        for column in df.columns:
            col_name = str(column)
            result[col_name] = {}
            for index in df.index:
                idx_name = str(index)
                value = df.loc[index, column]
                if pd.isna(value):
                    result[col_name][idx_name] = None
                else:
                    result[col_name][idx_name] = value
        return result


# For bulk downloads
def download_multiple_stocks(tickers, period="1y"):
    """Download multiple stocks with proper session"""
    session = requests.Session(impersonate="chrome")
    return yf.download(tickers, period=period, session=session)


# For fetching just stock info
def get_stock_info(ticker: str):
    """Get basic stock info with curl_cffi session"""
    session = requests.Session(impersonate="chrome")
    stock = yf.Ticker(ticker.upper(), session=session)
    return stock.info


# Example usage
if __name__ == "__main__":
    scraper = YahooFinanceScraper()
    result = scraper.scrape_financial_reports("AUB", force_scrape=True)
    
    if "error" not in result:
        print(f"✅ Success: {len(result['income_statement'])} income items")
    else:
        print(f"❌ Failed: {result['error']}")