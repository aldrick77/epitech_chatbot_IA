# agent.py
import httpx
import logging
import os
import re
import time
import unicodedata
from typing import Dict, List, Tuple, Optional

from dotenv import load_dotenv
from groq import AsyncGroq

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = "llama-3.1-8b-instant"

from knowledge import load_local_knowledge as load_local_knowledge_files
from scraper import scrape_epitech_page, BASE_URL  # scraping HTTP simple
from mcp_client import call_scrape_url, fetch_local_knowledge

MAX_MESSAGE_CHARS = 800
MAX_PROMPT_CHARS = 12000
MAX_HISTORY_CHARS = 2000
MAX_HISTORY_ITEM_CHARS = 500
SCRAPE_CACHE_TTL_SEC = 1800
LOCAL_KNOWLEDGE_TTL_SEC = 600

logger = logging.getLogger("epitech.agent")

SCRAPE_CACHE: Dict[str, Tuple[float, str]] = {}
LOCAL_KNOWLEDGE: Dict[str, str] = {}
LOCAL_KNOWLEDGE_CACHE_AT = 0.0
LOCAL_KNOWLEDGE_FALLBACK = load_local_knowledge_files()

GREETING_TOKENS = {
    "bonjour",
    "bonsoir",
    "salut",
    "hello",
    "hey",
    "yo",
    "coucou",
    "cc",
    "bjr",
    "bsr",
    "slt",
}
SMALL_TALK_TOKENS = {"comment", "ca", "va", "cv", "cava", "commentcava"}
GIBBERISH_MAX_LEN = 12


def select_docs_for_question(question: str, knowledge: Dict[str, str]) -> tuple[str, list[str]]:
    """
    Routage intelligent : n'injecte que les documents locaux pertinents 
    pour éviter de saturer le quota Groq (limite de tokens par minute) 
    et limiter les hallucinations liées au surplus d'informations.
    """
    if not knowledge:
        return "", []

    q = normalize_text(question)
    selected_keys = set()

    if any(w in q for w in ["admission", "inscription", "candidature", "concours", "bac"]):
        selected_keys.add("admissions")
    if any(w in q for w in ["alternance", "apprentissage", "rythme", "entreprise", "contrat"]):
        selected_keys.add("alternance")
    if any(w in q for w in ["campus", "ville", "paris", "lyon", "bordeaux", "locaux", "strasbourg"]):
        selected_keys.add("campus")
    if any(w in q for w in ["formation", "programme", "pge", "bachelor", "msc", "mba", "option", "annee", "cursus"]):
        selected_keys.add("formations")
    if any(w in q for w in ["partenaire", "entreprise", "reseau", "international", "stage", "etranger"]):
        selected_keys.add("partenaires")

    # Fallback pour ne pas répondre sans contexte
    if not selected_keys:
        selected_keys = {"formations", "campus"}

    parts: List[str] = []
    keys: List[str] = []
    
    # On garantit l'ordre pour les tests / logs
    for key in sorted(list(selected_keys)):
        if key in knowledge:
            parts.append(f"[{key.upper()}]\n{knowledge[key]}")
            keys.append(key)

    return "\n\n".join(parts), keys


def build_knowledge_context() -> str:
    return ""


def clamp_text(text: str, max_chars: int, from_end: bool = False) -> str:
    if len(text) <= max_chars:
        return text
    return text[-max_chars:] if from_end else text[:max_chars]


def preview_text(text: str, max_chars: int = 120) -> str:
    return clamp_text(text.replace("\n", " ").strip(), max_chars)


def normalize_text(text: str) -> str:
    text = text.strip().lower()
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c))


def tokenize_text(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text)


def is_small_talk(text: str) -> bool:
    normalized = normalize_text(text)
    tokens = tokenize_text(normalized)
    if not tokens:
        return False
    allowed = GREETING_TOKENS | SMALL_TALK_TOKENS
    if not all(token in allowed for token in tokens):
        return False
    return any(token in GREETING_TOKENS or token in SMALL_TALK_TOKENS for token in tokens)


def is_gibberish(text: str) -> bool:
    normalized = normalize_text(text)
    tokens = tokenize_text(normalized)
    if len(tokens) != 1:
        return False
    if tokens[0] in GREETING_TOKENS or tokens[0] in SMALL_TALK_TOKENS:
        return False
    letters = re.sub(r"[^a-z]", "", normalized)
    if not letters or len(letters) < 3 or len(letters) > GIBBERISH_MAX_LEN:
        return False
    vowels = set("aeiouy")
    vowel_count = sum(1 for c in letters if c in vowels)
    if vowel_count == 0:
        return True
    max_consonants = 0
    run = 0
    for c in letters:
        if c in vowels:
            run = 0
        else:
            run += 1
            if run > max_consonants:
                max_consonants = run
    if max_consonants >= 4:
        return True
    if (vowel_count / len(letters)) < 0.25:
        return True
    return False


def compose_prompt(
    system_context: str,
    knowledge_context: str,
    local_docs_context: str,
    external_knowledge: str,
    history_text: str,
    user_message: str,
) -> str:
    prompt = system_context
    prompt += "--- CONTEXTE EPITECH ---\n"
    if local_docs_context:
        prompt += local_docs_context
    if knowledge_context:
        prompt += knowledge_context
    if external_knowledge:
        prompt += external_knowledge
    prompt += "--- FIN CONTEXTE ---\n\n"
    if history_text:
        prompt += "Historique :\n" + history_text + "\n"
    prompt += f"Question : {user_message}\n"
    prompt += "Réponse :\n"
    return prompt


# session_id -> liste de (role, content)
conversations: Dict[str, List[Tuple[str, str]]] = {}


def choose_scraping_path(question: str) -> str | None:
    """
    Choix de la page EPITECH à scraper en fonction de la question.
    Facile à faire évoluer en ajoutant des règles.
    """
    q = question.lower()

    # Formations / programmes
    if "paris" in q and any(w in q for w in ["formation", "programme", "pge", "bachelor", "msc", "mba"]):
        return "/fr/epitech-diplome-expert-informatique/"

    # Admissions
    if any(w in q for w in ["admission", "inscription", "candidature", "parcoursup", "concours"]):
        return "/fr/admissions/"

    # Alternance / MSc & MBA
    if any(w in q for w in ["alternance", "apprentissage", "rythme", "mba"]):
        return "/fr/formation-alternance/master-of-science-post-bac3/"

    # Par défaut : pas de scraping
    return None


async def get_local_knowledge() -> Dict[str, str]:
    global LOCAL_KNOWLEDGE, LOCAL_KNOWLEDGE_CACHE_AT
    now = time.monotonic()
    if LOCAL_KNOWLEDGE and (now - LOCAL_KNOWLEDGE_CACHE_AT) < LOCAL_KNOWLEDGE_TTL_SEC:
        return LOCAL_KNOWLEDGE

    # Direct function instead of MCP equivalent
    direct_knowledge = load_local_knowledge_files()
    if not direct_knowledge:
        if not LOCAL_KNOWLEDGE:
            LOCAL_KNOWLEDGE = LOCAL_KNOWLEDGE_FALLBACK
        LOCAL_KNOWLEDGE_CACHE_AT = now
        return LOCAL_KNOWLEDGE

    LOCAL_KNOWLEDGE = direct_knowledge
    LOCAL_KNOWLEDGE_CACHE_AT = now
    return LOCAL_KNOWLEDGE


def get_cached_scrape(url: str) -> Optional[str]:
    cached = SCRAPE_CACHE.get(url)
    if not cached:
        return None
    cached_at, text = cached
    if (time.monotonic() - cached_at) > SCRAPE_CACHE_TTL_SEC:
        SCRAPE_CACHE.pop(url, None)
        return None
    return text


def put_cached_scrape(url: str, text: str) -> None:
    SCRAPE_CACHE[url] = (time.monotonic(), text)


async def fetch_scraped_text(path: str) -> str:
    url = f"{BASE_URL}{path}"
    cached = get_cached_scrape(url)
    if cached is not None:
        logger.info("agent scraping cache hit url=%s chars=%d", url, len(cached))
        return cached

    logger.info("agent scraping cache miss url=%s", url)
    
    # Bypass MCP subprocess overhead (which takes 13s on Render free tier)
    try:
        scraped = scrape_epitech_page(path)
    except Exception as e:
        logger.error("agent scraping direct failed url=%s err=%s", url, e)
        scraped = ""

    if scraped:
        put_cached_scrape(url, scraped)
    return scraped or ""


async def run_agent(user_message: str, session_id: str):
    """
    Gère une conversation par session_id et répond en streamant
    les tokens au fur et à mesure (Ollama stream: True).
    """
    start_time = time.monotonic()
    logger.info("agent start session_id=%s message_len=%d", session_id, len(user_message))

    # Hard limits for payload size
    if len(user_message) > MAX_MESSAGE_CHARS:
        logger.warning("agent reject session_id=%s reason=message_too_long", session_id)
        yield (
            "Message trop long. Merci de limiter votre question a "
            f"{MAX_MESSAGE_CHARS} caracteres."
        )
        return

    # Historique
    history = conversations.get(session_id, [])
    history.append(("user", user_message))
    history = history[-6:]
    conversations[session_id] = history
    logger.info("agent history session_id=%s items=%d", session_id, len(history))

    if is_small_talk(user_message):
        answer = (
            "Bonjour ! Ca va bien, merci. "
            "Je suis l'assistant EPITECH. "
            "Pose-moi une question sur les formations, admissions, alternance ou campus."
        )
        history.append(("assistant", answer))
        conversations[session_id] = history
        logger.info("agent short-circuit session_id=%s reason=small_talk", session_id)
        yield answer
        return

    if is_gibberish(user_message):
        answer = (
            "Je n'ai pas compris votre message. "
            "Pouvez-vous reformuler votre question sur EPITECH ?"
        )
        history.append(("assistant", answer))
        conversations[session_id] = history
        logger.info("agent short-circuit session_id=%s reason=gibberish", session_id)
        yield answer
        return

    # Rôle système
    system_context = (
        "Tu es l'assistant EPITECH. Tu réponds toujours en français correct. "
        "Réponds à la question en utilisant UNIQUEMENT le CONTEXTE EPITECH ci-dessous. "
        "Si la réponse n'est pas dans le contexte, dis 'Je ne peux répondre qu'aux questions sur EPITECH.' "
        "Si la question ne concerne pas EPITECH, dis 'Je ne peux répondre qu'aux questions sur EPITECH.' "
        "Ne répète pas les réponses précédentes de l'historique.\n\n"
    )

    # Historique texte (sans le dernier message)
    history_text = ""
    for role, content in history[:-1]:
        prefix = "Utilisateur" if role == "user" else "Assistant"
        trimmed = clamp_text(content, MAX_HISTORY_ITEM_CHARS)
        history_text += f"{prefix} : {trimmed}\n"
    history_text = clamp_text(history_text, MAX_HISTORY_CHARS, from_end=True)

    # Scraping : logique centralisee (MCP + cache, fallback HTTP direct)
    scraped_text = ""
    path = choose_scraping_path(user_message)
    if path is not None:
        logger.info("agent scraping session_id=%s path=%s", session_id, path)
        scraped_text = await fetch_scraped_text(path)
        logger.info("agent scraping done session_id=%s chars=%d", session_id, len(scraped_text))
    else:
        logger.info("agent scraping skip session_id=%s", session_id)

    external_knowledge = ""
    if scraped_text:
        external_knowledge = (
            "Voici un extrait d'informations officielles provenant du site d'EPITECH :\n"
            + scraped_text[:2000]
            + "\n\n"
        )

    # FAQ + docs locaux
    knowledge_context = build_knowledge_context()
    local_knowledge = await get_local_knowledge()
    local_docs_text, local_doc_keys = select_docs_for_question(user_message, local_knowledge)
    logger.info(
        "agent local docs session_id=%s keys=%s",
        session_id,
        ",".join(local_doc_keys) if local_doc_keys else "none",
    )
    local_docs_context = (
        "Voici des informations provenant de la base de connaissances locale EPITECH :\n"
        + local_docs_text[:4000]
        + "\n\n"
        if local_docs_text
        else ""
    )

    # Prompt final with size cap
    prompt = compose_prompt(
        system_context,
        knowledge_context,
        local_docs_context,
        external_knowledge,
        history_text,
        user_message,
    )
    if len(prompt) > MAX_PROMPT_CHARS:
        logger.info("agent prompt trim session_id=%s step=drop_external", session_id)
        prompt = compose_prompt(
            system_context,
            knowledge_context,
            local_docs_context,
            "",
            history_text,
            user_message,
        )
    if len(prompt) > MAX_PROMPT_CHARS:
        logger.info("agent prompt trim session_id=%s step=drop_local", session_id)
        prompt = compose_prompt(
            system_context,
            knowledge_context,
            "",
            "",
            history_text,
            user_message,
        )
    if len(prompt) > MAX_PROMPT_CHARS:
        logger.info("agent prompt trim session_id=%s step=drop_history", session_id)
        prompt = compose_prompt(
            system_context,
            knowledge_context,
            "",
            "",
            "",
            user_message,
        )
    if len(prompt) > MAX_PROMPT_CHARS:
        logger.info("agent prompt trim session_id=%s step=hard_cap", session_id)
        prompt = clamp_text(prompt, MAX_PROMPT_CHARS)
    logger.info("agent prompt ready session_id=%s chars=%d", session_id, len(prompt))

    answer = ""
    token_buffer = ""
    client = AsyncGroq(api_key=GROQ_API_KEY)
    stream = await client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        stream=True,
        temperature=0.2,
        max_tokens=1024,
    )
    async for chunk in stream:
        token = chunk.choices[0].delta.content or ""
        if token:
            token_buffer += token
            # Post-traitement : corrections linguistiques
            token_buffer = token_buffer.replace("campuses", "campus")
            token_buffer = token_buffer.replace("Campuses", "Campus")
            # On envoie tout sauf les 10 derniers chars (au cas où un mot est coupé)
            if len(token_buffer) > 10:
                to_send = token_buffer[:-10]
                token_buffer = token_buffer[-10:]
                answer += to_send
                yield to_send
    # Flush du buffer restant
    if token_buffer:
        token_buffer = token_buffer.replace("campuses", "campus")
        token_buffer = token_buffer.replace("Campuses", "Campus")
        answer += token_buffer
        yield token_buffer

    logger.info("agent model response session_id=%s chars=%d", session_id, len(answer))

    # Ajout à l'historique une fois terminé
    history.append(("assistant", answer))
    conversations[session_id] = history
    logger.info("agent done session_id=%s elapsed_ms=%d", session_id, int((time.monotonic() - start_time) * 1000))
