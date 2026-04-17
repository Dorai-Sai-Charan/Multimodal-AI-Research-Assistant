# Context Summary — Frontend Migration (Streamlit → Next.js 15)

> Living document. Every time the frontend is updated, this file is updated in the same change.

---

## 1. Project

- **Repo:** `Multimodal-AI-Research-Assistant` (cloned from `https://github.com/Dorai-Sai-Charan/Multimodal-AI-Research-Assistant.git`)
- **What it is:** Research assistant that does Multimodal RAG + Agentic (ReAct) reasoning over uploaded research PDFs. Extracts text, tables, images, equations; embeds into ChromaDB; answers via Groq / Gemini-Vision.
- **Backend (unchanged):** FastAPI app in `src/`, entrypoint `python -m src.main`, listens on `:8000`. Routes live in `src/api/routes.py`.
- **Original frontend:** Streamlit app in `src/ui/app.py` (`streamlit run src/ui/app.py`). Hits `API_URL=http://localhost:8000/api`.

---

## 2. Conversation log (user ↔ assistant)

### Turn 1 — user
> "I want to clone this https://github.com/Dorai-Sai-Charan"

**Assistant:** Pointed out that URL is a user profile not a repo. Asked which specific repo.

### Turn 2 — user
> "https://github.com/Dorai-Sai-Charan/Multimodal-AI-Research-Assistant.git"

**Assistant:** Cloned into `/home/nst-kaja/Documents/Dorai/Multimodal-AI-Research-Assistant`.

### Turn 3 — user
> "the frontend is streamlit, i want to change into great UI other than streamlit. What is the best UI option tech stack for fantastic ui"

**Assistant:** Recommended **Next.js 15 + React + Tailwind + shadcn-style components + Vercel AI SDK + Zustand + Framer Motion + react-pdf + KaTeX**. Listed runner-ups (SvelteKit, Nuxt, Remix, Chainlit). Asked whether to scaffold.

### Turn 4 — user
> "Yes i want you to continue with this tech stack. I want you to migrate all the frontend from streamlit to this techstack. The backend logic and everything needs to be remain same but only UI needs to be changed. along with this whatever the context is there, the prompts i asked and the response you give, maintain a context summmary.md. Whenever you update the code, update the contextsummary.md also. Keep this in mind that the backend logic and everything should be same, only UI needs to be changed"

**Assistant:** Read the Streamlit app and FastAPI routes to enumerate every feature, then scaffolded the new frontend in `frontend/` (see §3–6). Backend files were not touched. Typecheck and `next build` both pass cleanly.

---

## 3. Hard constraints from the user

1. **Backend is untouched.** No Python files were modified.
2. **Feature parity.** Every tab, every button, every API call in the Streamlit UI has an equivalent in the new UI.
3. **Better UI** than Streamlit.
4. **Keep this file updated** on every future code change.

---

## 4. Frontend tech stack (as implemented)

| Concern | Choice | Why |
|---|---|---|
| Framework | **Next.js 15.1** (App Router, React 19) | SSR + route handlers for the API proxy |
| Styling | **Tailwind CSS 3.4** + custom gradient theme | Hand-rolled, no shadcn CLI needed |
| State | **Zustand 5** with `persist` middleware | Lightweight, persists chat + settings to `localStorage` |
| Markdown | **react-markdown** + `remark-gfm` + `remark-math` + `rehype-katex` + `rehype-highlight` | GitHub-flavored + LaTeX + code highlighting (matches backend outputs) |
| Motion | **framer-motion 11** | Message enter/exit, collapsible panels |
| Icons | **lucide-react** | Consistent icon set |
| Toast | **sonner** (installed, not yet wired) | For future use |
| TS | **TypeScript 5.7** | Full typing across API boundary |

Node requirement: 18.18+. System has 18.19.1.

---

## 5. Directory layout (new)

```
Multimodal-AI-Research-Assistant/
├── src/                          ← UNCHANGED (FastAPI backend)
│   ├── api/routes.py
│   ├── main.py
│   └── ui/app.py                 ← original Streamlit, kept for reference
├── frontend/                     ← NEW Next.js app
│   ├── package.json
│   ├── tsconfig.json
│   ├── next.config.mjs
│   ├── tailwind.config.ts
│   ├── postcss.config.mjs
│   ├── .env.local.example        BACKEND_API_URL=http://localhost:8000/api
│   ├── app/
│   │   ├── layout.tsx            Sidebar + main
│   │   ├── globals.css           Theme, prose, utilities
│   │   ├── page.tsx              Chat Assistant (default tab)
│   │   ├── compare/page.tsx      Compare Papers tab
│   │   ├── survey/page.tsx       Literature Survey + Research Gaps tabs
│   │   ├── search/page.tsx       Semantic Search + Explain tabs
│   │   ├── trends/page.tsx       Trends + Recommend + Summarize tabs
│   │   └── api/[...path]/route.ts  Catch-all proxy to FastAPI
│   ├── components/
│   │   ├── sidebar.tsx           Logo, nav, settings, upload, docs list, stats
│   │   ├── model-settings.tsx    Presets, model selector, sliders, advanced
│   │   ├── upload-panel.tsx      Drag-and-drop PDF upload
│   │   ├── document-list.tsx     Polled list + delete + stats cards
│   │   ├── chat-panel.tsx        Full chat with Agent/Multi-doc toggles
│   │   ├── markdown.tsx          Markdown renderer
│   │   ├── citations.tsx         Collapsible citation list with relevance bars
│   │   ├── reasoning-steps.tsx   ReAct agent trace (Thought/Action/Observation)
│   │   ├── page-header.tsx       Shared header + ResultCard (loading/error/empty)
│   │   ├── result-view.tsx       Renders answer + citations + reasoning + meta
│   │   ├── models-bootstrap.tsx  Client bootstrap that fetches /api/models once
│   │   └── ui/                   Button, Input/Textarea, Slider, Select, Toggle, Card, Tabs, Spinner, Collapsible
│   └── lib/
│       ├── api.ts                Typed client (one function per FastAPI endpoint)
│       ├── types.ts              Mirrors Pydantic models in src/api/routes.py
│       ├── store.ts              Zustand store + buildLLMConfig helper
│       ├── hooks.ts              useDocumentsPolling, useInitModels, useTunablePayload, useAsync
│       └── utils.ts              cn(), formatPercent, truncate
└── context_summary.md            ← this file
```

---

## 6. Feature parity matrix

Every Streamlit surface → Next.js surface. Payloads identical to `src/api/routes.py` — backend contract preserved.

| Streamlit tab / control | API call | Next.js route / component |
|---|---|---|
| Sidebar — Model Settings (presets, model dropdown, sliders, advanced panel, reset) | `GET /api/models` | `components/model-settings.tsx` |
| Sidebar — Upload PDF | `POST /api/upload` | `components/upload-panel.tsx` |
| Sidebar — Uploaded papers list + delete | `GET /api/documents`, `DELETE /api/documents/{id}` | `components/document-list.tsx` (polls every 4s) |
| Sidebar — Stats cards | derived | `DocumentStats` in `document-list.tsx` |
| Tab 1: Chat — Agent Mode toggle | `POST /api/agent` | `app/page.tsx` + `components/chat-panel.tsx` |
| Tab 1: Chat — Multi-doc toggle | `POST /api/multi-doc` | `chat-panel.tsx` |
| Tab 1: Chat — default (with paper filter) | `POST /api/query` | `chat-panel.tsx` |
| Tab 1: Clear conversation | — | `chat-panel.tsx` |
| Tab 2: Compare Papers | `POST /api/compare` | `app/compare/page.tsx` |
| Tab 3a: Literature Survey | `POST /api/literature-survey` | `app/survey/page.tsx` (SurveyTab) |
| Tab 3b: Research Gaps | `POST /api/research-gaps` | `app/survey/page.tsx` (GapsTab) |
| Tab 4a: Semantic Search | `POST /api/query` | `app/search/page.tsx` (SearchTab) |
| Tab 4b: Explain Concept / Diagram / Table | `POST /api/explain` | `app/search/page.tsx` (ExplainTab) |
| Tab 5a: Research Trends | `POST /api/trends` | `app/trends/page.tsx` (TrendsTab) |
| Tab 5b: Recommendations | `POST /api/recommend` | `app/trends/page.tsx` (RecommendTab) |
| Tab 5c: Summarize | `POST /api/summarize` | `app/trends/page.tsx` (SummaryTab) |
| Citations panel (all tabs) | — | `components/citations.tsx` |
| Reasoning-step trace (Agent mode) | — | `components/reasoning-steps.tsx` |

The `llm_config` + `similarity_threshold` from model settings are auto-injected into every request body by `useTunablePayload()` — exactly mirroring the old Streamlit `api_post()` helper.

---

## 7. Running it

```bash
# Terminal 1 — backend (unchanged)
cd Multimodal-AI-Research-Assistant
python -m src.main                    # FastAPI on :8000

# Terminal 2 — new frontend
cd Multimodal-AI-Research-Assistant/frontend
cp .env.local.example .env.local      # optional; defaults to http://localhost:8000/api
npm install                           # first time only
npm run dev                           # Next.js on :3000
```

Browser → `http://localhost:3000`.

The Next.js server proxies `/api/*` → `BACKEND_API_URL` (default `http://localhost:8000/api`). So there's no CORS dance and the browser doesn't need to know the backend host.

---

## 8. UI design language

- Dark-first with a deep purple/cyan/pink radial-gradient mesh background
- `.glass` utility for frosted panels
- `gradient-text` brand (violet → purple → pink) for headings
- Sidebar is sticky full-height, 340px wide, with logo, nav, collapsible model-settings, upload dropzone, live document list (polled), stats cards
- Chat uses framer-motion for message enter animations and a custom "thinking dots" loader
- Citations render as a collapsible list with per-item relevance bars (vs. Streamlit's one-line strings)
- ReAct traces render Thought/Action/Observation with distinct icon + color coding per step

---

## 9. Verification performed

- `npm install` — 251 packages, clean
- `npx tsc --noEmit` — no errors
- `npx next build` — all 8 routes compiled, 5 feature pages + proxy + not-found + root
- Bundle sizes: ~3KB per page, ~330KB First Load JS total (shared across routes)

Not yet verified against a running backend (requires starting FastAPI + uploading a real PDF). Logic is 1:1 with the Streamlit version so behavior should match.

---

## 10. Change log (this file must be appended on every code change)

| Date | Scope | Summary |
|---|---|---|
| 2026-04-17 | Initial migration | Full Streamlit → Next.js 15 rewrite in `frontend/`. Backend untouched. Typecheck + build green. |
| 2026-04-17 | UX polish pass | Fantastic-UI upgrade — empty-state welcome hero with example prompts, auto-resize chat textarea, copy button per message, stage-aware loading indicator, active-model chip, mode banner, backend health dot (polls `/api/health`), help/shortcut dialog (`?` key), tooltips everywhere, sonner toast notifications for upload/delete, richer empty states on every feature page, clickable example prompts on survey/search/trends, info tooltips explaining each control, ingestion progress bars on document cards. No backend changes. Typecheck + build green. |

### Turn 5 — user
> Asked for a more user-friendly, informative, beautiful UI (UI-only; keep logic and backend unchanged; also update this summary).

**Assistant:** Added UX primitives (`Tooltip`, `InfoTip`, `Kbd`, `Dialog`, `Toaster`), a `BackendStatus` dot that polls `/api/health`, a `HelpButton`/`HelpDialog` pair with keyboard-shortcut cheatsheet, and an `ExamplePrompts` component. Overhauled `chat-panel.tsx` with a welcome hero, clickable starter prompts, auto-growing textarea (Enter to send / Shift+Enter for newline), per-message copy, stage-aware loading text, mode+model chips. Upgraded sidebar with status+help slot and richer nav hints. Added sonner toasts for upload/delete flows. Added example prompts and info tooltips to every feature page. Zero changes to `src/**` (Python) or to any API call shape — only visual and interaction improvements.

### New files (UX pass)

- `components/ui/tooltip.tsx`
- `components/ui/info-tip.tsx`
- `components/ui/kbd.tsx`
- `components/ui/dialog.tsx`
- `components/ui/toaster.tsx`
- `components/backend-status.tsx`
- `components/example-prompts.tsx`
- `components/help-dialog.tsx` (exports `HelpButton`)

### Files updated (UX pass)

- `app/layout.tsx` — mounts `<Toaster />`
- `components/chat-panel.tsx` — welcome hero, auto-resize textarea, copy buttons, stage indicator, mode/model chips, `?` shortcut wiring, toasts
- `components/sidebar.tsx` — backend-status + help button in header, richer nav with sub-hints
- `components/upload-panel.tsx` — sonner toasts, size label, clear-selection, animated progress bar
- `components/document-list.tsx` — sonner toasts, count badge, per-card ingestion shimmer, tooltips on refresh/delete/stat cards
- `app/compare/page.tsx` — empty-state card with guidance, counter of uploaded papers, info tooltips
- `app/survey/page.tsx` — starter-topic example cards, info tooltips, multi-query retrieval callout
- `app/search/page.tsx` — example query cards + concept cards, info tooltips
- `app/trends/page.tsx` — trend facets, interest starter cards, info tooltips

### Design language additions

- `.chip`, Kbd pills, gradient-brand logo glow, health-dot shadow glow, animated mode banner (pulsing dot), example-prompt cards with hover-lift + gradient bottom accent, dialog backdrop blur
