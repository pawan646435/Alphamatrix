# AlphaMatrix — Premium Mutual Fund Analytics & AI Platform

AlphaMatrix is a high-performance quantitative analytics terminal for Indian Mutual Funds. Inspired by premium minimalist aesthetics, the platform combines strict RAG models (Retrieval-Augmented Generation), timeseries performance math, and deep geopolitical risk analysis into a unified luxury dashboard.

---

## 💎 Design Philosophy & Theme

AlphaMatrix features a bespoke design inspired by luxury minimalism (such as *lunchlab.fr*):
* **Normal Mode**: Warm Ivory base background (`#E8DDC9`) with rich charcoal-black text (`#0A0908`) and dark gold lines.
* **Dark Mode**: Rich warm black background (`#0A0908`) with warm ivory text (`#E8DDC9`) and gold accents (`#C9A56B`).
* **Dynamic AMC Logos**: Autodetects Asset Management Companies (SBI, Quant, Axis, HDFC, Nippon, etc.) to render beautiful custom vector monograms (e.g., the keyhole for SBI, summation Sigma for Quant, and chevron vectors for Axis).

---

## ⚡ Core Features

1. **Quantitative Analytics**: Compute trailing returns (CAGR 1Y, 3Y, 5Y), volatility parameters (CAPM Beta vs Nifty 50), and risk-adjusted efficiency metrics (Sharpe & Sortino Ratios).
2. **Quantitative Intelligence Briefing**: Integrates trailing performance, geopolitical situations (global trade friction, inflation, interest cycles), and category volatility overlays to generate a definitive **BUY, HOLD, or AVOID** investment verdict.
3. **Interactive Analyst Terminal**: Pre-contextualized chat terminal enabling deep semantic query lookups for any fund.
4. **Latency Optimization**: Enforces a 5.5-year NAV cutoff limit and runs AI analysis asynchronously in background threads so the UI loads instantly (<300ms) and pulls summaries once computed.
5. **Interactive Charting Matrix**: Multi-duration area charts (1M, 6M, 1Y, 3Y, 5Y, MAX) and coordinate scatter plots of Risk vs Return.

---

## 🛠️ Technology Stack

* **Frontend**: React, Tailwind CSS, Recharts (Dynamic Theme SVG Mapping), Lucide Icons, Vite
* **Backend**: FastAPI, SQLite (local database), SQLAlchemy, Uvicorn, Google Gemini API

---

## 🚀 Getting Started

### Prerequisites
* Python 3.10+
* Node.js 18+

### Setup Configuration

1. **Backend Configuration**:
   Create a `.env` file inside `backend/` containing:
   ```env
   GEMINI_API_KEY=your_gemini_api_key_here
   DATABASE_URL=sqlite:///./alphamatrix.db
   ```

2. **Install Backend Dependencies**:
   ```bash
   cd backend
   python -m venv .venv
   source .venv/bin/activate  # Or .venv\Scripts\activate on Windows
   pip install -r requirements.txt
   ```

3. **Install Frontend Dependencies**:
   ```bash
   cd ../frontend
   npm install
   ```

### Running the Platform

1. **Launch the FastAPI Server**:
   ```bash
   cd backend
   uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
   ```
   *Note: At first startup, the server automatically initializes database schemas and seeds historical NAV data.*

2. **Launch the Vite Dev Server**:
   ```bash
   cd frontend
   npm run dev
   ```

3. Open **`http://localhost:5173/`** in your browser.
