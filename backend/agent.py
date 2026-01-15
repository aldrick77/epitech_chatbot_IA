# agent.py
import httpx
import logging
import re
import time
import unicodedata
from typing import Dict, List, Tuple, Optional

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
    Sélection simple des documents locaux en fonction des mots-clés de la question.
    On combine plusieurs fichiers si nécessaire.
    """
    q = question.lower()
    selected: List[str] = []
    selected_keys: List[str] = []

    # Formations / programmes / Pré-MSc / MSc / MBA / Bachelors / PGE
    if any(w in q for w in [
        "formation",
        "programme",
        "bachelor",
        "programme grande école",
        "pge",
        "pré-msc",
        "pre-msc",
        "msc",
        "mba",
    ]):
        if "formations_paris" in knowledge and "paris" in q:
            selected.append(knowledge["formations_paris"])
            selected_keys.append("formations_paris")
        if "formations" in knowledge:
            selected.append(knowledge["formations"])
            selected_keys.append("formations")

    # Admissions / inscription / candidature
    if any(w in q for w in ["admission", "inscription", "candidature", "concours", "parcoursup"]):
        if "admissions" in knowledge:
            selected.append(knowledge["admissions"])
            selected_keys.append("admissions")

    # Alternance / stage
    if any(w in q for w in ["alternance", "apprentissage", "stage", "rythme"]):
        if "alternance" in knowledge:
            selected.append(knowledge["alternance"])
            selected_keys.append("alternance")

    # Campus / villes
    if any(w in q for w in ["campus", "ville", "villes", "où se trouve", "où est situé"]):
        if "campus" in knowledge:
            selected.append(knowledge["campus"])
            selected_keys.append("campus")

    # Partenaires / entreprises / réseau
    if any(w in q for w in ["partenaire", "partenaires", "entreprise", "entreprises", "réseau"]):
        if "partenaires" in knowledge:
            selected.append(knowledge["partenaires"])
            selected_keys.append("partenaires")

    # Contexte global minimal si rien n'est matché
    if not selected:
        if "formations" in knowledge:
            selected.append(knowledge["formations"])
            selected_keys.append("formations")
        if "campus" in knowledge:
            selected.append(knowledge["campus"])
            selected_keys.append("campus")

    return "\n\n".join(selected), selected_keys


# Petite FAQ EPITECH codée en dur (contexte supplémentaire)
EPITECH_FAQ = [
    {
        "question": "formations epitech paris",
        "answer": (
            "À EPITECH Paris, les principales formations sont : "
            "le Programme Grande École en 5 ans, "
            "les Bachelors spécialisés en 3 ans, "
            "des MSc Pro dans 7 spécialités (IA, Big Data, Cybersécurité, Cloud, IoT, "
            "Réalité virtuelle, Business Technology Management) "
            "et plusieurs MSc/MBA orientés data, innovation et management des SI."
        ),
    },
    {
        "question": "admission epitech",
        "answer": (
            "L'admission à EPITECH repose sur l'étude du dossier et un entretien de motivation. "
            "Selon le programme, la candidature se fait via Parcoursup (Programme Grande École) "
            "ou hors Parcoursup (Bachelors, Pré‑MSc, MSc, MBA)."
        ),
    },
    {
        "question": "alternance epitech",
        "answer": (
            "De nombreux cursus EPITECH intègrent des stages longs et de l'alternance, "
            "notamment en 3e année de Bachelor, en MSc Pro et en MBA Data Science & BI, "
            "avec un fort lien au réseau d'entreprises partenaires."
        ),
    },
]


def build_knowledge_context() -> str:
    lines = []
    for item in EPITECH_FAQ:
        lines.append(f"Q: {item['question']}\nR: {item['answer']}")
    return "\n\n".join(lines) + "\n\n"


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
    return (
        system_context
        + "Voici quelques informations de reference sur EPITECH :\n"
        + knowledge_context
        + local_docs_context
        + external_knowledge
        + history_text
        + f"Utilisateur : {user_message}\n"
        + "En t'appuyant uniquement sur les informations ci-dessus, reponds precisement a la question.\n"
        + "Si certaines informations manquent, dis-le clairement et reste factuel.\n"
        + "Assistant :"
    )


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

    mcp_knowledge = await fetch_local_knowledge()
    if mcp_knowledge is None:
        if not LOCAL_KNOWLEDGE:
            LOCAL_KNOWLEDGE = LOCAL_KNOWLEDGE_FALLBACK
        LOCAL_KNOWLEDGE_CACHE_AT = now
        return LOCAL_KNOWLEDGE

    LOCAL_KNOWLEDGE = mcp_knowledge
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
    scraped = await call_scrape_url(url)
    if scraped is None:
        logger.warning("agent scraping via mcp failed url=%s fallback=direct", url)
        try:
            scraped = scrape_epitech_page(path)
        except Exception:
            scraped = ""

    put_cached_scrape(url, scraped)
    return scraped


async def run_agent(user_message: str, session_id: str) -> str:
    """
    Gère une conversation par session_id et répond uniquement sur la base
    des informations EPITECH (locales + scraping HTTP).
    """
    start_time = time.monotonic()
    logger.info("agent start session_id=%s message_len=%d", session_id, len(user_message))

    # Hard limits for payload size
    if len(user_message) > MAX_MESSAGE_CHARS:
        logger.warning("agent reject session_id=%s reason=message_too_long", session_id)
        return (
            "Message trop long. Merci de limiter votre question a "
            f"{MAX_MESSAGE_CHARS} caracteres."
        )

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
        return answer

    if is_gibberish(user_message):
        answer = (
            "Je n'ai pas compris votre message. "
            "Pouvez-vous reformuler votre question sur EPITECH ?"
        )
        history.append(("assistant", answer))
        conversations[session_id] = history
        logger.info("agent short-circuit session_id=%s reason=gibberish", session_id)
        return answer

    # Rôle système : on insiste sur "réponds de manière structurée et pédagogique"
    system_context = (
        "Tu es un conseiller EPITECH, l'école d'informatique.\n"
        "Tu dois répondre en français, de manière claire, structurée et concise.\n"
        "Tu réponds UNIQUEMENT aux questions sur EPITECH : "
        "formations, campus, modalités d'admission, alternance, frais, vie étudiante, débouchés.\n"
        "Tu NE DOIS PAS inventer de nouvelles questions, ni faire des exercices de mathématiques, "
        "de logique ou de culture générale qui ne concernent pas EPITECH.\n"
        "Tu dois répondre directement à la question de l'utilisateur en utilisant les informations "
        "fournies ci-dessous (base de connaissances locale, FAQ et extraits du site d'EPITECH).\n"
        "Si tu ne trouves pas la réponse dans ces informations, dis-le honnêtement "
        "et propose à l'utilisateur une autre question en lien avec EPITECH.\n\n"
        "Structure ta réponse avec des paragraphes courts et, si utile, des puces pour comparer les options.\n\n"
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

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "http://127.0.0.1:11434/api/generate",
            json={
                "model": "llama3.2",  # adapte si tu changes de modèle dans Ollama
                "prompt": prompt,
                "stream": False,
            },
            timeout=180,
        )

    data = resp.json()
    answer = data.get("response", "").strip()
    logger.info(
        "agent model response session_id=%s chars=%d preview=%s",
        session_id,
        len(answer),
        preview_text(answer),
    )

    # === GARDE-FOUS POSITIFS (ciblés) ===
    la = answer.lower()
    ql = user_message.lower()

    # 1) Questions sur le Pré-MSc
    if any(w in ql for w in ["pré-msc", "pre-msc"]):
        if "pré" not in la and "msc" not in la:
            answer = (
                "Le Pré‑MSc à EPITECH sert à consolider les fondamentaux techniques "
                "après un bac+2 ou un bac+3 avant d’entrer en MSc Pro ou en alternance. "
                "Pendant cette année, les étudiants renforcent leurs bases en administration "
                "système et réseaux, programmation orientée objet, développement web, "
                "DevOps, sécurité et méthodologie de projet, afin d’aborder sereinement "
                "les spécialisations avancées en MSc."
            )

    # 2) Questions PGE vs Bachelors
    elif any(w in ql for w in ["bachelor", "programme grande école", "pge"]):
        if "bachelor" not in la or "programme grande école" not in la:
            answer = (
                "Le Programme Grande École (PGE) d’EPITECH est un cursus en 5 ans "
                "qui mène à un niveau Bac+5 d’experte en technologies de l’information, "
                "avec une forte spécialisation et un passage à l’international.\n\n"
                "Les Bachelors sont des formations en 3 ans, plus courtes et très orientées "
                "métiers opérationnels (développeur full stack, data/IA, cybersécurité, "
                "cloud Web3, tech & business management). Ils permettent d’entrer rapidement "
                "sur le marché du travail, avec la possibilité de poursuivre ensuite en Bac+5."
            )

    # 3) Questions sur l’alternance
    elif "alternance" in ql or "apprentissage" in ql:
        if "alternance" not in la and "entreprise" not in la:
            answer = (
                "L’alternance à EPITECH permet de combiner cours et expérience en entreprise. "
                "Elle est particulièrement présente en 3e année de Bachelor, en MSc Pro et en MBA, "
                "avec des rythmes de type 3 jours en entreprise / 2 jours en cours, "
                "ou 4 jours en entreprise / 1 jour en cours pour certains MBA."
            )

    # 4) Questions sur les campus
    elif any(w in ql for w in ["campus", "ville", "villes"]):
        if not any(city in la for city in ["paris", "bordeaux", "lille", "lyon", "marseille"]):
            answer = (
                "EPITECH dispose d’un réseau d’environ 15 campus en France "
                "(Paris, Bordeaux, Lille, Lyon, Marseille, Montpellier, Nancy, Nantes, "
                "Nice, Rennes, Strasbourg, Toulouse, Mulhouse, Moulins, La Réunion) "
                "et de plusieurs implantations en Europe."
            )

    # 5) Questions sur les admissions
    elif any(w in ql for w in ["admission", "inscription", "candidature", "concours"]):
        if "entretien" not in la and "dossier" not in la:
            answer = (
                "Les admissions à EPITECH reposent sur l’étude du dossier et un entretien "
                "de motivation. Le Programme Grande École se fait via Parcoursup, tandis "
                "que les Bachelors, Pré‑MSc, MSc Pro et MBA recrutent hors Parcoursup, "
                "sur candidature en ligne puis entretien."
            )

    # ⚠️ SUPPRESSION du garde-fou global bloquant
    # À la place, si la réponse ne mentionne pas EPITECH, on renvoie quelque chose de neutre.
    la = answer.lower()
    if "epitech" not in la:
        answer = (
            "Je ne suis pas certain d’avoir bien répondu à ta question sur EPITECH. "
            "Peux-tu préciser si tu veux parler des formations, des admissions, de l’alternance "
            "ou des campus EPITECH ?"
        )

    # Ajout à l'historique
    history.append(("assistant", answer))
    conversations[session_id] = history
    logger.info("agent done session_id=%s elapsed_ms=%d", session_id, int((time.monotonic() - start_time) * 1000))

    return answer
