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
    
    # AI Analyst Synthesis
    ai_summary = Column(Text, nullable=True)
    
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
