<div align="center">

# 📖 BookwriterPro

### Write an entire book with AI — and *watch it happen.*

**Type a premise. Watch the cover design itself as you type. Generate a whole novel chapter‑by‑chapter, live. Read it like a real book. Track every token.**

A local‑first book‑generation studio with a beautiful editorial UI, an HTTP API, and a Model‑Context‑Protocol server — so a human *or an AI agent* can use it as a tool.

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![Tests](https://img.shields.io/badge/tests-49%20passing-2ea44f)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
![MCP](https://img.shields.io/badge/MCP-13%20tools-7c3aed)
![KDP](https://img.shields.io/badge/Amazon%20KDP-fast%20publish-FF9900?logo=amazon&logoColor=white)
![Build](https://img.shields.io/badge/build-none%20%C2%B7%20vanilla%20JS-orange)
![Design panel](https://img.shields.io/badge/design%20panel-9%2F10-e8624e)

[Quick start](#-quick-start-60-seconds) · [Features](#-why-youll-love-it) · [Use it as an agent tool](#-use-it-as-an-agent-tool-mcp) · [Architecture](#-how-it-works) · [The cost story](#-engineered-for-minimum-token-cost)

</div>

---

<div align="center">

![The Library](docs/screenshots/library-light.png)

*A bookshelf you actually want to browse — every cover is generated, not stock.*

</div>

<div align="center">

### 🪄 Your book cover designs itself as you type

![Live cover forge](docs/screenshots/cover-forge.gif)

*No stock art, no upload — a real procedural jacket forged live in the browser.*

</div>

## ✨ Why you'll love it

Most "AI writer" apps give you a chat box and a wall of text. BookwriterPro gives you a **studio**:

- 🪄 **Your book cover designs itself as you type.** Start a new book and a real, art‑directed jacket *forges live* beside the form — title typeset, genre‑driven palette, foil, spine, embossed motif. It's the kind of "wait, how?" moment that makes you lean in.
- ✍️ **Watch your book get written, live.** Chapters stream in **token‑by‑token** with a "Writing…" pulse — like watching an author at the keyboard, with a running word + cost meter.
- 📖 **Read it like a real book.** The finished manuscript opens into a **3D page‑turn reader** — two‑page spread, drop‑caps, page numbers, the works (with a plain‑scroll fallback).
- 🕸️ **See the story's web.** A live character‑relationship graph: clean at rest, revealing each character's ties on hover.
- ⌨️ **⌘K everything.** A Linear/Raycast‑class command palette to jump anywhere.
- 🌗 **Gorgeous in light *and* dark.** A true warm‑paper / espresso re‑theme, not a lazy invert. Fully responsive down to mobile.
- 🤖 **An agent can drive the whole thing** — write *and* publish — via 13 MCP tools or a clean HTTP/OpenAPI API.

> A panel of independent design critics scored the rendered UI a **9/10 — "a polished, premium, shipped product."**

<div align="center">

| Watch chapters stream live | Light *and* dark, both first‑class |
|---|---|
| ![Live streaming studio](docs/screenshots/studio-streaming.png) | ![Dark mode library](docs/screenshots/library-dark.png) |
| **Read it like a real book** | **Trace the story's web** |
| ![3D page-turn reader](docs/screenshots/manuscript-reader.png) | ![Character graph](docs/screenshots/graph-focus.png) |

</div>

---

## 🚀 Quick start (60 seconds)

> Requires **Python 3.10+**. No build step, no Node, no database.

```bash
git clone https://github.com/RealDealCPA-VR/BookwritterPro.git
cd BookwritterPro

# install the web server extras
pip install -e ".[server]"

# launch the studio
python -m bookwriter.serve          # or:  bookwriter-serve
```

Open **http://127.0.0.1:8000** → hit **New book** → start typing and **watch the cover forge itself**.

**No API key? No problem.** With no `ANTHROPIC_API_KEY` set, the app runs in **Demo mode** (a built‑in mock model — zero spend, zero network) so the *entire* experience works out of the box. When you're ready for real prose:

```bash
export ANTHROPIC_API_KEY=sk-ant-...   # Windows: setx ANTHROPIC_API_KEY "sk-ant-..."
python -m bookwriter.serve
```

…then toggle **Demo mode off** in the composer.

---

## 🤖 Use it as an agent tool (MCP)

BookwriterPro speaks the **Model Context Protocol**, so Claude Desktop, Claude Code, or any MCP client can write books for you:

```bash
pip install -e ".[mcp]"
python -m bookwriter.mcp_server     # stdio MCP server
```

**13 tools**, all sharing the same data store as the web app (a book an agent creates shows up in the UI, and vice‑versa):

`list_profiles` · `list_books` · `create_book` · `write_book` · `write_chapter` · `get_status` · `get_chapter` · `get_graph` · `get_cost` · `get_manuscript` · `prepare_kdp` · `export_epub` · `get_kdp_listing`

Claude Desktop config and details: **[`docs/MCP.md`](docs/MCP.md)**.

Prefer plain HTTP? The same engine is a **FastAPI/OpenAPI** service with live **Server‑Sent Events** streaming — interactive docs at **`/docs`** when the server is running.

---

## 🖥️ Or drive it from the CLI

```bash
# Plan + write a whole book end-to-end
python -m bookwriter generate \
  --premise "A lighthouse keeper discovers the nightly fog is erasing the town's memories." \
  --chapters 12 --genre "literary mystery" --project ./lighthouse

# Try the full pipeline offline first — no key, no spend:
python -m bookwriter generate --premise "test" --chapters 3 --project ./demo --mock

python -m bookwriter profiles        # see model tiers + pricing
python -m bookwriter report --project ./lighthouse   # cost + progress
```

Generation is **resumable** — it saves after every chapter, so an interrupted run picks up where it left off.

---

## 📤 Publish to Amazon KDP — fast

<div align="center">

![Publish to KDP](docs/screenshots/publish.png)

</div>

Go from finished manuscript to a **ready-to-upload KDP listing in minutes.** Hit **Publish to KDP** in the studio and BookwriterPro builds the whole kit:

- **✨ Auto-fill every KDP page‑1 field with AI** — a ≤4000‑char marketing description, up to **7 keyword‑rules‑compliant keywords**, up to **3 categories**, subtitle, series/edition — all editable, with live counters and inline validation.
- **A valid EPUB** of your book (pure‑stdlib builder — proper `mimetype`, nav/TOC, embedded cover; uploads straight to KDP).
- **A KDP‑ready cover** exported to a high‑res PNG (~2560px) right from the browser.
- **A copy‑paste listing** + a step‑by‑step **CHECKLIST.md** so you just paste, upload, price, and publish.
- One‑click **Open Amazon KDP**, and a built‑in tip for the `StorytellerUK2026` contest keyword.

Prefer the terminal or an agent?

```bash
# CLI: build the full KDP kit (EPUB + listing + checklist) into ./book/kdp/
python -m bookwriter kdp --project ./book --author-first Vera --author-last Solenne

# Or just export the EPUB via the API
curl -OJ "http://127.0.0.1:8000/api/books/<id>/export/epub?download=1"
```

Agents can do it too — the MCP server exposes `prepare_kdp`, `export_epub`, and `get_kdp_listing`.

> KDP has no public publishing API, so the final upload is yours to click — but everything you need is generated and waiting.

---

## 💸 Engineered for minimum token cost

This isn't just pretty — it's **cheap to run**, by design. Naïve book generators re‑send every prior chapter into every new one (cost grows quadratically). BookwriterPro keeps per‑chapter cost roughly **flat**:

- **A committed story graph** (characters, locations, plot threads, timeline) is the single source of truth — the engine never re‑reads old prose.
- **Prompt‑cached "bible" spine** — the stable spine of the book is sent as a `cache_control` prefix, read at **~0.1×** on every chapter.
- **Bounded rolling synopsis** instead of an ever‑growing transcript.
- **Model tiering** — a capable model writes prose; the cheapest model handles mechanical extraction/continuity.
- **Every call is metered** — the studio shows live `$`, `$/1k words`, and exact prompt‑cache savings.

> Inspired by the knowledge‑graph + deterministic‑fingerprinting approach of [Understand‑Anything](https://github.com/Egonex-AI/Understand-Anything), applied to long‑form fiction so characters and plot stay consistent across dozens of chapters.

---

## 🏗️ How it works

```
premise ──▶ Planner ──▶ Story Bible + Continuity Graph  (committed JSON, shared)
                              │
       ┌──────────────────────┴───────────────────────┐
       ▼                                                │
  Chapter Writer  ◀── cached bible prefix (~0.1× reads) ┤
       │            streams tokens live (SSE)           │
       ▼                                                │
  Extractor (cheap model) ──▶ structured state delta ───┘
       │                       merged into the graph
       ▼
  Continuity Checker ──▶ flags
```

Three surfaces over one engine: a **vanilla, no‑build web SPA**, a **FastAPI HTTP/SSE API**, and an **MCP server**. Full write‑up in **[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)**.

---

## 🧪 Tested & solid

```bash
python -m unittest discover -s tests      # 49 tests, runs fully offline (mock model)
```

The whole package imports and its test suite runs with **zero third‑party installs** (the LLM client is mockable). Server/MCP tests skip cleanly if those extras aren't installed.

---

## 📁 Project layout

```
bookwriter/
  config.py      model tiers, pricing, quality profiles
  pipeline.py    orchestration (plan → write → extract → check), live events
  graph.py       the continuity knowledge graph
  llm.py         Anthropic client (prompt caching, streaming, cost tracking)
  mock.py        offline MockLLM (demo mode + tests)
  server/        FastAPI app, service layer, SSE event broker
  serve.py       `python -m bookwriter.serve`
  mcp_server.py  MCP stdio server (10 tools)
  web/           the studio UI (index.html, styles.css, app.js, covers.js, palette.js)
docs/            ARCHITECTURE.md · MCP.md · screenshots/
tests/           37 offline tests
```

---

## ⚙️ Configuration

| What | How |
|---|---|
| Real generation | `ANTHROPIC_API_KEY` (else Demo/mock mode) |
| Where books live | `BOOKWRITER_DATA_DIR` (default `./.bookwriter_data`) |
| Server host/port | `BOOKWRITER_HOST` / `BOOKWRITER_PORT` (default `127.0.0.1:8000`) |
| Quality profile | `premium` · `balanced` (default) · `draft` — `bookwriter profiles` |

---

## 🛠️ Built with

Pure **Python 3** + **FastAPI** + the **Anthropic SDK** on the backend; **zero‑dependency vanilla HTML/CSS/JS** on the frontend (no framework, no build). The book covers are generated procedurally as inline SVG — no image assets.

<div align="center">

**Type a premise. Get a book. Watch every word of it happen.**

⭐ Star it if BookwriterPro made you smile.

</div>
