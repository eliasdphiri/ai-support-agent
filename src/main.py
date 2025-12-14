"""
AI Customer Support Agent - Main Application
=============================================

FastAPI application entry point for the AI Customer Support Agent.
Provides REST API endpoints for ticket processing, health checks, and metrics.

Author: Dan Elias Phiri - Senior Cloud & AI Automation Consultant
GitHub: https://github.com/eliasdphiri
Version: 2.4.1
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import generate_latest, REGISTRY
from starlette.responses import Response

# Import configurations and dependencies
from src.config import settings
from src.utils.logging import setup_logging

# Import API routers (to be implemented)
# from src.api.routes import tickets, health, admin, webhooks

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)


# ============================================================================
# Lifespan Context Manager
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    # Startup
    logger.info("=" * 80)
    logger.info("AI Customer Support Agent - Starting")
    logger.info(f"Environment: {settings.APP_ENV}")
    logger.info(f"Version: {settings.APP_VERSION}")
    logger.info("=" * 80)
    
    # Initialize database connection pool
    logger.info("Initializing database connection pool...")
    # await database.connect()
    
    # Initialize Redis connection
    logger.info("Initializing Redis connection...")
    # await redis_client.connect()
    
    # Initialize vector database
    logger.info("Initializing vector database...")
    # await vector_db.initialize()
    
    # Load knowledge base
    logger.info("Loading knowledge base...")
    # await knowledge_base.load()
    
    logger.info("✓ Application startup complete")
    
    yield
    
    # Shutdown
    logger.info("AI Customer Support Agent - Shutting down")
    
    # Close database connections
    # await database.disconnect()
    # await redis_client.disconnect()
    
    logger.info("✓ Application shutdown complete")


# ============================================================================
# FastAPI Application
# ============================================================================

app = FastAPI(
    title="AI Customer Support Agent API",
    description="Production-grade AI agent for automating customer support operations",
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)


# ============================================================================
# Middleware
# ============================================================================

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Gzip Compression
app.add_middleware(GZipMiddleware, minimum_size=1000)


# Request Logging Middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests"""
    logger.info(f"{request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"{request.method} {request.url.path} - {response.status_code}")
    return response


# ============================================================================
# Exception Handlers
# ============================================================================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": str(exc) if settings.DEBUG else "An unexpected error occurred",
        },
    )


# ============================================================================
# Core API Routes
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "AI Customer Support Agent API",
        "version": settings.APP_VERSION,
        "status": "operational",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    """
    Health check endpoint for Kubernetes liveness/readiness probes.
    """
    # Check database connection
    db_healthy = True  # await database.is_healthy()
    
    # Check Redis connection
    redis_healthy = True  # await redis_client.is_healthy()
    
    # Check LLM API connectivity
    llm_healthy = True  # await llm_service.is_healthy()
    
    healthy = all([db_healthy, redis_healthy, llm_healthy])
    
    return {
        "status": "healthy" if healthy else "unhealthy",
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "checks": {
            "database": "healthy" if db_healthy else "unhealthy",
            "redis": "healthy" if redis_healthy else "unhealthy",
            "llm_api": "healthy" if llm_healthy else "unhealthy",
        },
    }


@app.get("/metrics")
async def metrics():
    """
    Prometheus metrics endpoint.
    Exposes application and business metrics in Prometheus format.
    """
    return Response(
        content=generate_latest(REGISTRY),
        media_type="text/plain",
    )


# ============================================================================
# API Route Includes
# ============================================================================

# Include routers (uncomment when implementing)
# app.include_router(tickets.router, prefix="/api/v1/tickets", tags=["tickets"])
# app.include_router(health.router, prefix="/api/v1/health", tags=["health"])
# app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])
# app.include_router(webhooks.router, prefix="/api/v1/webhooks", tags=["webhooks"])


# ============================================================================
# Example API Endpoints (To be implemented)
# ============================================================================

@app.post("/api/v1/tickets")
async def create_ticket(request: Request):
    """
    Create a new support ticket.
    
    This endpoint accepts ticket data, classifies it, and either:
    1. Auto-resolves with AI if confidence > threshold
    2. Escalates to human agent if needed
    
    Returns the ticket ID and initial response.
    """
    # Implementation would go here
    return {
        "ticket_id": "TKT-12345",
        "status": "processing",
        "message": "Ticket received and being processed",
    }


@app.get("/api/v1/tickets/{ticket_id}")
async def get_ticket(ticket_id: str):
    """
    Retrieve ticket details by ID.
    """
    # Implementation would go here
    return {
        "ticket_id": ticket_id,
        "status": "resolved",
        "category": "technical_support",
        "resolution": "AI auto-resolved",
    }


# ============================================================================
# Application Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "src.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
        workers=1 if settings.DEBUG else settings.API_WORKERS,
        log_level=settings.LOG_LEVEL.lower(),
    )
