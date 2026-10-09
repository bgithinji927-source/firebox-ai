![FIREBOX AI icon](./firebox-ai-icon.svg)

# FIREBOX AI

A focused technical AI workspace by **FireboxTechs** for programming, cybersecurity, technical learning, document-grounded answers, and practical problem solving.

## Current application

FIREBOX AI now runs as a real FastAPI-backed application instead of a static-only dashboard.

- Dark ChatGPT-style responsive chat workspace
- MongoDB-backed conversations, messages, settings, document metadata, and processing state
- Ownership fields on persisted records for future multi-user isolation
- Indexed MongoDB collections with timestamps
- Local file storage for original uploaded documents
- PDF/text upload metadata endpoint with size and extension validation
- Configurable Ollama-compatible model adapter
- Backend health endpoint that reports MongoDB and model status honestly
- Graceful 503 responses when MongoDB or the model endpoint is unavailable
- No credentials or connection strings in frontend code
- Reusable FIREBOX AI SVG icon

The current preview has verified MongoDB connectivity. Live model generation is wired through `/api/chat`; it returns a clear unavailable response until an Ollama-compatible model endpoint is running.

## Backend setup

### 1. Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Set `MONGODB_URI` to your MongoDB deployment connection string. The value must stay in the backend environment and must never be placed in frontend JavaScript.

```env
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB_NAME=firebox_ai
FIREBOX_OWNER_ID=local-owner
STORAGE_DIR=storage/uploads
MODEL_BASE_URL=http://localhost:11434
MODEL_NAME=llama3.2
```

The managed project stores the production MongoDB URI as a protected environment value. The repository contains only `.env.example` placeholders.

### 3. Start the real application

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 3000
```

Open [http://localhost:3000](http://localhost:3000). API documentation is available at [http://localhost:3000/docs](http://localhost:3000/docs).

## MongoDB data model

The backend uses MongoDB as the primary application database. It does not use SQLite or PostgreSQL.

| Collection | Purpose |
| --- | --- |
| `conversations` | Conversation title, owner, creation time, and last update time |
| `messages` | User, assistant, and system messages linked to a conversation |
| `settings` | Per-owner model and web-search preferences |
| `documents` | Uploaded document metadata, storage key, checksum, and processing status |
| `document_chunks` | Extracted text chunk metadata for future retrieval and vector indexing |
| `web_research_cache` | Optional expiring web-search cache records |

Indexes are created at startup for ownership, timestamps, conversation message order, document status, chunk order, and cache expiration. Large originals are stored outside MongoDB in the configured `STORAGE_DIR`; MongoDB GridFS can be introduced later if the storage deployment requires it.

## API surface

- `GET /api/health` — MongoDB, storage, and model readiness
- `GET/POST /api/conversations` — list or create conversations
- `GET/DELETE /api/conversations/{id}` — retrieve or delete a conversation and its messages
- `POST /api/conversations/{id}/messages` — persist a message
- `GET/PATCH /api/settings` — retrieve or update owner preferences
- `GET /api/documents` — list uploaded document metadata
- `POST /api/documents/upload` — validate and store an uploaded document record
- `DELETE /api/documents/{id}` — delete metadata, indexed chunks, and the stored original
- `POST /api/chat` — call the configured Ollama-compatible model using conversation context

If MongoDB is unavailable, persistence endpoints return an error and the UI shows that the data was not saved. The application does not report successful storage when the operation failed.

## Model integration

The model adapter is separate from the database layer. Set `MODEL_BASE_URL` and `MODEL_NAME` for an Ollama-compatible inference server. The adapter sends a non-streaming `/api/chat` request with the recent conversation context. If the endpoint cannot be reached, `/api/chat` returns HTTP 503 instead of fabricating a response.

The current UI retains a clearly labeled local response fallback for development. It is not presented as a live model answer.

## Project structure

```text
.
├── Dockerfile                # production FastAPI container
├── backend/
│   ├── db.py                 # MongoDB client, indexes, and health state
│   ├── model_adapter.py      # Ollama-compatible model boundary
│   ├── repositories.py       # MongoDB persistence operations
│   ├── schemas.py            # Pydantic request contracts
│   └── main.py               # FastAPI routes and safe static serving
├── index.html                # dashboard markup
├── styles.css                # dark UI design system and responsive layout
├── app.js                    # client state and API synchronization
├── firebox-ai-icon.svg       # FIREBOX AI brand icon
├── public/                   # served asset copies and route manifest
├── .env.example              # safe configuration template
├── plan.md                   # implementation and design plan
└── TODO.md                   # product outcomes
```

## Roadmap

1. Add document text extraction, chunking, embeddings, and retrieval.
2. Add MongoDB Atlas Vector Search with a local vector-index fallback.
3. Add web search with source validation and research history.
4. Add authentication and enforce user ownership from verified identities rather than the temporary owner header.
5. Add streaming model responses and stop-generation support through the backend.
6. Add secure sandboxed programming tools.
7. Separate custom FIREBOX model research from the application runtime.

## License

Add a project license before public distribution. Keep the repository private while authentication, security controls, and data handling are being completed.
