![FIREBOX AI icon](./firebox-ai-icon.svg)

# FIREBOX AI

A single-workspace technical AI assistant for programming, cybersecurity, technical learning, document-grounded answers, and practical problem solving.

## What works in this version

- FastAPI serves the UI and backend from one Railway-compatible Docker service.
- MongoDB stores conversations, messages, settings, document metadata, and extracted document chunks.
- Chat requests use a configured OpenAI-compatible or Ollama-compatible model. No scripted fallback answers are returned.
- PDF and supported text files are validated, extracted, chunked, indexed in MongoDB, and made available for lexical retrieval. Retrieved passages include document and page references where available.
- Optional web search uses Tavily and includes real result links. If a provider is not configured or fails, the request returns an explicit error rather than fabricated sources.
- Server-side HTTP Basic Authentication protects the UI and API. `/api/health` is public and reports service readiness without exposing credentials.
- The single-workspace owner is fixed by `FIREBOX_OWNER_ID`; client-supplied owner headers are ignored.

This is a protected **single-workspace deployment**, not a multi-user SaaS product. It does not yet include individual user accounts, streaming token output, vector embeddings, or a formal security review. Do not claim full production readiness until the required services are configured and integration checks are completed.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with valid MongoDB credentials, model configuration,
# and a unique APP_USERNAME / APP_PASSWORD.
uvicorn backend.main:app --host 0.0.0.0 --port 3000
```

Open `http://localhost:3000`. The browser will request the configured HTTP Basic credentials. Health status is available at `/api/health`; API docs at `/docs` are protected.

## Required runtime configuration

Keep secrets only in the backend environment; never put them in frontend code or commit a populated `.env` file.

| Variable | Required | Purpose |
| --- | --- | --- |
| `MONGODB_URI` | Yes | MongoDB connection string (Atlas or another reachable MongoDB deployment) |
| `MONGODB_DB_NAME` | No | Database name; defaults to `firebox_ai` |
| `APP_USERNAME` | Yes | Username for the single-workspace Basic Auth gate |
| `APP_PASSWORD` | Yes | Strong, unique password for the workspace |
| `MODEL_PROVIDER` | Yes for chat | `openai` or `ollama` |
| `MODEL_BASE_URL` | Yes for chat | Provider base URL; for OpenAI use `https://api.openai.com/v1` |
| `MODEL_NAME` | Yes for chat | Exact model identifier supported by the provider |
| `MODEL_API_KEY` | OpenAI | Provider API key; not used by Ollama mode |
| `TAVILY_API_KEY` | Optional | Enables web search when the user toggles it on |
| `STORAGE_DIR` | Yes for durable uploads | Upload path; attach a Railway Volume at `/app/storage` |
| `FIREBOX_OWNER_ID` | No | Fixed workspace owner identifier |

Without MongoDB or model configuration, the app reports degraded/unavailable status and does not claim data was saved or an answer was generated. Web search stays unavailable until `TAVILY_API_KEY` is configured.

## Deploy to Railway

1. Push this repository to GitHub and create a Railway project using **Deploy from GitHub repo**.
2. Railway will build the included `Dockerfile`; the container binds to `0.0.0.0:$PORT`.
3. Add the environment variables above in the Railway service's Variables tab. Use fresh, unique values for `APP_USERNAME` and `APP_PASSWORD`; add provider credentials in Railway, not in this repository.
4. Connect MongoDB (for example, MongoDB Atlas) and set `MONGODB_URI` and `MONGODB_DB_NAME`.
5. Attach a Railway Volume mounted at `/app/storage` so uploaded original files survive container restarts and redeploys.
6. Generate a Railway public domain only after the access password and data-provider configuration are set. Check `/api/health`; verify chat, MongoDB persistence, document processing, and web search separately.

Railway environment variables are not included in this repository. The deployment is not fully functional until the required external service values are configured.

## API surface

- `GET /api/health` — dependency status (public, no secrets returned)
- `GET/POST /api/conversations` — list or create conversations
- `GET/PATCH/DELETE /api/conversations/{id}` — retrieve, rename, or delete a conversation
- `POST /api/conversations/{id}/messages` — persist a message
- `GET/PATCH /api/settings` — retrieve or update model/search preferences
- `GET /api/documents` — list processed documents
- `POST /api/documents/upload` — validate, extract, chunk, and index supported files
- `DELETE /api/documents/{id}` — delete a document, its chunks, and its stored file
- `POST /api/chat` — call the configured model with conversation context and retrieved evidence

## Tests

```bash
python -m unittest discover -s tests -v
python -m compileall -q backend
node --check app.js
```

The included unit tests cover text extraction, page-aware chunking, and ignoring caller-controlled owner IDs. Integration tests still require a reachable MongoDB, model provider, and (for web search) Tavily credentials.

## Project layout

```text
backend/main.py          FastAPI routes, auth gate, uploads, retrieval, search
backend/db.py            MongoDB connection and indexes
backend/repositories.py  Persistence operations
backend/model_adapter.py OpenAI-compatible / Ollama model client
app.js                   Frontend interactions and API synchronization
index.html / styles.css  FIREBOX AI interface
Dockerfile               Railway container runtime
.env.example             Safe configuration template
```
