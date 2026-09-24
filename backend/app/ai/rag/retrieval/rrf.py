"""Reciprocal Rank Fusion for hybrid retrieval rankings."""

from __future__ import annotations

from collections.abc import Sequence


def fuse_rankings(
    *ranked_id_lists: Sequence[int],
    k: int = 60,
) -> list[tuple[int, float]]:
    """Fuse one or more ranked result lists with RRF.

    RRF_score(d) = Σ 1 / (k + rank_i(d)) with 1-based ranks.
    Returns (chunk_id, score) sorted by score DESC, then chunk_id ASC.
    Duplicate IDs within a single list use the first occurrence only.
    """
    if k < 1:
        raise ValueError("RRF k must be >= 1")

    scores: dict[int, float] = {}
    for ranked in ranked_id_lists:
        seen: set[int] = set()
        for index, chunk_id in enumerate(ranked):
            if chunk_id in seen:
                continue
            seen.add(chunk_id)
            rank = index + 1
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)

    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))
