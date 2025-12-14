"""
Application Configuration
==========================

Centralized configuration management using Pydantic Settings.
Loads configuration from environment variables.
"""

from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field, validator


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # ========================================================================
    # Application Settings
    # ========================================================================
    APP_ENV: str = Field(default="development", env="APP_ENV")
    APP_NAME: str = Field(default="AI Customer Support Agent", env="APP_NAME")
    APP_VERSION: str = Field(default="2.4.1", env="APP_VERSION")
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    DEBUG: bool = Field(default=False, env="DEBUG")
    
    # ========================================================================
    # API Settings
    # ========================================================================
    API_HOST: str = Field(default="0.0.0.0", env="API_HOST")
    API_PORT: int = Field(default=8000, env="API_PORT")
    API_WORKERS: int = Field(default=4, env="API_WORKERS")
    
    # CORS Settings
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:3000"],
        env="CORS_ORIGINS"
    )
    
    # ========================================================================
    # LLM Configuration
    # ========================================================================
    ANTHROPIC_API_KEY: str = Field(..., env="ANTHROPIC_API_KEY")
    OPENAI_API_KEY: str = Field(..., env="OPENAI_API_KEY")
    
    LLM_PRIMARY_PROVIDER: str = Field(default="anthropic", env="LLM_PRIMARY_PROVIDER")
    LLM_PRIMARY_MODEL: str = Field(
        default="claude-sonnet-4-20250514",
        env="LLM_PRIMARY_MODEL"
    )
    LLM_FALLBACK_PROVIDER: str = Field(default="openai", env="LLM_FALLBACK_PROVIDER")
    LLM_FALLBACK_MODEL: str = Field(default="gpt-4", env="LLM_FALLBACK_MODEL")
    LLM_TEMPERATURE: float = Field(default=0.3, env="LLM_TEMPERATURE")
    LLM_MAX_TOKENS: int = Field(default=2000, env="LLM_MAX_TOKENS")
    LLM_TIMEOUT_SECONDS: int = Field(default=30, env="LLM_TIMEOUT_SECONDS")
    
    # ========================================================================
    # Vector Database Configuration
    # ========================================================================
    PINECONE_API_KEY: str = Field(..., env="PINECONE_API_KEY")
    PINECONE_ENVIRONMENT: str = Field(
        default="us-west1-gcp",
        env="PINECONE_ENVIRONMENT"
    )
    PINECONE_INDEX_NAME: str = Field(
        default="support-knowledge",
        env="PINECONE_INDEX_NAME"
    )
    PINECONE_DIMENSION: int = Field(default=1536, env="PINECONE_DIMENSION")
    
    # ========================================================================
    # Database Configuration
    # ========================================================================
    DATABASE_URL: str = Field(..., env="DATABASE_URL")
    DATABASE_POOL_SIZE: int = Field(default=20, env="DATABASE_POOL_SIZE")
    DATABASE_MAX_OVERFLOW: int = Field(default=40, env="DATABASE_MAX_OVERFLOW")
    DATABASE_POOL_TIMEOUT: int = Field(default=30, env="DATABASE_POOL_TIMEOUT")
    DATABASE_POOL_RECYCLE: int = Field(default=3600, env="DATABASE_POOL_RECYCLE")
    
    # ========================================================================
    # Redis Configuration
    # ========================================================================
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        env="REDIS_URL"
    )
    REDIS_CACHE_TTL: int = Field(default=3600, env="REDIS_CACHE_TTL")
    REDIS_MAX_CONNECTIONS: int = Field(default=50, env="REDIS_MAX_CONNECTIONS")
    
    # ========================================================================
    # Security Configuration
    # ========================================================================
    SECRET_KEY: str = Field(..., env="SECRET_KEY")
    JWT_SECRET_KEY: str = Field(..., env="JWT_SECRET_KEY")
    JWT_ALGORITHM: str = Field(default="HS256", env="JWT_ALGORITHM")
    JWT_EXPIRATION_HOURS: int = Field(default=24, env="JWT_EXPIRATION_HOURS")
    
    # ========================================================================
    # Monitoring Configuration
    # ========================================================================
    PROMETHEUS_PORT: int = Field(default=9090, env="PROMETHEUS_PORT")
    METRICS_ENABLED: bool = Field(default=True, env="METRICS_ENABLED")
    TRACING_ENABLED: bool = Field(default=True, env="TRACING_ENABLED")
    
    # ========================================================================
    # Business Logic Configuration
    # ========================================================================
    AI_CONFIDENCE_THRESHOLD: float = Field(
        default=0.75,
        env="AI_CONFIDENCE_THRESHOLD"
    )
    AI_AUTO_RESOLVE_THRESHOLD: float = Field(
        default=0.85,
        env="AI_AUTO_RESOLVE_THRESHOLD"
    )
    ESCALATION_CONFIDENCE_THRESHOLD: float = Field(
        default=0.60,
        env="ESCALATION_CONFIDENCE_THRESHOLD"
    )
    
    # ========================================================================
    # Cost Management
    # ========================================================================
    COST_TRACKING_ENABLED: bool = Field(default=True, env="COST_TRACKING_ENABLED")
    MONTHLY_BUDGET_USD: float = Field(default=2500, env="MONTHLY_BUDGET_USD")
    DAILY_BUDGET_USD: float = Field(default=100, env="DAILY_BUDGET_USD")
    
    # ========================================================================
    # Validators
    # ========================================================================
    
    @validator("CORS_ORIGINS", pre=True)
    def parse_cors_origins(cls, v):
        """Parse CORS origins from string or list"""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
    
    @validator("LOG_LEVEL")
    def validate_log_level(cls, v):
        """Validate log level"""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of {valid_levels}")
        return v.upper()
    
    @validator("AI_CONFIDENCE_THRESHOLD", "AI_AUTO_RESOLVE_THRESHOLD", "ESCALATION_CONFIDENCE_THRESHOLD")
    def validate_confidence_threshold(cls, v):
        """Validate confidence thresholds are between 0 and 1"""
        if not 0 <= v <= 1:
            raise ValueError("Confidence threshold must be between 0 and 1")
        return v
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Global settings instance
settings = Settings()
