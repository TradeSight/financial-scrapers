from pathlib import Path
from datetime import datetime
import json
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

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
                    ]
                )

                # Set user-agent and headers in context
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/134.0.0.0 Safari/537.36",
                    extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
                )

                page = context.new_page()

                result = {}
                for key, url in urls.items():
                    result[key] = self.extract_report_data(page, url)

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
            try:
                browser.close()
            except:
                pass

    def extract_report_data(self, page, url):
        """
        Extract annual and quarterly data from Yahoo Finance page
        """
        print(f"🔍 Extracting data from {url}")
        page.goto(url, wait_until="domcontentloaded", timeout=90000)

        def extract_table_data(label):
            expand_button = page.query_selector("button.link2-btn")
            if expand_button:
                print(f"⏳ Expanding all rows for {label}")
                expand_button.click()
                page.wait_for_timeout(2000)

            page.wait_for_selector(".row.lv-0, .row.lv-1, .row.lv-2", timeout=60000)
            html = page.content()
            soup = BeautifulSoup(html, "lxml")

            headers = [col.text.strip() for col in soup.select(".tableHeader .row .column")]

            rows = []
            for row in soup.select(".tableBody .row"):
                title_el = row.select_one(".rowTitle")
                if not title_el:
                    continue

                row_title = title_el.text.strip()
                level = "0"
                for c in row.get("class", []):
                    if "lv-" in c:
                        level = c.split("-")[1]

                values = [col.text.strip().replace(",", "") for i, col in enumerate(row.select(".column")) if i > 0]

                if values:
                    metric = row_title if level == "0" else ("  " * int(level) + row_title)
                    rows.append({"metric": metric.strip(), "values": values})

            return {"headers": headers, "rows": rows}

        # Annual data
        annual_data = extract_table_data("Annual")

        # Quarterly data
        quarterly_tab = page.query_selector("#tab-quarterly")
        if quarterly_tab:
            print("🔄 Switching to Quarterly data")
            quarterly_tab.click()
            page.wait_for_timeout(2000)
            page.wait_for_selector(".tableBody .row", timeout=60000)
            quarterly_data = extract_table_data("Quarterly")
        else:
            quarterly_data = {}

        return {"annual": annual_data, "quarterly": quarterly_data}