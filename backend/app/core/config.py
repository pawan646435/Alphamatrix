import os
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "AlphaMatrix"
    API_V1_STR: str = "/api/v1"
    
    # Database configuration - defaults to SQLite but can be overridden with PostgreSQL URL
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./alphamatrix.db",
        validation_alias="DATABASE_URL"
    )
    
    # Cache and worker queues
    REDIS_URL: Optional[str] = Field(
        default=None,
        validation_alias="REDIS_URL"
    )
    
    # AI models
    GEMINI_API_KEY: Optional[str] = Field(
        default=None,
        validation_alias="GEMINI_API_KEY"
    )
    OPENAI_API_KEY: Optional[str] = Field(
        default=None,
        validation_alias="OPENAI_API_KEY"
    )
    
    # Security parameters
    SECRET_KEY: str = Field(
        default="SUPER_SECRET_ALPHAMATRIX_KEY_FOR_LOCAL_DEV_CHANGE_IN_PROD",
        validation_alias="SECRET_KEY"
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    
    # Rate Limiting
    RATE_LIMIT_CALLS: int = 100
    RATE_LIMIT_PERIOD: int = 60  # seconds
    
    # Default Benchmark Scheme Code (HDFC Index Fund - Nifty 50 Plan - Direct Plan or standard Nifty 50 Index Fund)
    # 120687 is HDFC Nifty 50 Index Fund Direct Growth
    BENCHMARK_SCHEME_CODE: int = 120687
    
    # Risk-Free Rate (Annualized - 6.0%)
    RISK_FREE_RATE: float = 0.06

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
