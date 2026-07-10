from sqlalchemy import Column, Integer, String, Float, Text, Date, ForeignKey, Index, DateTime, func
from sqlalchemy.orm import relationship
from app.core.database import Base

class StockMaster(Base):
    __tablename__ = "stock_masters"

    symbol = Column(String(50), primary_key=True, index=True)
    company_name = Column(String(255), index=True, nullable=False)
    isin = Column(String(50), nullable=True)
    sector = Column(String(100), index=True, nullable=False) # e.g. Banking, IT, Auto, Defence, Pharma, Energy, FMCG
    industry = Column(String(100), nullable=True)
    
    # Financial Ratios / Metrics
    market_cap = Column(Float, nullable=True)   # in Crores
    pe_ratio = Column(Float, nullable=True)
    pb_ratio = Column(Float, nullable=True)
    roe = Column(Float, nullable=True)          # in % (e.g. 15.4 means 15.4%)
    debt_equity = Column(Float, nullable=True)   # absolute (e.g. 0.45)
    dividend_yield = Column(Float, nullable=True) # in % (e.g. 1.2 means 1.2%)
    beta = Column(Float, nullable=True)
    
    # Quantitative Returns (drift-matched from simulated historical price series)
    cagr_1y = Column(Float, nullable=True)
    cagr_3y = Column(Float, nullable=True)
    cagr_5y = Column(Float, nullable=True)
    
    # Proprietary Alpha Score
    alpha_score = Column(Float, nullable=True)   # 0 to 100
    
    # Intermediate scores from Institutional Scoring Engine v2
    fundamental_score = Column(Float, nullable=True)
    valuation_score = Column(Float, nullable=True)
    technical_score = Column(Float, nullable=True)
    risk_score = Column(Float, nullable=True)
    sector_relative_score = Column(Float, nullable=True)
    quality_score = Column(Float, nullable=True)
    event_score = Column(Float, nullable=True)
    confidence_score = Column(Float, nullable=True)
    
    # Mode-based Stances
    investor_verdict = Column(String(50), nullable=True)
    trader_verdict = Column(String(50), nullable=True)
    trend_structure = Column(String(50), nullable=True)
    
    # Direct Explainability Fields
    bull_case = Column(Text, nullable=True)
    bear_case = Column(Text, nullable=True)
    verdict_rationale = Column(Text, nullable=True)
    
    # AI Analyst Synthesis
    ai_summary = Column(Text, nullable=True)     # detailed briefing markdown cached in DB

    # ── Progressive Discovery Pipeline ──────────────────────────────────────
    # Tracks the ingestion state machine for async progressive loading.
    # DISCOVERED: basic info fetched (name, price, sector) — page can render header
    # INGESTING: price history downloaded, CAGR/beta computing
    # ANALYTICS_RUNNING: alpha score and sub-scores computing
    # READY: fully ingested, all analytics available
    # FAILED: all providers failed, permanently invalid
    ingestion_status = Column(String(20), nullable=False, server_default="READY")
    current_price = Column(Float, nullable=True)   # live price at discovery time
    exchange = Column(String(10), nullable=True)   # "NSE" | "BSE"
    
    last_updated = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    price_history = relationship("StockPriceHistory", back_populates="stock", cascade="all, delete-orphan", passive_deletes=True)
    watchlist_items = relationship("WatchlistItem", back_populates="stock", cascade="all, delete-orphan", passive_deletes=True)

class StockPriceHistory(Base):
    __tablename__ = "stock_price_histories"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(50), ForeignKey("stock_masters.symbol", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    close = Column(Float, nullable=False)

    # Relationships
    stock = relationship("StockMaster", back_populates="price_history")

class WatchlistItem(Base):
    __tablename__ = "watchlist_items"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), index=True, nullable=False)
    symbol = Column(String(50), ForeignKey("stock_masters.symbol", ondelete="CASCADE"), nullable=False)
    added_at = Column(DateTime, default=func.now())

    # Relationships
    stock = relationship("StockMaster", back_populates="watchlist_items")


class VerdictSnapshot(Base):
    """
    Point-in-time record of what the Alpha Score model actually said about a
    stock at ingestion time — written on every (re)ingestion so a real
    backtest can later compare the model's own past verdicts against actual
    subsequent price action, instead of the price-only proxy model in
    services/backtesting.py (backtest_stock/aggregate_backtest_summary).

    Deliberately NOT a ForeignKey to stock_masters.symbol: these are an
    append-only historical audit trail for backtesting and must survive
    independent of a StockMaster row's current lifecycle (e.g. a symbol
    later re-discovered from scratch, or marked Invalid, should not lose or
    cascade-delete its prior verdict history).
    """
    __tablename__ = "verdict_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(50), nullable=False, index=True)
    snapshot_date = Column(Date, nullable=False, index=True)
    verdict = Column(String(50), nullable=False)          # investor_verdict at snapshot time
    score = Column(Float, nullable=False)                 # investor final_score (0-100) at snapshot time
    # JSON-encoded dict (stored as TEXT, matching this codebase's existing
    # convention of storing structured data as serialized text rather than a
    # DB-specific JSON column type — see ai_summary/bull_case elsewhere in
    # this file). Holds the full ratings breakdown: fundamental/quality/
    # valuation/technical/risk/sector_relative/event/confidence scores, plus
    # trader_score/trader_verdict (not given dedicated columns to keep this
    # migration minimal — see Phase 4 summary).
    pillar_scores = Column(Text, nullable=True)
    model_version = Column(String(20), nullable=False)    # e.g. "v2" — Alpha Score model version that produced this snapshot

# Index for quick time-series queries
Index("idx_stock_price_symbol_date", StockPriceHistory.symbol, StockPriceHistory.date)
# Composite unique constraint to prevent duplicate symbols in a single user watchlist
Index("idx_watchlist_email_symbol", WatchlistItem.email, WatchlistItem.symbol, unique=True)

# Indexes for sort-heavy list queries (alpha_score is the default sort column)
Index("idx_stock_alpha_score", StockMaster.alpha_score.desc())
Index("idx_stock_cagr3y", StockMaster.cagr_3y.desc())

# Composite index for the backtest lookup pattern: "past snapshots for this
# symbol near date X" (see services/backtesting_v2.py)
Index("idx_verdict_snapshot_symbol_date", VerdictSnapshot.symbol, VerdictSnapshot.snapshot_date)
