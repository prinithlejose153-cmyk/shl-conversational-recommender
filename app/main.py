"""
SHL Conversational Assessment Recommender

FastAPI service exposing:
    GET  /         -> Service information
    GET  /health   -> Health check
    POST /chat     -> Stateless conversational recommender
"""

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .schemas import ChatRequest, ChatResponse
from .retrieval import CatalogIndex
from .agent import handle_chat


logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s — %(message)s"
)
logger = logging.getLogger("shl_recommender")


app = FastAPI(
    title="SHL Conversational Assessment Recommender",
    description=(
        "Conversational agent that recommends the most appropriate "
        "SHL Individual Test Solutions through natural dialogue."
    ),
    version="1.0.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ------------------------------------------------------------------
# Load SHL catalog once at startup
# ------------------------------------------------------------------

logger.info("Loading SHL catalog index...")
_index = CatalogIndex()
logger.info(f"Catalog ready: {len(_index.items)} assessments indexed.")


# ------------------------------------------------------------------
# Root Endpoint
# ------------------------------------------------------------------

@app.get("/")
def root():
    """
    Root endpoint providing service metadata.
    """
    return {
        "service": "SHL Conversational Assessment Recommender",
        "status": "running",
        "version": "1.0.0",
        "documentation": "/docs",
        "health": "/health",
        "chat_endpoint": "/chat",
    }


# ------------------------------------------------------------------
# Health Check
# ------------------------------------------------------------------

@app.get("/health")
def health():
    """
    Readiness probe.
    """
    return {"status": "ok"}


# ------------------------------------------------------------------
# Chat Endpoint
# ------------------------------------------------------------------

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """
    Stateless conversational endpoint.

    The client sends the full conversation history on every request.
    The service returns:
      - reply
      - recommendations
      - end_of_conversation
    """
    logger.info(f"POST /chat — {len(req.messages)} conversation turns")
    return await handle_chat(req.messages, _index)


# ------------------------------------------------------------------
# Global Exception Handler
# ------------------------------------------------------------------

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception")

    return JSONResponse(
        status_code=500,
        content={
            "reply": "An unexpected internal error occurred. Please try again.",
            "recommendations": [],
            "end_of_conversation": False,
        },
    )