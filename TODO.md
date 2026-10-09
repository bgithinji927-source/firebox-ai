# FIREBOX AI Dashboard — Outcomes

- [x] Deliver a complete responsive FIREBOX AI dashboard with a clean chat interface, collapsible conversation sidebar, conversation history, new-chat action, multiline composer, file uploads, web-search control, model selection, markdown-style responses, syntax-highlighted code blocks, copy buttons, source citations, loading indicators, clear error states, stop-generation control, regenerate action, and desktop/mobile layouts.
- [x] Use the supplied FIREBOX AI icon and apply a black-and-white/grayscale-only visual system across backgrounds, text, borders, controls, icons, states, and typography without purple or other colored accents.
- [x] Make the frontend demonstrably interactive: switch conversations, create new chats, toggle web search, change models, select/remove files, submit a message, show generation state, stop generation, regenerate the last response, copy code, and open source citations.
- [x] Keep the preview honest and maintainable by showing the backend connection state, preserving a clear `/api/chat` integration seam, and avoiding claims that a live model request or database save succeeded when it did not.
- [x] Provide a route manifest and project metadata so the managed web preview can serve and identify the dashboard correctly.
- [x] Use MongoDB as the primary application database for conversations, messages, settings, document metadata, document chunks, and processing state; do not use SQLite or PostgreSQL.
- [x] Keep MongoDB credentials in protected backend environment variables, include `.env.example`, and never expose connection strings in frontend code.
- [x] Add graceful MongoDB failure handling so failed operations return errors and the UI does not claim that data was saved.
- [x] Add a FastAPI/PyMongo backend with ownership fields, timestamps, indexes, conversation/message CRUD, settings persistence, document metadata upload/delete, and a configurable Ollama-compatible model boundary.
- [ ] Add document text extraction, chunking, embeddings, MongoDB Atlas Vector Search support, and a compatible local retrieval fallback.
