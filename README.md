# 💎 AlphaMatrix — Quantitative Analytics & AI Intelligence Terminal

AlphaMatrix is a premium, high-performance quantitative intelligence terminal for Indian Mutual Funds and Equities. Designed with a luxury minimalist aesthetic (inspired by *lunchlab.fr*), the platform integrates strict multi-factor RAG models (Retrieval-Augmented Generation), timeseries performance mathematics, dynamic stock auto-ingestion, and macro-financial risk overlays into a unified desktop dashboard.

---

## 🎨 Visual Identity & Theme

AlphaMatrix features a custom-engineered design system that prioritizes structural grids, fine lines, and clean typographic hierarchy:
* **Light Mode (Warm Ivory)**: Warm Ivory base background (`#E8DDC9`) with charcoal text (`#0A0908`) and dark gold lines.
* **Dark Mode (Charcoal Black)**: Deep charcoal-black background (`#0A0908`) with warm ivory text (`#E8DDC9`) and gold accents (`#C9A56B`).
* **Bespoke Vector Monograms**: 
  * **AMCs (Mutual Funds)**: Auto-detects Asset Management Companies (SBI, Quant, Axis, HDFC, Nippon, etc.) to render vector logos (e.g., the keyhole for SBI, summation Sigma for Quant, and chevron vectors for Axis).
  * **Equities (Stocks)**: Dynamic lettermark generation mapped to stock ticker prefixes, maintaining absolute design cohesion.

---

## ⚡ Core Platform Capabilities

### 1. Cross-Asset Experience
A unified interface structure where Mutual Funds and Equities share a single design language, card system, AI-briefing layout, and interactive charts.

### 2. Unified Global Search & Discovery
* **Dual-Class Router**: A unified search experience. Users can search for tickers (e.g., `TCS`, `RELIANCE`) or scheme names (e.g., `Parag Parikh Flexi Cap`, `HDFC Mid Cap Fund`) and the router automatically classifies and routes the request.
* **Portal-Based Suggestions**: The search dropdown is rendered using React Portals (`createPortal`) directly on `document.body` to completely bypass parent container clipping and CSS stacking context issues.
* **Self-Expanding Database**: If a queried ticker does not exist in the local database, the search system initiates a quick Yahoo Finance verification. If valid, the frontend presents a **⚡ DISCOVER** option to auto-ingest the equity.

### 3. Dynamic Auto-Ingestion & Fallbacks
* **Ingestion Pipeline**: When an unindexed stock is requested, the backend triggers an asynchronous background ingestion task. It pulls up to 6 years of historical price data from Yahoo Finance, falling back sequentially (`6y` → `max` → `3y` → `2y` → `1y`) for newer listings (like `SWIGGY` or `ZOMATO`).
* **Exchange Fallbacks**: Automatically checks NSE (`.NS`) first, falling back to BSE (`.BO`) if the ticker is only listed on the secondary exchange.
* **Quantitative Math**: Calculates 3-Year CAGR, rolling return metrics, volatility coefficients (Beta vs Nifty 50), and calculates a multi-factor **Alpha Score (0-100)** incorporating valuation, debt-equity, return on equity, and momentum.

### 4. Interactive Analytics & Charts
* **Timeseries Visualization**: High-performance SVG area charts showing performance over customizable periods (1M, 6M, 1Y, 3Y, 5Y, MAX).
* **Risk/Return Scatter Matrix**: Coordinate mapping plots of Sharpe Ratio vs. CAGR for Mutual Funds, and Volatility vs. CAGR for Stocks, to visually identify efficient frontier candidates.
* **Multi-Stock Comparison**: Interactive comparison overlay mapping relative returns of multiple stocks on a single timeseries axis.
* **Geopolitical & Regime Intelligence**: Incorporates macro market regime classifiers (**RISK ON** / **RISK OFF**) and generates macro geopolitical briefings contextually.

---

## 🛠️ Technology Stack

### Backend
* **FastAPI**: Asynchronous high-performance API server.
* **SQLAlchemy & SQLite**: Modern ORM layer and local relational database for indexing stock master data, historical price series, and fund data.
* **Yahoo Finance API & MFAPI**: Ingestion pipelines for stock prices, fund NAVs, and metadata.
* **Groq Llama 3.3**: Dynamic AI summarization, investment briefings, semantic query parsing, and conversational stock/fund chatbots targeting the `llama-3.3-70b-versatile` model.
* **Redis**: (Optional) Cache manager for speed-up of global search queries and fund calculations.

### Frontend
* **Vite + React**: Rapid HMR frontend tooling.
* **Tailwind CSS**: Utility-first CSS framework mapped to custom theme variables.
* **Recharts**: Responsive chart rendering matching light/dark SVGs.
* **Lucide Icons**: Minimalist vector icons.

---

## 📁 Repository Structure

```
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── api.py           # Endpoint router mount point
│   │   │   └── v1/
│   │   │       ├── search.py    # Unified Global Search endpoint
│   │   │       ├── stocks.py    # Equities metadata, status, comparison, & details
│   │   │       ├── funds.py     # Mutual funds query, search & details
│   │   │       └── ai.py        # Semantic SQL parsing & analyst chat endpoints
│   │   ├── core/
│   │   │   ├── database.py      # SQLite connection & database session generators
│   │   │   └── config.py        # Environment variables & Pydantic setting declarations
│   │   ├── models/
│   │   │   └── stock.model      # StockMaster & StockPriceHistory SQL schemas
│   │   ├── workers/
│   │   │   └── stock_ingestion.py # yfinance data harvester, CAGR and Alpha Score calculations
│   │   └── tests/               # Pytest suite (AI agents, CAGR formulas, and Stock score analytics)
│   └── requirements.txt         # Python package dependencies
│
└── frontend/
    ├── src/
    │   ├── components/
    │   │   ├── GlobalSearch.jsx # Portaled global search input & event delegation
    │   │   ├── StockLogo.jsx    # SVG dynamic stock monogram generator
    │   │   └── charts/
    │   │       ├── InteractiveChart.jsx       # Fund NAV area timeseries
    │   │       ├── StockComparisonChart.jsx   # Multi-equity comparative timeseries
    │   │       └── StockRiskScatterplot.jsx   # Volatility vs return scatterplot
    │   ├── hooks/
    │   │   ├── useFunds.js      # Custom React hooks for MF querying, chat & semantic lookup
    │   │   └── useStocks.js     # Custom React hooks for stock query, status polling & comparison
    │   └── pages/
    │       ├── Home.jsx         # Mutual Funds homepage
    │       ├── StockHome.jsx    # Equities homepage & Market Regime overview
    │       └── StockDetail.jsx  # Equities detail views, including live polling spinner
    ├── package.json             # NPM package scripts
    └── vite.config.js           # Vite dev server configuration
```

---

## 🚀 Setup & Execution

### Prerequisites
* **Python**: Version 3.10 or higher
* **Node.js**: Version 18 or higher (LTS recommended)

### 1. Environment Configuration
Create a `.env` file inside the `backend/` directory:
```env
GROQ_API_KEY=your_groq_api_key
DATABASE_URL=sqlite:///./alphamatrix.db
REDIS_URL=redis://localhost:6379  # Optional
```

### 2. Backend Installation & Server Start
From the project root:
```bash
# Navigate to backend directory
cd backend

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows use: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start the FastAPI server
PYTHONPATH=. uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
*Note: On startup, the backend automatically initializes database tables and seeds base records.*

### 3. Frontend Installation & Client Start
In a new terminal window from the project root:
```bash
# Navigate to frontend directory
cd frontend

# Install package dependencies
npm install

# Start Vite dev server
npm run dev
```

Open your browser to **`http://localhost:5173/`** to view the platform.

### 4. Running the Test Suite
Ensure the backend virtual environment is active, then run:
```bash
cd backend
PYTHONPATH=. pytest
```
