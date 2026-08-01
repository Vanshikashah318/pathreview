"""LLM-based re-ranking of retrieved chunks (issue #34).

Second-stage pass over the hybrid-retrieved candidate set: prompts a smaller LLM
to score each chunk's relevance to the query, then reorders by that score. Opt-in
via HybridRetriever(enable_rerank=True); on any API or parse failure it falls back
to the original (blended-score) order so retrieval never breaks.
"""

import json
from dataclasses import dataclass

import openai
import structlog

logger = structlog.get_logger()


@dataclass
class RerankConfig:
    """Configuration for LLM re-ranking."""

    api_key: str
    base_url: str
    model: str
    temperature: float = 0.0
    max_tokens: int = 500


class LLMReranker:
    """Re-score and reorder retrieved chunks by LLM-judged relevance."""

    def __init__(self, config: RerankConfig):
        """Initialize the re-ranker.

        Args:
            config: RerankConfig with API settings
        """
        self.config = config
        self.client = openai.OpenAI(api_key=config.api_key, base_url=config.base_url)

    def rerank(self, query: str, chunks: list[dict], top_k: int) -> list[dict]:
        """Re-rank candidate chunks by LLM relevance to the query.

        Args:
            query: The user's text query
            chunks: Candidate chunk dicts (each with at least 'id' and 'text'),
                already ordered by blended score
            top_k: Number of chunks to return after re-ranking

        Returns:
            The top_k chunks ordered by LLM relevance, each with an added
            'rerank_score'. On empty input or any failure, falls back to the
            original order.
        """
        if not chunks:
            return []

        try:
            scores = self._score_chunks(query, chunks)
        except Exception as e:
            logger.warning("rerank_failed_fallback_to_blended", error=str(e))
            return chunks[:top_k]

        # Attach scores; tiebreak on original position (stable, deterministic).
        for i, chunk in enumerate(chunks):
            chunk["rerank_score"] = scores.get(i, 0.0)

        reranked = sorted(
            enumerate(chunks),
            key=lambda pair: (pair[1]["rerank_score"], -pair[0]),
            reverse=True,
        )
        results = [chunk for _, chunk in reranked][:top_k]

        logger.info("rerank_complete", candidates=len(chunks), returned=len(results))
        return results

    def _score_chunks(self, query: str, chunks: list[dict]) -> dict[int, float]:
        """Ask the LLM to score each chunk 0-1 for relevance to the query.

        Args:
            query: The user's text query
            chunks: Candidate chunk dicts

        Returns:
            Mapping of chunk index -> relevance score (0.0-1.0). Missing or
            unparseable entries are omitted (treated as 0.0 by the caller).
        """
        numbered = "\n".join(f"[{i}] {chunk.get('text', '')}" for i, chunk in enumerate(chunks))
        prompt = (
            f"Query: {query}\n\n"
            f"Candidate chunks:\n{numbered}\n\n"
            "Score how well each chunk answers the query, from 0.0 (irrelevant) "
            "to 1.0 (directly answers it). Respond ONLY with a JSON array of "
            'objects like [{"index": 0, "score": 0.9}], one per chunk.'
        )

        response = self.client.chat.completions.create(
            model=self.config.model,
            messages=[
                {"role": "system", "content": "You are a precise relevance judge."},
                {"role": "user", "content": prompt},
            ],
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )
        content = response.choices[0].message.content
        if content is None:
            return {}

        return self._parse_scores(content)

    @staticmethod
    def _parse_scores(content: str) -> dict[int, float]:
        """Parse the LLM's JSON response into an index->score map.

        Args:
            content: Raw LLM response text

        Returns:
            Mapping of index -> score for every well-formed entry; malformed
            entries are skipped rather than raising.
        """
        scores: dict[int, float] = {}
        parsed = json.loads(content)
        for entry in parsed:
            try:
                idx = int(entry["index"])
                score = float(entry["score"])
            except (KeyError, TypeError, ValueError):
                continue
            scores[idx] = max(0.0, min(1.0, score))
        return scores
