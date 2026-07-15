# Retrieval Strategy Contract

Every retrieval implementation in `backend/retrieval/strategies/` — deterministic
BM25F, dense embeddings, and future hybrid / reranker strategies — implements the
`RetrievalStrategy` interface (`backend/retrieval/strategies/base.py`) and MUST
uphold the guarantees below. A conforming strategy is interchangeable behind the
frozen Retrieval Evaluation Framework and safe to compose in later phases (hybrid
fusion, cross-encoder reranking, the Tutor Brain).

## Interface

```python
class RetrievalStrategy(ABC):
    def search(self, query: str, top_k: int = 5,
               context: RetrievalContext | None = None) -> list[SearchResult]: ...
    def batch_search(self, queries: list[str], top_k: int = 5,
               context: RetrievalContext | None = None) -> list[list[SearchResult]]: ...
    def metadata(self) -> StrategyMetadata: ...
```

- `SearchResult` = `(score: float, document: KnowledgeDocument)` — reused from the
  frozen BM25F module so results plug directly into `RetrievalEvaluationEngine`
  (which reads `result.document.name` / `result.document.aliases`).
- The interface returns `SearchResult`, not a bare `KnowledgeDocument`, so scores
  are available to hybrid fusion and rerankers. `result.document` is the document.

## Guarantees

### 1. Determinism
For a fixed underlying index and a fixed `(query, top_k, context)`, `search` MUST
return the identical ordered list on every call, within a process and across
processes — independent of `PYTHONHASHSEED` and dict/set iteration order.

- Purely lexical/analytic strategies (BM25F) are exactly reproducible.
- Model-backed strategies (dense) are deterministic given fixed model weights in
  inference/eval mode. Floating-point summation may make two *scores* differ in the
  last ULPs across hardware; the ordering guarantee is preserved because ties are
  broken by a stable key (see Ordering). Strategies MUST run models in eval mode
  with no sampling/dropout.

### 2. Ordering
Results are sorted by `score` descending, then by a stable secondary key
(`document.concept_id` ascending). No result ordering may depend on the insertion
order of the corpus or on hash randomization. Each strategy documents its exact
sort key in code.

### 3. Immutability
A strategy MUST NOT mutate:
- the Knowledge Index or any `KnowledgeDocument` it reads,
- any embedding artifact on disk.

Embedding artifacts are write-once: each build produces a new, content-addressed
versioned directory (`embeddings/<provider>/<model>/<version>/`) with an immutable
`manifest.json` + `vectors.jsonl`. Existing versions are never edited in place.

### 4. Context semantics
`context` is optional; `None` (or an all-`None` context) is a no-op, which keeps the
signature backward compatible with callers that pass only `query`/`top_k`.

When a context is supplied, its filters (`subject`, `chapter`, `concept_ids`, and
future fields) are applied to the **candidate pool before `top_k` truncation**, so a
filtered search still returns up to `top_k` matching results rather than fewer.
Filtering is order-preserving and deterministic.

### 5. `top_k`
`search` returns at most `top_k` results and never more. `top_k <= 0` returns an
empty list. Fewer than `top_k` results is valid (small corpus / strict context).

### 6. Empty / trivial queries
A query that normalizes to no content tokens (empty, punctuation-only, or
stop-words-only) returns `[]`.

### 7. `batch_search`
`batch_search(queries, ...)` returns one result list per query, positionally
aligned. Each element MUST equal what `search(query, ...)` would return for that
query. Batching (e.g. embedding all queries in one model call) is an implementation
optimization and MUST NOT change results.

### 8. `metadata`
`metadata()` returns a `StrategyMetadata` describing `name`, `kind`
(`lexical` | `dense` | `hybrid` | `reranker`), `deterministic`, and — for
model-backed strategies — `provider`, `model_id`, and `dimension`. Reports and
provenance rely on this.

## Compliance testing
`tests/test_strategy_contract.py` exercises these guarantees against every concrete
strategy (currently BM25F and Dense), including determinism across hash seeds,
ordering/tie-breaks, `top_k` bounds, empty-query behavior, `batch_search` parity,
context filtering, and interchangeability through `RetrievalEvaluationEngine`.
