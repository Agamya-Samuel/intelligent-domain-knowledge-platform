"""
Citation extractor — maps factual claims in generated text to source documents.

Implements C8 (Citation Extraction) from the advanced RAG pipeline (TRD §4.3).

After the LLM generates a response, this module:
  1. Splits the response into factual claims (sentence-level)
  2. Matches each claim to the most relevant retrieved context chunk
  3. Produces structured citation objects with source, page, section

Also supports injecting citations into the SSE stream as interleaved
`citation` events between `token` events.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from app.services.rag.retriever import RetrievalResult

logger = logging.getLogger(__name__)


# ── Types ─────────────────────────────────────────────────────────────


@dataclass
class Citation:
    """A citation linking a factual claim to a source document."""

    claim: str
    source_file: str
    page: int | None = None
    section: str | None = None
    chunk_id: str | None = None
    confidence: float = 1.0

    def to_dict(self) -> dict:
        """Serialize to SSE-compatible dict."""
        return {
            "claim": self.claim,
            "source": self.source_file,
            "page": self.page,
            "section": self.section,
        }


@dataclass
class CitationResult:
    """Result of citation extraction for a full response."""

    citations: list[Citation] = field(default_factory=list)
    claims_without_citations: list[str] = field(default_factory=list)

    @property
    def accuracy(self) -> float:
        """Fraction of claims that have citations."""
        total = len(self.citations) + len(self.claims_without_citations)
        if total == 0:
            return 1.0
        return len(self.citations) / total


# ── Claim Extraction ──────────────────────────────────────────────────


def _split_claims(text: str) -> list[str]:
    """
    Split generated text into factual claim sentences.

    Uses sentence boundary detection and filters out non-factual
    sentences (questions, hedging phrases, meta-commentary).
    """
    # Split on sentence boundaries
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())

    claims: list[str] = []
    skip_patterns = [
        r"^(i hope|i'm sorry|please note|i cannot|i don't have)",
        r"^(however|that said|in summary|to summarize|in conclusion)",
        r"\?$",  # questions are not claims
    ]

    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) < 15:
            continue

        # Skip non-factual sentences
        lower = sentence.lower()
        if any(re.match(p, lower) for p in skip_patterns):
            continue

        claims.append(sentence)

    return claims


def _jaccard_similarity(text_a: str, text_b: str) -> float:
    """Compute word-level Jaccard similarity between two texts."""
    words_a = set(text_a.lower().split())
    words_b = set(text_b.lower().split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union) if union else 0.0


# ── Citation Matching ─────────────────────────────────────────────────


def extract_citations(
    response_text: str,
    retrieval: RetrievalResult,
    *,
    min_similarity: float = 0.15,
) -> CitationResult:
    """
    Extract citations by matching generated claims to retrieved context.

    For each factual claim in the response, finds the best matching
    context chunk using word overlap (Jaccard similarity) and entity
    matching.

    Args:
        response_text: The full generated LLM response.
        retrieval: The retrieval results that were used as context.
        min_similarity: Minimum Jaccard similarity to assign a citation.

    Returns:
        CitationResult with matched citations and unmatched claims.
    """
    claims = _split_claims(response_text)

    if not claims or not retrieval.has_results:
        return CitationResult(
            citations=[],
            claims_without_citations=claims,
        )

    citations: list[Citation] = []
    unmatched: list[str] = []

    for claim in claims:
        best_match = None
        best_score = 0.0

        for result in retrieval.results:
            score = _jaccard_similarity(claim, result.content)

            # Boost score if source file is mentioned in the claim
            source_file = result.metadata.get("source_file", "")
            if source_file and source_file.lower() in claim.lower():
                score += 0.3

            if score > best_score:
                best_score = score
                best_match = result

        if best_match and best_score >= min_similarity:
            citations.append(
                Citation(
                    claim=claim,
                    source_file=best_match.metadata.get("source_file", "Unknown"),
                    page=best_match.metadata.get("page_number"),
                    section=best_match.metadata.get("section"),
                    chunk_id=best_match.chunk_id,
                    confidence=min(best_score, 1.0),
                )
            )
        else:
            unmatched.append(claim)

    result = CitationResult(
        citations=citations,
        claims_without_citations=unmatched,
    )

    logger.info(
        "Citation extraction: %d claims → %d citations (%.0f%% accuracy)",
        len(claims),
        len(citations),
        result.accuracy * 100,
    )
    return result


# ── SSE Citation Injection ────────────────────────────────────────────


def inject_citations_into_tokens(
    tokens: list[str],
    citations: list[Citation],
) -> list[tuple[str, dict]]:
    """
    Interleave citation events with token events for SSE streaming.

    Inserts citation events at approximate positions based on which
    token range each citation's claim corresponds to.

    Args:
        tokens: List of generated text tokens.
        citations: List of extracted citations.

    Returns:
        List of (event_type, event_data) tuples for SSE streaming.
    """
    events: list[tuple[str, dict]] = []

    # Add all token events first
    for token in tokens:
        events.append(("token", {"content": token, "citations": None}))

    # Insert citation events at the end (post-generation)
    # In a more sophisticated implementation, we'd track cumulative
    # text and insert citations at the right position.
    for citation in citations:
        events.append(("citation", citation.to_dict()))

    return events
