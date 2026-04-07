from pathlib import Path
from datetime import datetime
import json
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

class YahooFinanceScraper:
    def __init__(self, cache_dir="data/financials"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def scrape_financial_reports(self, ticker: str, force_scrape: bool = False):
        """
        Scrape Yahoo Finance financials (income, balance sheet, cash flow)
        Fully synchronous (Playwright sync API)
        """
        ticker = ticker.upper()
        cache_path = self.cache_dir / f"{ticker}.json"

        if not force_scrape and cache_path.exists():
            print(f"📂 Using cached data for {ticker}")
            return json.loads(cache_path.read_text())

        urls = {
            "income_statement": f"https://finance.yahoo.com/quote/{ticker}/financials?p={ticker}",
            "balance_sheet": f"https://finance.yahoo.com/quote/{ticker}/balance-sheet?p={ticker}",
            "cash_flow": f"https://finance.yahoo.com/quote/{ticker}/cash-flow?p={ticker}",
        }

        browser = None
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-accelerated-2d-canvas",
                        "--disable-gpu",
                        "--disable-software-rasterizer",
                        "--disable-web-security",  # Sometimes helps with CORS
                        "--disable-features=IsolateOrigins,site-per-process",
                    ],
                    timeout=30000  # Browser launch timeout
                )

                # Set user-agent and headers in context
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
                    extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
                    viewport={"width": 1920, "height": 1080}  # Set viewport size
                )

                page = context.new_page()
                
                # Set default timeout for all operations
                page.set_default_timeout(60000)
                page.set_default_navigation_timeout(60000)

                result = {}
                for key, url in urls.items():
                    print(f"📊 Processing {key} for {ticker}")
                    try:
                        result[key] = self.extract_report_data(page, url)
                    except PlaywrightTimeoutError as te:
                        print(f"⏰ Timeout on {key} for {ticker}: {te}")
                        result[key] = {"error": f"Timeout: {str(te)}", "annual": {}, "quarterly": {}}
                    except Exception as e:
                        print(f"❌ Error on {key} for {ticker}: {e}")
                        result[key] = {"error": str(e), "annual": {}, "quarterly": {}}

                # Save cache
                output = {
                    "ticker": ticker,
                    "fetched_at": datetime.now().isoformat(),
                    **result
                }
                cache_path.write_text(json.dumps(output, indent=2))
                return output

        except Exception as e:
            print("❌ Error scraping Yahoo Finance:", e)
            return {"error": str(e)}

        finally:
            if browser:
                try:
                    browser.close()
                except:
                    pass

    def extract_report_data(self, page, url):
        """
        Extract annual and quarterly data from Yahoo Finance page
        """
        print(f"🔍 Navigating to {url}")
        
        try:
            # Navigate with retry logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=45000)
                    break
                except PlaywrightTimeoutError:
                    if attempt == max_retries - 1:
                        raise
                    print(f"⏰ Navigation timeout, retrying ({attempt + 1}/{max_retries})...")
                    page.wait_for_timeout(2000)
            
            # Wait for main content to load
            page.wait_for_selector(".tableContainer", timeout=30000)
            page.wait_for_timeout(2000)  # Additional buffer for dynamic content
            
            def extract_table_data(label):
                """Extract table data with better error handling"""
                try:
                    # Try to expand rows if button exists
                    expand_button = page.query_selector("button.link2-btn")
                    if expand_button and expand_button.is_visible():
                        print(f"⏳ Expanding all rows for {label}")
                        try:
                            expand_button.click()
                            page.wait_for_timeout(2000)
                        except Exception as e:
                            print(f"⚠️ Could not expand rows: {e}")
                    
                    # Wait for table rows with a more flexible selector
                    try:
                        page.wait_for_selector(".tableBody .row", timeout=15000)
                    except PlaywrightTimeoutError:
                        print(f"⚠️ No table rows found for {label}, trying alternative selector")
                        page.wait_for_selector("[data-test='fin-row']", timeout=10000)
                    
                    html = page.content()
                    soup = BeautifulSoup(html, "lxml")
                    
                    # Try different table structures
                    headers = []
                    header_selectors = [".tableHeader .row .column", "thead th", "[data-test='fin-col']"]
                    for selector in header_selectors:
                        headers = [col.text.strip() for col in soup.select(selector)]
                        if headers:
                            break
                    
                    rows = []
                    # Try different row selectors
                    row_selectors = [".tableBody .row", "tbody tr", "[data-test='fin-row']"]
                    
                    for selector in row_selectors:
                        table_rows = soup.select(selector)
                        if table_rows:
                            for row in table_rows:
                                # Extract title
                                title_selectors = [".rowTitle", "td:first-child", "[data-test='fin-col']:first-child"]
                                title_el = None
                                for ts in title_selectors:
                                    title_el = row.select_one(ts)
                                    if title_el:
                                        break
                                
                                if not title_el:
                                    continue
                                
                                row_title = title_el.text.strip()
                                
                                # Extract level from classes
                                level = "0"
                                for c in row.get("class", []):
                                    if "lv-" in c:
                                        level = c.split("-")[1]
                                
                                # Extract values
                                value_selectors = [".column", "td:not(:first-child)", "[data-test='fin-col']:not(:first-child)"]
                                values = []
                                for vs in value_selectors:
                                    values = [col.text.strip().replace(",", "") for col in row.select(vs)]
                                    if values:
                                        break
                                
                                if values:
                                    metric = row_title if level == "0" else ("  " * int(level) + row_title)
                                    rows.append({"metric": metric.strip(), "values": values})
                            break  # Break if we found rows
                    
                    return {"headers": headers, "rows": rows}
                    
                except Exception as e:
                    print(f"❌ Error extracting {label} data: {e}")
                    return {"headers": [], "rows": [], "error": str(e)}
            
            # Extract annual data
            print("📈 Extracting annual data...")
            annual_data = extract_table_data("Annual")
            print(f"✅ Annual data extracted: {len(annual_data.get('rows', []))} rows")
            
            # Try to get quarterly data
            quarterly_data = {"headers": [], "rows": []}
            try:
                quarterly_tab = page.query_selector("#tab-quarterly")
                if quarterly_tab and quarterly_tab.is_visible():
                    print("🔄 Switching to Quarterly data")
                    quarterly_tab.click()
                    page.wait_for_timeout(3000)
                    page.wait_for_selector(".tableBody .row", timeout=15000)
                    quarterly_data = extract_table_data("Quarterly")
                    print(f"✅ Quarterly data extracted: {len(quarterly_data.get('rows', []))} rows")
                else:
                    print("⚠️ Quarterly tab not found")
            except Exception as e:
                print(f"⚠️ Could not extract quarterly data: {e}")
            
            return {"annual": annual_data, "quarterly": quarterly_data}
            
        except PlaywrightTimeoutError as e:
            print(f"❌ Timeout extracting data from {url}: {e}")
            raise
        except Exception as e:
            print(f"❌ Unexpected error extracting data from {url}: {e}")
            return {"annual": {"error": str(e)}, "quarterly": {"error": str(e)}}

# Example usage
if __name__ == "__main__":
    scraper = YahooFinanceScraper()
    
    # Test with a single ticker
    result = scraper.scrape_financial_reports("AAPL", force_scrape=True)
    
    if "error" not in result:
        print(f"✅ Successfully scraped {result['ticker']}")
        for report_type in ["income_statement", "balance_sheet", "cash_flow"]:
            if report_type in result:
                annual_rows = result[report_type].get("annual", {}).get("rows", [])
                print(f"  - {report_type}: {len(annual_rows)} annual metrics")
    else:
        print(f"❌ Failed: {result['error']}")