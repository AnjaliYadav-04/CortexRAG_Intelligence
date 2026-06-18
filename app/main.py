"""FastAPI application entrypoint — Enterprise Advanced RAG."""

from __future__ import annotations
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.api.routes import router
from app.config import settings

log = structlog.get_logger()

app = FastAPI(
    title="Enterprise Advanced RAG — K8s SRE Copilot",
    description=(
        "Production-grade RAG system with LangGraph, Hybrid Search, CRAG, "
        "Self-RAG, Text2SQL (HITL), 5-Tier Redis Cache, and 9-Layer Guardrails."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(router, prefix="/api/v1")


@app.get("/", tags=["Root"])
async def root():
    return {
        "service": "Enterprise Advanced RAG",
        "docs": "/docs",
        "health": "/api/v1/health",
    }


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    log.error("unhandled_exception", error=str(exc))
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})
