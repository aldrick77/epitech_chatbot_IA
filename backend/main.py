# main.py
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from agent import run_agent  # logique IA dans agent.py
from logging_utils import setup_logging


app = FastAPI()
logger = logging.getLogger("epitech.api")

setup_logging()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    logger.info("chat request session_id=%s message_len=%d", req.session_id, len(req.message))
    # Appel à la logique d'agent qui utilise Ollama
    answer = await run_agent(req.message, req.session_id)
    logger.info("chat response session_id=%s answer_len=%d", req.session_id, len(answer))
    return ChatResponse(answer=answer)
