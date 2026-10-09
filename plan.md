# FIREBOX AI Dashboard — Plan & Design

## Product scope

Create a responsive, browser-based FIREBOX AI dashboard shell that feels like a real assistant product and is ready to connect to a model, document retrieval service, and web-search backend. This first project is intentionally frontend-first: it provides meaningful client-side interactions and clearly marks the preview-mode boundary instead of pretending a backend is connected.

## Implementation approach

- Use semantic HTML, plain CSS, and vanilla JavaScript so a beginner can read and maintain the project without a build framework.
- Keep the app as a static web project served on port 3000.
- Put the reusable brand icon in `public/firebox-ai-icon.svg`.
- Keep the route manifest at `public/manus-routes.json`.
- Use `app.js` for UI state: conversation switching, composing/sending messages, preview responses, file-chip handling, model/search controls, copy buttons, regenerate, stop generation, and mobile sidebar behavior.
- Preserve future integration seams with a single `API_BASE_URL` constant and an optional `/api/chat` request path; when unavailable, the UI explicitly stays in preview mode.

## Design direction

### Design movement

Monochrome neo-industrial editorial: a quiet, high-contrast interface that combines terminal discipline with a premium technical workspace.

### Core principles

1. **Signal over decoration** — every control earns its place and the hierarchy is readable at a glance.
2. **Hard contrast, soft rhythm** — black and white create authority while spacing, rounded corners, and subtle transitions keep the experience calm.
3. **Visible system state** — model, search, preview mode, files, citations, and generation status are surfaced instead of hidden.
4. **Built for focus** — the chat workspace is the visual center; secondary tools stay in the rail or compact utility bar.

### Color philosophy

Use only near-black, charcoal, white, and a restrained grayscale ladder. The dark canvas reduces visual noise and makes white typography feel decisive; softer grays are reserved for metadata and boundaries. No purple, blue, green, or other accent hues are used.

### Layout paradigm

Use a left command rail plus an offset main workspace. The sidebar is a persistent navigation spine on desktop and a slide-in drawer on mobile. The main chat column uses a wide reading measure and a separate utility rail to avoid an undifferentiated dashboard grid.

### Signature elements

- FIREBOX icon: a geometric flame core inside a rounded box.
- Thin ruled dividers and monospaced system labels.
- Charcoal command surfaces with white type, echoing a focused ChatGPT-style workspace.

### Interaction philosophy

Interactions are direct and reversible. Buttons show clear hover/focus states, toggles expose their state in text, file selection is represented as a removable chip, and destructive actions require an explicit second step only where needed. The preview fallback is honest and visible.

### Animation

Use short 150–220ms ease-out transitions for surfaces, buttons, chips, and drawer movement. Use a restrained three-dot pulse for generation. Avoid looping motion except while work is active. Respect `prefers-reduced-motion` by removing transitions and pulsing.

### Typography system

Use a system sans stack for readable interface text and a system monospace stack for labels, model metadata, status pills, code, and citations. Headlines are compact and weighty; body copy stays at 15–16px with 1.55 line height; metadata is uppercase with letter spacing.

### Brand essence

**Positioning:** a focused technical AI workspace for builders who want signal, sources, and practical next steps.

**Personality:** precise, capable, grounded.

### Brand voice

Headlines and CTAs are concise, active, and specific. Microcopy explains what the system is doing without hype.

- “Make the next technical decision clearer.”
- “Attach a source, then ask the hard question.”

### Wordmark & logo

Use the FIREBOX mark as a geometric flame-in-box icon next to a two-line wordmark: `FIREBOX` in strong uppercase and `AI / TECHNICAL ASSISTANT` in monospaced microtype.

### Signature brand color

The ownable brand color for this requested version is **ink black** (`#050505`) paired with charcoal surfaces and white type. The identity is intentionally built from contrast rather than hue.

## Project structure

```text
fireboxai/
├── index.html                 # semantic application shell
├── styles.css                 # monochrome design system and responsive layout
├── app.js                     # client-side state and interactions
├── app.config.ts              # project logo metadata
├── plan.md                    # this implementation and design plan
├── TODO.md                    # deliverable outcomes and acceptance clauses
└── public/
    ├── firebox-ai-icon.svg    # reusable brand mark
    └── manus-routes.json       # route manifest for the web preview
```
