"""
SHL Conversational Assessment Recommender
FastAPI service — two endpoints:
  GET  /health  →  readiness check
  POST /chat    →  stateless conversational agent
"""
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .schemas import ChatRequest, ChatResponse
from .retrieval import CatalogIndex
from .agent import handle_chat

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s — %(message)s")
logger = logging.getLogger("shl_recommender")

app = FastAPI(
    title="SHL Conversational Assessment Recommender",
    description=(
        "Conversational agent that guides hiring managers to the right "
        "SHL Individual Test Solutions through natural dialogue."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

# Catalog loaded once at startup — BM25 index over data/catalog.json
logger.info("Loading SHL catalog index…")
_index = CatalogIndex()
logger.info(f"Catalog ready: {len(_index.items)} assessments indexed.")


@app.get("/health")
def health():
    """Readiness probe. Returns 200 + status ok when service is up."""
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """
    Stateless conversational endpoint.
    The full conversation history must be sent on every call.
    Returns the agent's next reply and, when ready, a structured shortlist.
    """
    logger.info(f"POST /chat — {len(req.messages)} turns")
    return await handle_chat(req.messages, _index)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "reply": "An unexpected error occurred. Please try again.",
            "recommendations": [],
            "end_of_conversation": False,
        },
    )
