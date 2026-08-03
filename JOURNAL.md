# Module 3 Journal

## Week 7 — Issue selection

**Issue link:** https://github.com/ascherj/pathreview/issues/34

**Issue title:** Implement a re-ranking step that uses an LLM to score retrieved chunks before generation

**Tier:** [ ] Tier 1  [ ] Tier 2  [x] Tier 3

**Problem summary:**
The RAG retriever currently ranks chunks with a purely mechanical score — a
weighted blend of vector cosine similarity and BM25 keyword scores in
`HybridRetriever.retrieve()`. That blended score measures surface-level
similarity, not whether a chunk actually answers the query, so genuinely
relevant chunks can be pushed below the top-k cutoff and passed over before
generation. This issue asks for an optional second-stage re-ranking pass: after
hybrid retrieval produces its candidate set, prompt a smaller LLM to score each
candidate's relevance to the query and reorder them, so the top-k handed to the
generator reflects semantic relevance rather than just lexical/embedding
overlap. A successful fix adds a new `rag/retriever/reranker.py`, wires it into
`hybrid.py` behind a toggle (so the existing behavior stays the default), and is
covered by at least one new unit test — improving answer quality without
breaking the current retrieval path.

**Branch name:** feat/34-llm-chunk-reranking

**Setup confirmation:** [x] App runs locally at localhost:5173

**Cohort ledger:** [x] Issue added to cohort ledger

---

### "Is this right for me?" checklist reasoning

- **Understand it:** I can explain it in my own words (add an optional LLM
  re-scoring pass over the hybrid-retrieved chunks before the top-k reach the
  generator), located the referenced files (`rag/retriever/hybrid.py` + new
  `reranker.py`), and can describe the before/after behavior. 
- **Tier fit:** Labeled **tier-3** (RAG/AI-pipeline change); 7–10h estimate fits
  the Weeks 8–9 window and I'm accepting that scope knowingly. 
- **Codebase readiness:** Read `HybridRetriever.retrieve()` and the retriever
  subpackage end to end, so I know the chunk dict shape and the insertion point
  for the re-rank hook; reviewed `tests/unit/test_keyword_search.py` for test
  patterns and will add a new unit test with the LLM mocked. 
- **Scope & time:** No blockers or dependencies, the files already exist, and the
  estimate is realistic for my two weeks; still need to confirm the Claims count
  on the ledger. 

**Verdict:** Understanding and codebase boxes checked. Remaining actions: confirm
localhost:5173 runs and add the issue to the cohort ledger.

---

## Week 8 — Reproduction & solution planning

**Reproduction commit link:** https://github.com/Vanshikashah318/pathreview/commit/b369655f8709cf4f5ff2bcb9396f569e035ee23d

**Reproduction summary:**
Traced the ranking path in `HybridRetriever.retrieve()` (`rag/retriever/hybrid.py`,
lines 92–97): the candidate chunks are filtered by `min_score`, sorted by the
blended vector+BM25 score, and sliced to `max_chunks` — with no LLM relevance
re-ranking anywhere between the sort and the top-k cut. Documented the gap with a
marker comment at the insertion point and a characterization test
(`tests/unit/test_reranker.py`) pinning the current mechanical-only ordering,
confirming exactly where the missing re-rank hook belongs.

**PLAN.md link:** https://github.com/Vanshikashah318/pathreview/blob/feat/34-llm-chunk-reranking/PLAN.md

**Walkthrough video (recommended):** [optional Loom link, ≤2 min]

**Blockers or open questions:**
Need to trace how `HybridRetriever` is constructed at its call site (likely
`agent/orchestrator.py` or a retrieval factory) to finalize the `__init__`
signature for the `reranker` / `enable_rerank` toggle. Separately, `make run`'s
frontend fails with a Node `crypto.getRandomValues` error (Node-version issue,
unrelated to this backend/RAG issue) — backend + unit tests run fine.

---

## Week 9 — Solution building & PR submission

### Check-in 1 (mid-week)

**Current progress:**
Implemented all PLAN.md sub-tasks: added `rag/retriever/reranker.py`
(`LLMReranker` + `RerankConfig`), wired an off-by-default `enable_rerank` toggle
into `HybridRetriever`, and added `tests/unit/test_reranker.py` (9 unit tests, LLM
mocked — all passing). Ran the full unit suite with and without my changes: 53
pre-existing failures either way, +9 new passing tests, so my change introduces no
new failures.

**Next steps:**
Open the draft PR, incorporate peer/mentor review feedback, then mark ready.

**Blockers:**
Repo has pre-existing `ruff`/`mypy`/test failures unrelated to this issue; confirmed
my changes don't add to them.

---

### Check-in 2 (end of week)

**PR link:** https://github.com/ascherj/pathreview/pull/182

**Branch:** `feat/34-llm-chunk-reranking`

**What you built:**
An optional second-stage LLM re-ranking pass for the hybrid retriever. After
vector+BM25 blending, an opt-in reranker prompts a smaller LLM to score each
candidate chunk's relevance and reorders before the top-k cut, so semantically
strong chunks aren't dropped by purely mechanical scoring. Off by default, with a
safe fallback to blended order on any LLM/parse failure.

**Tests added or updated:**
`tests/unit/test_reranker.py` — 9 tests covering relevance reordering, empty input,
error and partial-response fallback, JSON/code-fence parsing, no input mutation, and
both states of the `enable_rerank` toggle.

**Self-review confirmation:** [ ] make check passes  [ ] make test-unit passes
(All checks pass on the files I authored; the repo's pre-existing `ruff`/`mypy`/test
failures in unrelated modules are documented in the PR and unaffected by this change.)

**Draft PR feedback received from:** [name or Slack handle, or "none"]
