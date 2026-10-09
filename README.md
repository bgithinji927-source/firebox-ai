![FIREBOX AI icon](./firebox-ai-icon.svg)

# FIREBOX AI

A focused technical AI workspace by **FireboxTechs**, designed for programming, cybersecurity, technical learning, and practical problem solving.

## Dashboard

This repository contains the first FIREBOX AI dashboard interface: a responsive, ChatGPT-style dark workspace with white typography and a monochrome FIREBOX brand system.

It includes:

- Dark responsive chat workspace
- Collapsible conversation sidebar
- Conversation history and new-chat flow
- Model selector and web-search control
- File attachment interface for future document retrieval
- Markdown-style assistant responses
- Code blocks with copy buttons
- Source citation links
- Regenerate and stop-generation controls
- System status and source-layer panels
- Reusable FIREBOX AI SVG icon

## Current status

The frontend is functional in **preview mode**. Client-side interactions are implemented, but a live language-model endpoint, document index, and web-search backend still need to be connected. The frontend keeps the integration seam at:

```text
POST /api/chat
```

It does not claim that a live model request was made when the endpoint is unavailable.

## Run locally

The dashboard is intentionally framework-free so it is easy to understand and modify.

```bash
python3 -m http.server 3000 --bind 0.0.0.0
```

Then open:

```text
http://localhost:3000
```

## Project structure

```text
.
├── index.html                 # dashboard markup
├── styles.css                 # dark UI design system and responsive layout
├── app.js                     # client-side state and interactions
├── firebox-ai-icon.svg        # FIREBOX AI brand icon
├── public/                    # served asset copies and route manifest
├── plan.md                    # implementation and design plan
└── TODO.md                    # product outcomes
```

## Design direction

The interface uses a dark, high-contrast workspace inspired by modern AI chat products: near-black navigation, charcoal conversation surfaces, white primary text, and restrained gray metadata. No purple, blue, green, or other accent colors are used.

## Roadmap

1. Connect a configurable local model through Ollama or a compatible inference backend.
2. Add persistent conversations and backend session storage.
3. Add PDF/text document ingestion, embeddings, retrieval, and citations.
4. Add configurable web search with source validation and citations.
5. Add secure, sandboxed programming tools.
6. Separate custom FIREBOX model research from the application runtime.

## License

Add a project license before public distribution. Until then, keep this repository private while backend security and data handling are being implemented.
