"""Pure retrieval ranking metrics for Phase 5.10 evaluation."""

from __future__ import annotations


def recall_at_k(
    relevant: list[int] | set[int],
    ranked: list[int],
    k: int,
) -> float:
    """Fraction of relevant IDs appearing in the top-k ranked results."""
    if k < 1:
        raise ValueError("k must be >= 1")
    relevant_set = set(relevant)
    if not relevant_set:
        return 0.0
    top = ranked[:k]
    found = {item for item in top if item in relevant_set}
    return len(found) / len(relevant_set)


def precision_at_k(
    relevant: list[int] | set[int],
    ranked: list[int],
    k: int,
) -> float:
    """Fraction of top-k ranked results that are relevant."""
    if k < 1:
        raise ValueError("k must be >= 1")
    relevant_set = set(relevant)
    top = ranked[:k]
    if not top:
        return 0.0
    hits = sum(1 for item in top if item in relevant_set)
    return hits / len(top)


def mean_reciprocal_rank(
    relevant: list[int] | set[int],
    ranked: list[int],
) -> float:
    """1 / rank of the first relevant hit (0 if none)."""
    relevant_set = set(relevant)
    if not relevant_set or not ranked:
        return 0.0
    for index, item in enumerate(ranked, start=1):
        if item in relevant_set:
            return 1.0 / index
    return 0.0


def compute_retrieval_metrics(
    relevant: list[int] | set[int],
    ranked: list[int],
    *,
    ks: tuple[int, ...] = (1, 3, 5),
) -> dict[str, float]:
    metrics: dict[str, float] = {"mrr": mean_reciprocal_rank(relevant, ranked)}
    for k in ks:
        metrics[f"recall_at_{k}"] = recall_at_k(relevant, ranked, k)
        metrics[f"precision_at_{k}"] = precision_at_k(relevant, ranked, k)
    return metrics
