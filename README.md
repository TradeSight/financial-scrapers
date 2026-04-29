
---

#  Financial Data Platform (Scrapers + API)

A **production-ready FastAPI backend** that aggregates and serves:

*  Earnings call transcripts (AlphaStreet)
*  Financial statements (Yahoo Finance)
*  Market data (prices, key metrics, earnings)
*  Unified company-level APIs

Designed for **data-intensive systems**, **AI pipelines (RAG/LLMs)**, and **financial analytics platforms**.

---

## Why This Project Matters

Most financial data sources are:

* fragmented
* slow to query
* difficult to structure for downstream systems

This project solves that by:

* Converting **unstructured HTML → structured JSON**
* Providing **clean, consistent APIs**
* Optimizing for **performance with caching + concurrency**
* Making it **ready for AI consumption (RAG, embeddings, etc.)**

---

##  Key Engineering Highlights

### 1. Structured Transcript Extraction

* Parses complex HTML into:

  * Speaker-wise content
  * Presentation vs Q&A separation
* Maintains **context fidelity**, critical for LLM pipelines

### 2. Clean Financial Data Modeling

* Converts pandas DataFrames → structured JSON
* Supports:

  * Income Statement
  * Balance Sheet
  * Cash Flow
* Handles missing/null data safely

### 3. Performance-First Design

* Async FastAPI + thread pool for blocking I/O
* File-based caching:

  * Financials → 24h
  * Market data → 1h
* Reduces redundant external calls significantly

### 4. Unified Data Layer

* Single API combines:

  * Financials
  * Market data
  * Transcripts
* Simplifies frontend + AI integration

---

## System Design

```
Client (Frontend / AI Service)
            │
            ▼
     FastAPI Backend
            │
 ┌──────────┼──────────┐
 ▼                      ▼
Earnings Scraper   Financial Scraper
(AlphaStreet)      (Yahoo Finance)
 ▼                      ▼
HTML Parsing        yFinance + pandas
 ▼                      ▼
Structured JSON     Structured JSON
            │
            ▼
        Cache Layer
     (File-based JSON)
```

---

##  Tech Stack

| Layer       | Tech                               |
| ----------- | ---------------------------------- |
| Backend     | FastAPI, Python                    |
| Scraping    | BeautifulSoup, requests, curl_cffi |
| Data        | yfinance, pandas                   |
| Concurrency | asyncio, ThreadPoolExecutor        |
| Caching     | File-based JSON                    |
| APIs        | REST                               |

---

##  Core APIs

### Earnings Transcripts

```bash
GET /scrape/{ticker}/{year}/{quarter}
GET /search
GET /transcripts
```

### Financial Data

```bash
GET /financials/{ticker}
GET /financials/{ticker}/{statement}
```

### Market Data

```bash
GET /market-data/{ticker}
```

### Unified Endpoint

```bash
GET /company/{ticker}
```

---

##  Project Structure

```
.
├── app.py                     # FastAPI entry point
├── scrapers/
│   ├── earnings_scraper.py   # AlphaStreet scraper
│   └── financial_scraper.py  # Yahoo Finance scraper
├── data/
│   └── financials/           # Cached responses
```

---

##  Getting Started

```bash
git clone https://github.com/TradeSight/financial-scrapers.git
cd financial-scrapers

pip install -r requirements.txt
python app.py
```

Visit:

```
http://localhost:8000/docs
```

---

##  Performance Optimizations

*  Async request handling (FastAPI)
*  Thread pool for blocking scrapers
*  Intelligent caching layer
*  Reduced API latency + external dependency load

---

##  Real-World Use Cases

* AI-powered financial assistants (RAG systems)
* Earnings call summarization engines
* Stock analytics dashboards
* Quant research pipelines
* Data ingestion layer for fintech apps

---

##  Example Output

```json
{
  "ticker": "AAPL",
  "financials": {...},
  "marketData": {...},
  "earnings_call": {
    "presentation": [...],
    "qa_session": [...]
  }
}
```

---

##  Future Improvements

* Redis-based caching
* Background workers (Celery / RabbitMQ)
* Rate limiting & retries
* Docker + Kubernetes deployment
* Vector DB integration for semantic search

---

##  Author

**Vishal Singh**
Full-Stack Developer | Backend & AI Systems

* GitHub: [https://github.com/vishalsinghlab](https://github.com/vishalsinghlab)
* Portfolio: [https://singhvishal.vercel.app](https://singhvishal.vercel.app)

---



