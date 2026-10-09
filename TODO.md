# FIREBOX AI — implementation status

## Implemented in the current codebase

- [x] Preserve the existing FIREBOX AI responsive monochrome interface and branding.
- [x] Remove scripted local chat answers and seeded conversation history; model failures are explicit.
- [x] Connect chat to configurable OpenAI-compatible and Ollama-compatible APIs, with recent persisted conversation context.
- [x] Persist conversations, messages, settings, document metadata, and extracted chunks in MongoDB.
- [x] Support conversation listing, loading, renaming, and deletion from the UI/API.
- [x] Add server-side single-workspace Basic Authentication and ignore client-supplied owner IDs.
- [x] Validate and process supported PDFs/text files with text extraction, chunking, MongoDB indexing, retrieval, and document/page citations.
- [x] Connect optional real web search through Tavily and return source titles and URLs; report missing keys and provider errors honestly.
- [x] Implement actual model selection/search settings persistence, attachment processing, and best-effort request cancellation.
- [x] Add Railway Dockerfile selection and a public health-check route; configure durable uploads via a Railway Volume.
- [x] Add unit tests for text extraction, page-aware chunking, owner-header rejection, and HTTP Basic Auth.

## Required before a useful Railway deployment

- [ ] Configure `MONGODB_URI` and verify real MongoDB connectivity/persistence.
- [ ] Configure `APP_USERNAME` and a strong `APP_PASSWORD` before exposing a public domain.
- [ ] Configure `MODEL_PROVIDER`, `MODEL_BASE_URL`, `MODEL_NAME`, and (for OpenAI-compatible services) `MODEL_API_KEY`; test real generation.
- [ ] Configure `TAVILY_API_KEY` if web search is required and verify real source retrieval.
- [ ] Attach a Railway Volume at `/app/storage` and verify uploaded originals survive a restart.
- [ ] Run end-to-end integration checks against the actual Railway services.

## Remaining work / limitations

- [ ] Implement per-user accounts and authorization; this version is intentionally single-workspace behind one Basic Auth credential.
- [ ] Add streaming output and provider-level cancellation where supported; current stop action aborts the in-flight request on a best-effort basis.
- [ ] Add semantic embeddings/vector search; current document retrieval is lexical keyword scoring.
- [ ] Add robust document deletion/list management controls and a standalone knowledge-library view.
- [ ] Add rate limiting, audit logging, observability, backup/restore, and a formal security review.

No external database, model, or search integration has been declared verified unless that integration was actually tested with its credentials.
