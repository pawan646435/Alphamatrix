from sqlalchemy import Column, Integer, String, Float, Text, Date, ForeignKey, Index, DateTime, func
from sqlalchemy.orm import relationship
from app.core.database import Base

class FundMaster(Base):
    __tablename__ = "fund_masters"

    scheme_code = Column(Integer, primary_key=True, index=True)
    isin = Column(String(50), index=True, nullable=True)
    fund_name = Column(String(255), index=True, nullable=False)
    category = Column(String(50), index=True, nullable=False) # e.g. Large Cap, Mid Cap, Small Cap, Sectoral, Index
    sub_category = Column(String(100), nullable=True)         # e.g. Equity - Mid Cap, Equity - Index
    pe_ratio = Column(Float, nullable=True)
    expense_ratio = Column(Float, nullable=True)
    
    # Quantitative Risk-Return Metrics
    cagr_1y = Column(Float, nullable=True)
    cagr_3y = Column(Float, nullable=True)
    cagr_5y = Column(Float, nullable=True)
    sharpe_ratio = Column(Float, nullable=True)
    sortino_ratio = Column(Float, nullable=True)
    alpha = Column(Float, nullable=True)
    beta = Column(Float, nullable=True)
    
    # Fund Rating Engine v1 — Composite Score & Verdict
    fund_score = Column(Float, nullable=True)                    # 0–100 deterministic score
    fund_verdict = Column(String(20), nullable=True)             # Elite/Strong/Good/Average/Avoid

    # Risk Metrics (computed from NAV history)
    std_deviation = Column(Float, nullable=True)                 # Annualized standard deviation
    max_drawdown = Column(Float, nullable=True)                  # Maximum peak-to-trough drawdown %
    aum = Column(Float, nullable=True)                           # AUM in crores (scraped/estimated)
    consistency_score = Column(Float, nullable=True)             # 0–100 rolling return consistency

    # Category Peer Analytics
    category_rank = Column(Integer, nullable=True)               # Rank within category
    category_count = Column(Integer, nullable=True)              # Total funds in category
    category_avg_cagr_3y = Column(Float, nullable=True)         # Category average 3Y CAGR
    category_avg_sharpe = Column(Float, nullable=True)           # Category average Sharpe
    category_avg_alpha = Column(Float, nullable=True)            # Category average alpha

    # AI Analyst Synthesis
    ai_summary = Column(Text, nullable=True)
    bull_case = Column(Text, nullable=True)                      # AI bull case explanation
    bear_case = Column(Text, nullable=True)                      # AI bear case explanation
    fund_rationale = Column(Text, nullable=True)                 # AI rating rationale

    last_updated = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    nav_history = relationship("NAVHistory", back_populates="fund", cascade="all, delete-orphan", passive_deletes=True)

class NAVHistory(Base):
    __tablename__ = "nav_histories"

    id = Column(Integer, primary_key=True, index=True)
    scheme_code = Column(Integer, ForeignKey("fund_masters.scheme_code", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    nav = Column(Float, nullable=False)

    # Relationships
    fund = relationship("FundMaster", back_populates="nav_history")

# Indices for quick lookup of NAV timeseries
Index("idx_nav_scheme_date", NAVHistory.scheme_code, NAVHistory.date)

# Indexes for fund list default sort
Index("idx_fund_cagr3y", FundMaster.cagr_3y.desc())
Index("idx_fund_sharpe", FundMaster.sharpe_ratio.desc())
