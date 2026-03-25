# Epitech Chatbot

Site vitrine EPITECH avec un assistant IA intégré.

**Demo :** [GitHub Pages link] | **API :** [Render link]

---

## Stack

| Couche | Technologie |
|---|---|
| Frontend | HTML / CSS / JS (statique) |
| Backend | FastAPI + Uvicorn (Python) |
| LLM | Groq API — `llama-3.3-70b-versatile` |
| Hébergement | GitHub Pages (front) + Render (back) |

## Architecture

```
Navigateur
    │
    ▼
Frontend (HTML/CSS/JS)
    │  POST /chat
    ▼
FastAPI (agent.py)
    ├── Base de connaissance locale (data/epitech/*.txt)
    ├── Scraping epitech.fr (cache mémoire 30min)
    └── Groq API (LLM streaming)
```

## Structure

```
Epitech-INFO/
├── frontend/
│   ├── index.html
│   ├── styles.css
│   └── app.js
└── backend/
    ├── main.py          # API FastAPI
    ├── agent.py         # Logique IA + Groq
    ├── knowledge.py     # Chargement des .txt
    ├── scraper.py       # Scraping epitech.fr
    ├── requirements.txt
    └── data/epitech/    # Base de connaissance locale
```

## Installation locale

```bash
# Créer l'environnement virtuel
python -m venv .venv
.venv\Scripts\activate       # Windows
# source .venv/bin/activate  # Mac/Linux

# Installer les dépendances
pip install -r backend/requirements.txt
```

Créer `backend/.env` :
```
GROQ_API_KEY=ta_cle_groq_ici
```

Démarrer le backend :
```bash
cd backend
uvicorn main:app --reload --port 8000
```

Ouvrir `frontend/index.html` dans le navigateur.

## Déploiement

### Backend → Render
- Root Directory : `backend`
- Build Command : `pip install -r requirements.txt`
- Start Command : `uvicorn main:app --host 0.0.0.0 --port $PORT`
- Variable d'env : `GROQ_API_KEY`

### Frontend → GitHub Pages
- Mettre à jour `API_BASE_URL` dans `frontend/app.js` avec l'URL Render
- Activer GitHub Pages sur le repo (branche `main`, dossier `/frontend`)

## API

| Endpoint | Méthode | Description |
|---|---|---|
| `/health` | GET | Ping |
| `/chat` | POST | Envoyer un message |

```bash
curl -X POST https://ton-app.onrender.com/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Quelles sont les admissions ?", "session_id": "demo"}'
```

## Personnalisation

- **Ajouter des connaissances** : créer un `.txt` dans `backend/data/epitech/`
- **Changer le modèle** : modifier `GROQ_MODEL` dans `backend/agent.py`
- **Ajuster le cache scraping** : modifier `SCRAPE_CACHE_TTL_SEC` dans `backend/agent.py`
