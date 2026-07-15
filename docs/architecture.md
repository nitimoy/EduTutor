# Retrieval Architecture

The retrieval stack is **strategy-based**: the deterministic compiler produces a
Knowledge Index, and one or more retrieval strategies sit behind a single
interface over it. Dense embeddings are an *additional* representation — the
compiler and its outputs remain the canonical source of truth.

```
Educational IR ─▶ Knowledge Index (knowledge_index.json)   ← canonical, frozen
                        │
        ┌───────────────┴───────────────────────────┐
        ▼                                            ▼
  RetrievalStrategy (ABC)                     EmbeddingBuilder (doc → text)
  search / batch_search / metadata                   │
        │                                            ▼
  ┌─────┼─────────┬───────────────┐            EmbeddingProvider (ABC)
  ▼     ▼         ▼               ▼             Hashing (default) │ BGE-M3 (lazy)
BM25F  Dense    Hybrid        Reranker                 │
(wraps  Retrieval (future)     (future)                ▼
 API)   Strategy                              EmbeddingIndex  ◀── canonical, versioned,
        │  ▲                                  provenance-stamped artifacts
        │  │ hydrate                                   │
        │  └──────────── VectorStore (CACHE) ◀─────────┘
        │                Local (default) │ Qdrant (lazy)
        ▼
  evaluation/retrieval_benchmark  ─▶  RetrievalEvaluationEngine (frozen)
                                       └─ BM25F vs Dense comparison report
```

## Layers

- **RetrievalStrategy** (`backend/retrieval/strategies/base.py`) — the common
  interface. `search(query, top_k, context) -> list[SearchResult]`,
  `batch_search(...)`, and `metadata() -> StrategyMetadata`. `RetrievalContext`
  carries optional, non-breaking query filters (subject/chapter/concept ids). See
  the formal guarantees in [`retrieval_strategy_contract.md`](retrieval_strategy_contract.md).
  - `BM25FRetrievalStrategy` — thin wrapper over the frozen deterministic retriever
    in `retrieval/api/search.py` (unmodified).
  - `DenseRetrievalStrategy` — embeds the query, searches the vector store, maps
    hits back to `KnowledgeDocument`s.
  - `HybridRetrievalStrategy` — orchestrates BM25F + Dense and fuses their rankings
    with Reciprocal Rank Fusion (`strategies/fusion.py`, `score = Σ wᵢ/(k+rank)`,
    optional per-retriever weights, k configurable, deterministic). Over-fetches
    `candidate_k` from each component so a doc outside one retriever's top_k can
    still be fused. Neither component knows Hybrid exists.
    **Findings (Phase 3.4 / 3.4.1):** equal-weight RRF regressed macro MRR vs Dense
    (0.766 vs 0.835). A full 54-cell k×weight sweep raised the best hybrid to 0.825
    (k=20, Dense:BM25F=2:1) and repaired the Chemistry regression, but it never
    overtook Dense and could not fix a Mathematics regression at any setting.
    **Dense (BGE-M3, A0, macro MRR 0.835) remains the production retriever;** the
    weighted-RRF hybrid is implemented and available but not promoted. See
    `docs/phase_3_4_hybrid_retrieval_report.md` and
    `docs/phase_3_41_hybrid_optimization_report.md`.
  - `AdaptiveRouterStrategy` (`routing/`) — deterministic per-query routing over
    BM25F/Dense/Hybrid using observable query features (definition/explanation/
    comparison form, math notation, quoted phrases, exact-concept overlap with the
    index vocabulary). No ML/LLM/hardcoded concepts. **Finding (Phase 3.5):** all
    four benchmarked policies tie Dense exactly (0.835) — the lexical wins BM25F
    could contribute occur only on queries where Dense already scores 1.0, and the
    feature that predicts BM25F's real advantage is the *subject*, not any query
    characteristic. **Dense remains production;** the router is available but not
    promoted. See `docs/phase_3_5_adaptive_routing_report.md`.

**Retrieval optimization arc (all deterministic methods converge on Dense):**
Phase 3.3 froze the embedding representation (Dense macro MRR **0.835**); Phase
3.4/3.4.1 showed fusion cannot beat it (best 0.825); Phase 3.5 showed routing cannot
beat it (0.835 exactly). Per-query oracle is 0.873 — the residual gap is one Physics
query whose winning retriever isn't predictable from query text. **Production
retriever: Dense (BGE-M3, A0 representation).**

- **EmbeddingProvider** (`backend/retrieval/embedding/provider.py`) — swappable
  model boundary. `HashingEmbeddingProvider` is the dependency-free default used by
  tests/CI (**infrastructure validation only**, not a quality baseline).
  `BGEM3EmbeddingProvider` (`embedding/bge_m3.py`) is the production backend,
  imported lazily.

- **EmbeddingBuilder** (`embedding/builder.py`) — composes the deterministic
  embedding text. The representation is frozen (Phase 3.35 ablation): **concept
  name → aliases → definitions**, one line each, label-free. Examples, related
  concepts, prerequisites, formulas, and metadata prefixes are deliberately
  excluded — the ablation showed each of them reduced or failed to consistently
  improve retrieval quality (see
  `docs/phase_3_35_embedding_representation_report.md`). Only the Knowledge Index
  is used; never PDF text, parser output, or LLM metadata.

- **EmbeddingIndex** (`embedding/index.py`) — the **canonical** on-disk store of
  vectors: immutable, content-addressed versioned artifacts under
  `embeddings/<provider>/<model>/<version>/` with a provenance `manifest.json`
  (compiler version, Knowledge-Index checksum, provider, model, dimension, content
  checksum, document count, timestamp). Rebuilds incrementally — only changed
  documents are re-embedded.

- **VectorStore** (`vectorstore/base.py`) — a disposable **cache** hydrated from the
  EmbeddingIndex. `LocalVectorStore` (pure-Python cosine) is the default;
  `QdrantVectorStore` (lazy) is the optional production backend. Qdrant is never the
  source of truth — it is always rebuildable from the EmbeddingIndex, which is
  rebuildable from the Knowledge Index.

- **Benchmark** (`backend/evaluation/retrieval_benchmark.py`) — owned by the
  evaluation layer; runs both strategies through the frozen
  `RetrievalEvaluationEngine` on identical datasets.

## Walkthrough

Compile a book (produces `knowledge_index.json`), then:

```bash
# Deterministic BM25F search (no embeddings needed)
PYTHONPATH=. python -m backend.retrieval.cli search \
  --compiled data/compiled/physics/physics_part_1 --query "What is an electric dipole?"

# Build the embedding artifact (incremental; re-run embeds nothing new)
PYTHONPATH=. python -m backend.retrieval.cli build-embeddings \
  --compiled data/compiled/physics/physics_part_1 --provider hashing --dimension 256

# Dense search over the same index
PYTHONPATH=. python -m backend.retrieval.cli search-dense \
  --compiled data/compiled/physics/physics_part_1 --query "What is an electric dipole?"

# Side-by-side BM25F vs Dense comparison (evaluation-owned)
PYTHONPATH=. python -m backend.evaluation.retrieval_benchmark \
  --compiled data/compiled/physics/physics_part_1 \
  --dataset data/evaluation/retrieval_queries/phys_ch1.yaml
```

For the production dense stack, install the optional extras and switch providers:

```bash
pip install FlagEmbedding torch          # BGE-M3
PYTHONPATH=. python -m backend.retrieval.cli build-embeddings \
  --compiled <dir> --provider bge-m3
```

## Tutor Brain (post-retrieval)

`backend/tutor/` sits **entirely after** retrieval and turns retrieved
`KnowledgeDocument`s into a **structured teaching plan** — deterministic, **no LLM, no
natural-language generation** (Phase 4.0). It is retrieval-agnostic (takes
`list[SearchResult]` from any strategy) and runs fully offline.

```
list[SearchResult] ─▶ QueryPlanner ▸ ContextOrganizer ▸ TeachingStrategy ─▶ TeachingPlan
                                                                (Phase-5 editable) │
                                          CitationBuilder ▸ AnswerComposer ◀────────┘
                                                                ▼
                                                          TutorPlan (final IR)
```

- **Two IRs, one seam:** `build_teaching_plan()` → `TeachingPlan` (intermediate, what to
  teach, mutable by a future Student Model); `compose_from()` → `TutorPlan` (final, fixed
  compiler-backed section slots + resolved citations). Neither step re-runs retrieval.
- **Compiler-backed sections only** — definitions, formulas, examples, prerequisites/
  related/next, comparison, summary, plus **proof/exercise/theorem/property recovered**
  from the frozen compiler artifacts (`concept_index.json` + `educational_ir.json`) via a
  storage-agnostic `KnowledgeRepository`. No synthesized content; a section with no
  backing object is flagged `unsupported_by_index`, never generated. Misconceptions and
  derivations have no source anywhere and are always flagged.
- **Deterministic intent** reuses the frozen `routing/analyzer.py`; a **data-aware
  strategy fallback** degrades honestly when a lead section has no content; a
  **no-invention invariant** asserts every cited concept id is a real retrieved document.
- **Evaluation** (`backend/evaluation/tutor_eval.py`): intent/strategy/primary accuracy,
  citation validity, no-hallucination rate, determinism. Datasets under
  `data/evaluation/tutor_cases/`. Benchmark: `scripts/tutor_benchmark.py`. See
  `docs/phase_4_0_tutor_brain_report.md` and example plans in `docs/examples/tutor_plans/`.

```bash
# Evaluate the planning pipeline (offline BM25F; run twice → byte-identical)
PYTHONHASHSEED=0 PYTHONPATH=. python -m backend.evaluation.tutor_eval \
  --compiled data/compiled/physics/physics_part_1 \
  --dataset data/evaluation/tutor_cases/phys_ch1.yaml
```

## Student Model (personalization)

`backend/student/` sits in the Tutor Brain seam, **between** `TeachingPlan` and
`TutorPlan`. It answers *"how should **this student** be taught?"* by reordering,
suppressing, and annotating existing sections — deterministic, rule-based, **no LLM, no
scheduling, no ML**. It never invents content or edits retrieved knowledge.

```
TeachingPlan ─▶ StudentModel ─▶ TeachingPlanDelta ─▶ TeachingPlanApplier ─▶ TeachingPlan' ─▶ compose_from ─▶ TutorPlan
                    ▲               (immutable patch)       (applies it)
        StudentProfile { StudentState + StudentPreferences } + LearningState
```

- **`StudentProfile`** = `StudentState` (mastery, confidence, `concept_states`,
  misconception flags, completion, prerequisite gaps, revision counts, streak) +
  `StudentPreferences` (difficulty / explanation / example / pace). **`LearningState`**
  (`student/learning_state.py`) is a deterministic `transition(state, signal)` table plus
  `derive_state(...)`.
- **`TeachingPlanDelta`** is an **immutable** patch (source plan + ordered
  `PersonalizationDecision`s + directives); the dedicated **`TeachingPlanApplier`** is the
  only component that executes it (`apply` → a new plan; source never mutated).
- **Rule engine** (`student/rules.py`): `PersonalizationRule(name, priority, axis,
  predicate, build)`, evaluated **priority ascending then declaration order**, **one
  decision per axis** (conflicts skipped + noted). Every op targets only sections present
  in the plan (no-invention).
- **Evaluation** (`backend/evaluation/student_eval.py`): determinism, decision
  correctness, priority ordering, state transitions, structural invariants — architectural
  correctness only. Benchmark: `scripts/student_benchmark.py`. See
  `docs/phase_5_0_student_model_report.md` and `docs/examples/student_plans/`.

```bash
PYTHONHASHSEED=0 PYTHONPATH=. python -m backend.evaluation.student_eval
```

## Learning Session Engine (progression)

`backend/session/` closes the loop **after** a tutoring interaction: it folds an ordered
log of learning events into an updated `StudentState` and a structured `SessionSummary`.
Deterministic, event-sourced, replayable — **no LLM, no scheduling, no ML**.

```
StudentState(before) + LearningSession ─▶ LearningSessionEngine ─▶ StudentStateDelta ─▶ StudentStateApplier ─▶ StudentState(after)
   (immutable event log)                         │  (pure fold)      (canonical)          (mirrors TeachingPlanApplier)
                                                 └▶ SessionSummary (strictly derived report)
```

- **`LearningEvent` / `LearningSession`** (`session/events.py`) — the immutable, ordered,
  timestamp-free event log (`EventType`: lesson/exercise/proof/review/mastered).
- **`StudentStateDelta`** (`session/state_delta.py`) — the **canonical**, immutable update;
  `StudentStateApplier.apply(before, delta)` produces a new `StudentState` (clamps [0,1],
  replays signals through the frozen `transition()`, completes on the mastery floor). The
  event log + delta are the source of truth; the `SessionSummary` is always regenerable.
- **`LearningSessionEngine`** (`session/engine.py`) — `build_delta` (pure fold) + `process`
  → `SessionResult(delta, after, summary)`. Per-event effects are a fixed table
  (`session/event_rules.py`).
- **`SessionSummary`** (`session/summary.py`) — structured counts + per-concept before/after
  deltas, no NL. It deliberately has **no "suggested next concepts"** (that belongs to the
  Tutor Brain / Student Model on the next query).
- **Evaluation** (`backend/evaluation/session_eval.py`): determinism, identical replay,
  canonical-delta, transitions, ordering, invariants. Benchmark:
  `scripts/session_benchmark.py`. See `docs/phase_5_1_session_engine_report.md` and
  `docs/examples/session/`.

```bash
PYTHONHASHSEED=0 PYTHONPATH=. python -m backend.evaluation.session_eval
```

## Language Generation Layer (renderer)

`backend/generation/` is the **presentation layer**: it turns a frozen `TutorPlan` into a
natural-language teaching response via an LLM, **making no educational decisions** (no
retrieve, reorder, add, or invent; citations preserved). Prompt construction is
deterministic; the LLM is the only non-determinism, isolated behind an interface.

```
TutorPlan ─▶ build_generation_plan ─▶ LanguageGenerationPlan (RenderUnits, stable unit_id)
                     │  per section, in TutorPlan slot order
                     ▼
        PromptBuilder ─▶ PromptDocument (provider-NEUTRAL) ─▶ ProviderAdapter ─▶ LanguageModel
                     ▼
        Renderer ─▶ RenderedResponse (sections in plan order + citations preserved)
```

- **Per-section segmented rendering** — each populated section gets its own scoped prompt
  (its items + citations only); results concatenate in `TutorPlan` slot order.
- **Three-layer provider neutrality** — `PromptBuilder` emits a provider-neutral
  `PromptDocument`; `ProviderAdapter` (Echo/OpenAI/Claude/Gemini) owns all chat-message
  construction; `LanguageModel` pairs an adapter with a backend. `EchoLanguageModel` is the
  deterministic offline default (validation only); real backends import their SDK lazily.
- **Stable `unit_id`** threads `RenderUnit → PromptDocument → GenerationResult` for future
  streaming/retries/caching/telemetry.
- **Guarantees** (all tested, offline): prompt + response determinism, section-order
  preservation, no added concepts, citation preservation, Echo grounding, provider-neutral
  adapter equivalence, and template purity (no facts in style/system templates).
- **Evaluation** (`backend/evaluation/generation_eval.py`) + benchmark
  (`scripts/generation_benchmark.py`) + golden prompt snapshots
  (`tests/snapshots/generation/`). See `docs/phase_6_0_language_generation_report.md` and
  `docs/examples/generation/`.

```bash
PYTHONHASHSEED=0 PYTHONPATH=. python -m backend.evaluation.generation_eval
```

## Response Verification Layer (grounding)

`backend/verification/` analyzes whether a `RenderedResponse` faithfully represents its
`TutorPlan` / `LanguageGenerationPlan`. It **never modifies text** — no LLM, no retrieval,
no rewriting; it only emits a deterministic, explainable `VerificationReport`.

```
TutorPlan + LanguageGenerationPlan + RenderedResponse
        ▼
ResponseVerificationEngine ─▶ 6 verifiers ─▶ VerificationReport (metrics + issues[] + passed)
```

- **Six deterministic verifiers**: section coverage, citation preservation, **content-word
  grounding** (rendered content words ⊆ that section's own PromptDocument; connectives may
  be rephrased, new content words are flagged), completeness (every prompt content line
  represented), renderer contract (no new/reordered/missing/duplicated/empty sections), and
  provider invariants (`unit_id` / identity / citations / ordering unchanged; only wording
  may differ).
- **Source of truth is the TutorPlan** — the verifier never consults the compiler. Citations
  compare as ordered tuples (the frozen `Citation` is non-hashable). Reports are byte-stable
  across runs and `PYTHONHASHSEED`; inputs are never mutated.
- **Evaluation** (`backend/evaluation/verification_eval.py`): a faithful response + nine
  adversarially tampered variants, each checked for the right verdict and issue code.
  Benchmark: `scripts/verification_benchmark.py`. See
  `docs/phase_6_1_verification_report.md` and `docs/examples/verification/`.

```bash
PYTHONHASHSEED=0 PYTHONPATH=. python -m backend.evaluation.verification_eval
```

## Educational Tutor Orchestrator (end-to-end)

`backend/orchestrator/` is the capstone: a deterministic layer that wires every frozen
component into one pipeline behind a single public API — **coordination only**, no new
educational logic, no retries, no input mutation.

```
EducationalTutorEngine.answer(query, student_profile, retrieval_context) -> TutorResponse
  retrieval        RetrievalStrategy.search
  planning         TutorBrain.build_teaching_plan          ┐ personalization sits BETWEEN
  personalization  StudentModel.personalize -> Applier.apply │ planning and composition
  composition      TutorBrain.compose_from                 ┘ (the Phase-4/5 seam)
  generation       build_generation_plan -> Renderer.render
  verification     ResponseVerificationEngine.verify
```

- **`TutorResponse`** bundles the rendered answer, `TutorPlan`, `VerificationReport`,
  citations (== plan references), retrieval + execution metadata, an `ExecutionTrace`
  (per-stage name/status/timing), and timing. `deterministic_fingerprint()` excludes
  wall-clock timing, so identical inputs → identical fingerprint.
- **Failure policy** — a stage exception is wrapped in `StageExecutionError` and halts the
  pipeline (no retries); a failing verification *verdict* is returned in the response by
  default (or raises `VerificationFailedError` under `strict_verification`).
- **Construction** — dependency injection with config-based fallback; tests inject a fake
  strategy + Echo + no repository, so the suite runs offline with no compiled data.
- **Evaluation** (`backend/evaluation/orchestrator_eval.py`): determinism, stage ordering,
  metadata propagation, verify-fail handling, citation preservation, config propagation,
  no-mutation. Benchmark: `scripts/orchestrator_benchmark.py`. See
  `docs/phase_7_0_orchestrator_report.md` and `docs/examples/orchestrator/`.

With this layer the **core educational engine is complete** (compile → retrieve → plan →
personalize → generate → verify, end-to-end); remaining work is product integration
(service/API/frontend/persistence/deploy), not core architecture.

```bash
PYTHONHASHSEED=0 PYTHONPATH=. python -m backend.evaluation.orchestrator_eval
```

## Constraints upheld
- The compiler, Educational IR, Concept/Relationship/Reasoning layers, the
  Knowledge Index schema, and the evaluation framework are unchanged.
- Embeddings derive only from the Knowledge Index; no PDF chunks, no LLM metadata.
- The vector store is a cache; the EmbeddingIndex (and ultimately the Knowledge
  Index) is canonical.
- Everything runs deterministically and offline by default; heavy backends are
  optional and lazy.
```

---

## Service Layer (Phase 8.0)

The service layer exposes the frozen educational engine through a FastAPI REST API.
It adds no educational logic — only configuration, dependency injection,
request/response mapping, and exception handling.

### Architecture

```
                            FastAPI (backend/api/app.py)
                                     │
                    ┌────────────────┼─────────────────┐
                    ▼                ▼                  ▼
               GET /             POST /api/v1/      POST /chat
               /api/v1/health   tutor/ask           (legacy compat)
               /api/v1/ready    /api/v1/session/
               /api/v1/version    process
               /api/v1/config
                    │                │                  │
                    └────────────────┼──────────────────┘
                                     ▼
                    Depends(get_factory) → EngineFactory
                                     │
                    ┌────────────────┼─────────────────┐
                    ▼                                   ▼
          EducationalTutorEngine             LearningSessionEngine
            (frozen Phase 7.0)                 (frozen Phase 5.1)
```

### Configuration

`ServiceConfig` (Pydantic `BaseSettings`) reads from environment variables and
`.env`, then maps to the frozen `OrchestratorConfig` / `GenerationConfig` /
`VerificationConfig` via `to_orchestrator_config()`. Key env vars:

| Variable | Default | Description |
|---|---|---|
| `COMPILED_DIR` | `None` | Path to compiled textbook data |
| `PROVIDER` | `echo` | LLM provider (echo/openai/claude/gemini) |
| `MODEL_ID` | `echo-v1` | Model identifier |
| `TOP_K` | `5` | Retrieval results count |
| `STRICT_VERIFICATION` | `False` | Fail on verification failure |

### Dependency Injection

Route handlers never instantiate educational objects. The `EngineFactory` is built
once during lifespan and stored in `app.state`. FastAPI `Depends` functions
retrieve it. Tests override the factory with offline `FakeStrategy` + `EchoLanguageModel`.

### Error Mapping

| Orchestrator Error | HTTP Status | Code |
|---|---|---|
| `ConfigurationError` | 500 | `CONFIGURATION_ERROR` |
| `StageExecutionError` | 500 | `STAGE_EXECUTION_ERROR` |
| `VerificationFailedError` | 422 | `VERIFICATION_FAILED` |
| Pydantic `ValidationError` | 422 | (FastAPI default) |

### Evaluation

```bash
PYTHONPATH=. python -m backend.evaluation.api_eval
```

### Constraints upheld
- The entire educational engine (Phases 1–7) is frozen and untouched.
- The API layer only calls existing public APIs.
- No educational logic is duplicated or added.
- The server defaults to offline Echo mode (no API keys needed).
- All 423 existing tests continue to pass.

