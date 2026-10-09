![FIREBOX AI icon](./firebox-ai-icon.svg)

# FIREBOX AI

A single-workspace technical AI assistant for programming, cybersecurity, technical learning, document-grounded answers, and practical problem solving.

## What works in this version

- FastAPI serves the UI and backend from one Railway-compatible Docker service.
- MongoDB stores conversations, messages, settings, document metadata, and extracted document chunks.
- Chat requests start with the locally trained FIREBOX model checkpoint. No external model provider is required; Groq supervision is optional when `GROQ_API_KEY` is configured.
- When `GROQ_API_KEY` is configured, an optional Groq teacher reviews the local draft against retrieved evidence and rewrites it into a clear answer; local and extractive fallbacks remain available if Groq is unavailable.
- PDF and supported text files are validated, extracted, chunked, indexed in MongoDB, and made available for lexical retrieval. Retrieved passages include document and page references where available.
- The `/chat` experience provides capability cards, rich Markdown/code/table rendering, interactive checklists, copy/regenerate/verify actions, web-search toggles, source cards, and drag-free file attachment previews. PDF and supported text attachments become knowledge sources for the next answer; image, audio, and video files are previewed in the composer and clearly labeled when the current text checkpoint cannot inspect their contents.
- Optional web search uses Tavily for current source discovery only; it is not an AI model and is never used to generate answers.
- Server-side HTTP Basic Authentication protects the UI and API. `/api/health` is public and reports service readiness without exposing credentials.
- The single-workspace owner is fixed by `FIREBOX_OWNER_ID`; client-supplied owner headers are ignored.

This is a protected **single-workspace deployment**, not a multi-user SaaS product. It includes local lexical RAG, a small trainable CPU-friendly model, lessons, owner feedback, approved knowledge, evaluation metadata, and bounded local verification tools. It is not a ChatGPT-scale model and still requires a security review before public exposure.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with valid MongoDB credentials and a unique APP_USERNAME / APP_PASSWORD.
uvicorn backend.main:app --host 0.0.0.0 --port 3000
```

Open `http://localhost:3000`. The browser will request the configured HTTP Basic credentials. Health status is available at `/api/health`; API docs at `/docs` are protected.

The private training and administration dashboard is available at `/`. The clean customer-facing chatbot is available at `/chat`; it uses the same authenticated backend, document retrieval, and optional Groq teacher without exposing training controls.

## Required runtime configuration

Keep secrets only in the backend environment; never put them in frontend code or commit a populated `.env` file.

| Variable | Required | Purpose |
| --- | --- | --- |
| `MONGODB_URI` | Yes | MongoDB connection string (Atlas or another reachable MongoDB deployment) |
| `MONGODB_DB_NAME` | No | Database name; defaults to `firebox_ai` |
| `APP_USERNAME` | Yes | Username for the single-workspace Basic Auth gate |
| `APP_PASSWORD` | Yes | Strong, unique password for the workspace |
| `FIREBOX_CHECKPOINT` | Yes for chat | Path to a checkpoint created by the local training command |
| `TAVILY_API_KEY` | Optional | Enables web search when the user toggles it on |
| `GROQ_API_KEY` | Optional | Enables the real-time Groq teacher/supervisor |
| `GROQ_MODEL` | No | Groq model ID; defaults to `openai/gpt-oss-20b` |
| `GROQ_TIMEOUT_SECONDS` | No | Teacher request timeout; defaults to `20` |
| `STORAGE_DIR` | Yes for durable uploads | Upload path; attach a Railway Volume at `/app/storage` |
| `FIREBOX_OWNER_ID` | No | Fixed workspace owner identifier |

Without MongoDB or a trained local checkpoint, the app reports degraded/unavailable status and does not claim data was saved or an answer was generated. Web search stays unavailable until `TAVILY_API_KEY` is configured.

The Groq teacher is optional. Add `GROQ_API_KEY` as a secret Railway variable to enable it. It receives the user question, the local FIREBOX draft, and retrieved document passages; it is instructed to cite only those passages and to say when evidence is insufficient. The key is never sent to the browser.

When Groq returns a correction, it is saved as a **pending teacher review**. Clicking **Useful** approves that example; unapproved examples are never exported for training. Export approved examples and retrain locally with:

```bash
python training/export_teacher_dataset.py --output training_data/teacher_approved.jsonl
python training/train_firebox.py --data training_data/teacher_approved.jsonl --checkpoint storage/checkpoints/latest.pt --epochs 8
```

## Deploy to Railway

1. Push this repository to GitHub and create a Railway project using **Deploy from GitHub repo**.
2. Railway will build the included `Dockerfile`; the container binds to `0.0.0.0:$PORT`.
3. Add the environment variables above in the Railway service's Variables tab. Use fresh, unique values for `APP_USERNAME` and `APP_PASSWORD`.
4. Connect MongoDB (for example, MongoDB Atlas) and set `MONGODB_URI` and `MONGODB_DB_NAME`.
5. Attach a Railway Volume mounted at `/app/storage`, then train or copy a checkpoint to `/app/storage/checkpoints/latest.pt`.
6. Generate a Railway public domain only after the access password and MongoDB configuration are set. Check `/api/health`; verify local inference, MongoDB persistence, document processing, and web search separately.

Railway environment variables are not included in this repository. The deployment is not fully functional until MongoDB and a local FIREBOX checkpoint are configured.

## Train FIREBOX locally

The repository contains a deliberately small CPU-friendly GRU language model. It is a real trainable local model, not a scripted answer generator and not a wrapper around an external model. Start with the smoke-test corpus, then replace it with legally usable technical examples:

```bash
python training/train_firebox.py --data training_data/starter.jsonl --checkpoint storage/checkpoints/latest.pt --epochs 8
```

For Railway, run training in a separate worker/job and save the checkpoint on the persistent `/app/storage` volume. MongoDB stores conversations, document chunks, feedback, lessons, knowledge, and training metadata; it does not store large tensor files.

## API surface

- `GET /api/health` — dependency status (public, no secrets returned)
- `GET/POST /api/conversations` — list or create conversations
- `GET/PATCH/DELETE /api/conversations/{id}` — retrieve, rename, or delete a conversation
- `POST /api/conversations/{id}/messages` — persist a message
- `GET/PATCH /api/settings` — retrieve or update model/search preferences
- `GET /api/documents` — list processed documents
- `POST /api/documents/upload` — validate, extract, chunk, and index supported files
- `DELETE /api/documents/{id}` — delete a document, its chunks, and its stored file
- `POST /api/chat` — call the local FIREBOX checkpoint with conversation context and retrieved evidence
- `/api/learning/*` — feedback, lessons, approved knowledge, and training-run metadata
- `POST /api/tools/verify` — safe local Python syntax, JSON, and arithmetic checks; never executes user code

User interface routes:

- `/` — private training and administration dashboard
- `/chat` — customer-facing FIREBOX chatbot

## Tests

```bash
python -m unittest discover -s tests -v
python -m compileall -q backend
node --check app.js
```

The included unit tests cover text extraction, page-aware chunking, and ignoring caller-controlled owner IDs. Integration tests require MongoDB, a trained local checkpoint, and (for web search) Tavily credentials.

## Project layout

```text
backend/main.py          FastAPI routes, auth gate, uploads, retrieval, search
backend/db.py            MongoDB connection and indexes
backend/repositories.py  Persistence operations
backend/model_adapter.py Local FIREBOX checkpoint adapter
backend/teacher_supervisor.py Optional Groq answer reviewer
backend/firebox_model/   Tokenizer, model, runtime, and training utilities
training/                 Local training entry point
training_data/            Starter JSONL corpus and dataset guidance
app.js                   Frontend interactions and API synchronization
chat.html / chat.css     Customer-facing chatbot interface
chat.js                  Customer-facing chatbot behavior
index.html / styles.css  FIREBOX AI interface
Dockerfile               Railway container runtime
.env.example             Safe configuration template
```
