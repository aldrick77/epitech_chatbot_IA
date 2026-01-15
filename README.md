# Epitechsiteweb
Site vitrine avec un widget de chatbot EPITECH (frontend statique + API FastAPI).

## Apercu
- Frontend HTML/CSS/JS avec slider et widget de chat.
- Backend FastAPI qui interroge une base locale via MCP + un scraping via MCP + Ollama.
- Scraping mis en cache en memoire pour limiter les requetes.
- API disponible sur `http://127.0.0.1:8000`.

## Architecture (diagramme ASCII)
```
Utilisateur (navigateur)
        |
        v
[1] Frontend (HTML/CSS/JS)
        |
        v
[2] FastAPI (/chat)
        |
        v
[3] Agent (orchestrateur)
   |      |           |\
   |      |           | +--> Cache scraping (RAM)
   |      |           |
   |      |           +--> MCP Client -> MCP Server
   |      |                         |-> tool scrape_url -> Site EPITECH
   |      |                         |-> resources epitech/* -> Base locale (.txt)
   |      |
   |      +--> Fallback scraper direct -> Site EPITECH
   |
   +--> Ollama (LLM)

Reponse JSON -> Frontend -> Utilisateur
```

## Structure
- `frontend/` : page statique et widget de chat.
- `backend/` : API FastAPI et logique d'agent.
- `backend/data/epitech/` : base locale (fichiers `.txt`, optionnel).

## Prerequis
- Python 3 et `pip`.
- Ollama en local (par defaut sur `http://127.0.0.1:11434`) avec un modele dispo.

## Installation
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

## Demarrage
Backend (dans un terminal) :
```bash
cd backend
uvicorn main:app --reload --port 8000
```

Ollama (si besoin) :
```bash
ollama pull llama3.2
ollama serve
```

Frontend (au choix) :
```bash
cd frontend
python -m http.server 5173
```
Puis ouvrir `http://127.0.0.1:5173`.

## API
- `GET /health` : ping.
- `POST /chat` : envoie un message et recoit une reponse.

Exemple :
```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Bonjour","session_id":"demo"}'
```

## Configuration rapide
- Changer le modele Ollama : modifier `"model"` dans `backend/agent.py`.
- Changer le port backend cote frontend : modifier `BACKEND_PORT` dans `frontend/app.js`.
- Ajouter des connaissances locales : poser des `.txt` dans `backend/data/epitech/`.
- Ajuster le cache scraping : modifier `SCRAPE_CACHE_TTL_SEC` dans `backend/agent.py`.
