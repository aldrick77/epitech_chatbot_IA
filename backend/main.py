# main.py
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from agent import run_agent  # logique IA dans agent.py
from logging_utils import setup_logging


app = FastAPI()
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


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat")
async def chat(req: ChatRequest):
    logger.info("chat request session_id=%s message_len=%d", req.session_id, len(req.message))
    # Appel à la logique d'agent qui stream les tokens
    return StreamingResponse(run_agent(req.message, req.session_id), media_type="text/plain")
