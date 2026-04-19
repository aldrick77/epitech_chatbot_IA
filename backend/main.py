# main.py
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from agent import run_agent
from logging_utils import setup_logging

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
import json
import os
from datetime import datetime

app = FastAPI()
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

logger = logging.getLogger("epitech.api")

setup_logging()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://aldrick77.github.io",   # GitHub Pages (prod)
        "http://localhost:5500",          # Live Server (dev)
        "http://127.0.0.1:5500",         # Live Server (dev)
        "http://localhost:3000",          # Dev alternatif
        "null",                           # fichier local ouvert directement
    ],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)


class ChatRequest(BaseModel):
    message: str
    session_id: str  # identifiant de conversation (fourni par le front)


class ChatResponse(BaseModel):
    answer: str


class FeedbackRequest(BaseModel):
    session_id: str
    question: str
    answer: str
    thumb: int  # 1 (pour up), 0 (pour down)


@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/feedback")
@limiter.limit("10/minute")
async def feedback(request: Request, req: FeedbackRequest):
    logger.info("feedback received session_id=%s thumb=%d", req.session_id, req.thumb)
    
    data = {
        "timestamp": datetime.now().isoformat(),
        "session_id": req.session_id,
        "question": req.question,
        "answer": req.answer,
        "thumb": req.thumb
    }
    
    os.makedirs("data", exist_ok=True)
    log_file = "data/failed_queries.jsonl"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False) + "\n")
        
    return {"status": "ok"}


@app.post("/chat")
@limiter.limit("5/minute")
async def chat(request: Request, req: ChatRequest):
    logger.info("chat request session_id=%s message_len=%d", req.session_id, len(req.message))
    # Appel à la logique d'agent qui stream les tokens
    return StreamingResponse(run_agent(req.message, req.session_id), media_type="text/plain")
