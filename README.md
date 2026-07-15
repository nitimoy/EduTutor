# EduTutor — AI-Powered NCERT Class 12 Tutor

An AI tutor for CBSE Class 12 Mathematics, Physics, and Chemistry that answers questions using only NCERT textbook content. Every response is grounded in the textbook with citations — no hallucinated answers.

---

## What We Built

### Two Engine Versions

**v1 — Deterministic Pipeline**
- 9-stage pipeline: Retrieval → Ranking → Evidence Assessment → Planning → Personalization → Generation → Verification
- BM25F lexical search with educational ranking
- Student profiling and personalized teaching
- Every educational decision is rule-based; LLM only renders natural language
- Verifiable, deterministic responses

**v2 — RAG Engine (Recommended)**
- Hybrid retrieval: BM25F + Qdrant semantic search (BGE-M3 embeddings)
- Reciprocal Rank Fusion merges lexical and vector results
- LLM-powered intent resolution for follow-up questions
- Formula preprocessing: converts math notation to natural language for better embedding
- Chapter-based queries ("chapter 13 of math" → probability topics)
- Exercise-guided solving: hints first, full solution only when requested
- Response caching (50%+ LLM cost reduction)
- Rate limiting (30 queries/minute per session)

### Frontend
- Chat interface with LaTeX/Markdown rendering
- Math symbol toolbar (Greek, arrows, matrices, chemistry symbols)
- Live LaTeX preview while typing
- Auth system (register/login)
- Session persistence across page reloads
- Developer mode with pipeline trace visualization
- PDF paste → auto-converts tabular data to LaTeX matrix

### Backend
- FastAPI REST API with OpenAPI docs
- SQLite session storage
- User authentication with password hashing
- Two engine versions behind a version selector
- Health/readiness probes

---

## What We Achieved

### Technical
1. **Hybrid retrieval** — BM25F + semantic search with RRF fusion
2. **LLM-powered intent resolution** — understands context from conversation history
3. **Formula preprocessing** — math notation → natural language for embedding
4. **Chapter-based queries** — "chapter 13 of math" returns probability topics
5. **Exercise-guided solving** — hints first, solution only when requested
6. **Response caching** — 50%+ LLM cost reduction
7. **Rate limiting** — prevents abuse
8. **User authentication** — register/login with proper password hashing
9. **Textbook-grounded responses** — every answer cites the NCERT textbook
10. **No hallucination** — system refuses to answer when content isn't available

### Educational
1. Proper pedagogical planning (profiling → retrieval → personalization → generation)
2. Student profiling tracks completed concepts and learning style
3. Citation system shows textbook sources with page references
4. Works with natural language queries, not just keywords

---

## What We Didn't Achieve

| Feature | Status | Reason |
|---------|--------|--------|
| Image/figure extraction | Partial | PDF figure detection is complex; cropped images are full-page, not individual diagrams |
| Formula preprocessing edge cases | Partial | Handles common patterns but some notation variants fail |
| Perfect worked example extraction | Partial | Reassembles fragments but some are incomplete |
| Cross-subject linking | Not done | e.g., "how does Chemistry Bonding relate to Physics Quantum" |
| Multi-language support | Not done | BGE-M3 supports Hindi but not implemented |
| Mobile app | Not done | Web-only |
| Real-time collaboration | Not done | Single-user sessions |
| Assessment/quiz mode | Not done | No automated testing |
| Comprehensive progress tracking | Basic | Tracks completed concepts but no analytics dashboard |
| All NCERT subjects | Partial | Only Physics, Chemistry, Mathematics (Class 12) |

---

## Tech Stack

### Backend
| Component | Technology |
|-----------|------------|
| Framework | FastAPI + Uvicorn |
| LLM | Cerebras (gpt-oss-120b) via OpenAI SDK |
| Embeddings | BGE-M3 (1024-dim, multilingual) |
| Vector Store | Qdrant (local mode) |
| Search | BM25F + semantic hybrid with RRF fusion |
| Database | SQLite (sessions, users) |
| PDF Processing | PyMuPDF + pdfplumber |
| Math | LaTeX rendering (KaTeX) |

### Frontend
| Component | Technology |
|-----------|------------|
| Framework | Next.js 16 (App Router) |
| UI | React 19, Tailwind CSS 4 |
| Icons | Lucide React |
| Math | KaTeX + remark-math |
| Markdown | react-markdown + remark-gfm |
| Animations | Framer Motion |

---

## Prerequisites

- **Python 3.10+** — [python.org](https://python.org)
- **Node.js 18+** — [nodejs.org](https://nodejs.org)
- **Cerebras API key** — [cloud.cerebras.ai](https://cloud.cerebras.ai) (free tier available)

---

## Quick Start

### Step 1: Clone the repo

```bash
git clone https://github.com/<your-username>/EduTutor.git
cd EduTutor
```

### Step 2: Set up API key

```bash
cp .env.sample .env
```

Edit `.env` and add your Cerebras API key:

```
CEREBRAS_API_KEY=your-key-here
```

Get a free key at https://cloud.cerebras.ai

### Step 3: Install and run

```bash
python run.py --setup    # Install dependencies (first time only)
python run.py            # Start everything
```

On **first run**, the script will automatically:
1. Download 6 NCERT textbook PDFs from ncert.nic.in (~30MB)
2. Compile PDFs into searchable concept graphs
3. Build BGE-M3 embeddings for semantic search

**First run takes 10-15 minutes** (model download + compilation). Subsequent starts are instant.

### Step 4: Open in browser

```
http://localhost:3000
```

Register an account, pick v1 or v2 engine, and start asking questions.

---

## Manual Setup

<details>
<summary>Click for manual setup without run.py</summary>

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cd ..
PYTHONPATH=. uvicorn backend.main:app --port 8000
```

### Frontend

```bash
cd frontend
npm install
PORT=3000 npm run dev
```

### Build data manually

```bash
# Download NCERT zips (place in data/ directory)
# Then:
PYTHONPATH=. python scripts/build_raw_pdfs.py
PYTHONPATH=. python -m backend.compiler.pipeline
pip install -r backend/requirements-embeddings.txt
PYTHONPATH=. python scripts/build_bge_embeddings.py
```

</details>

---

## Available Commands

| Command | Description |
|---------|-------------|
| `python run.py` | Start backend + frontend |
| `python run.py --setup` | Install all dependencies |
| `python run.py --build` | Rebuild data from NCERT PDFs |
| `python run.py --stop` | Stop all running services |

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v2/auth/register` | Register new user |
| POST | `/api/v2/auth/login` | Login |
| GET | `/api/v1/health` | Health check |
| POST | `/api/v1/version/session/start` | Create v2 session |
| POST | `/api/v1/version/query` | Query v2 engine |
| POST | `/api/v1/session/start` | Create v1 session |
| POST | `/api/v1/session/{id}/ask` | Query v1 engine |
| GET | `/api/v1/config` | View engine configuration |
| GET | `/docs` | Swagger UI (auto-generated) |

---

## Project Structure

```
├── backend/                  # FastAPI server
│   ├── api/                  # REST endpoints, auth, config
│   ├── orchestrator/         # 9-stage pipeline (v1)
│   ├── retrieval/            # BM25F search + embeddings
│   ├── tutor/                # Pedagogical planning
│   ├── generation/           # LLM integration
│   ├── verification/         # Response grounding checks
│   ├── session/              # Session state management
│   ├── compiler/             # PDF → concept graph compiler
│   └── v2/                   # RAG engine (v2)
│       ├── rag/              # RAG query engine with streaming
│       └── core/             # Hybrid retriever, cache, auth
│
├── frontend/                 # Next.js 16 app
│   ├── app/                  # Pages (auth, session, settings)
│   ├── components/           # UI (chat, sidebar, markdown)
│   ├── lib/                  # Contexts (auth, session)
│   └── services/             # API client
│
├── data/                     # NCERT data (built by run.py)
│   ├── manifest.json         # Book metadata
│   └── (compiled/, figures/ generated on first run)
│
├── scripts/                  # Build & benchmark scripts
├── tests/                    # Test suite
├── docs/                     # Architecture documentation
├── run.py                    # Cross-platform launcher
├── .env.sample               # Environment template
└── README.md
```

---

## Data Assets

| Asset | Count | Source |
|-------|-------|--------|
| Concepts | 465 | NCERT Class 12 (Math, Physics, Chemistry) |
| Textbooks | 6 | 2 parts per subject |
| Worked examples | 586 | Extracted and reassembled from PDFs |
| BGE-M3 embeddings | 472 vectors | 1024-dim, cosine similarity |
| Formulas linked | 905 | Connected to concepts |

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `CEREBRAS_API_KEY` | Yes | Your Cerebras API key |
| `CEREBRAS_BASE_URL` | No | API base URL (default: `https://api.cerebras.ai/v1`) |
| `MODEL_ID` | No | Model to use (default: `gpt-oss-120b`) |
| `COMPILED_DIR` | No | Path to compiled data (default: `data/compiled`) |
| `MIN_GROUNDING_COVERAGE` | No | Verification threshold (default: `0.3`) |
| `MIN_COMPLETENESS` | No | Verification threshold (default: `0.3`) |

---

## Troubleshooting

**First run is slow**
- BGE-M3 model downloads from HuggingFace on first use (~500MB)
- Subsequent runs use cached model

**Cerebras rate limit (429)**
- Free tier has limits. Wait 30-60 seconds and retry
- v2 engine is more efficient (cached embeddings, fewer API calls)

**Port already in use**
```bash
lsof -ti:3000 | xargs kill -9
lsof -ti:8000 | xargs kill -9
```

**Data not building**
- Ensure you have internet connection (downloads NCERT PDFs)
- Check Python version is 3.10+

---

## License

MIT
