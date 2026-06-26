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
    
    # AI Analyst Synthesis
    ai_summary = Column(Text, nullable=True)     # detailed briefing markdown cached in DB
    
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

# Index for quick time-series queries
Index("idx_stock_price_symbol_date", StockPriceHistory.symbol, StockPriceHistory.date)
# Composite unique constraint to prevent duplicate symbols in a single user watchlist
Index("idx_watchlist_email_symbol", WatchlistItem.email, WatchlistItem.symbol, unique=True)

# Indexes for sort-heavy list queries (alpha_score is the default sort column)
Index("idx_stock_alpha_score", StockMaster.alpha_score.desc())
Index("idx_stock_cagr3y", StockMaster.cagr_3y.desc())
