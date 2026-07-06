"""Retrieval evaluation: vault-resident probes, recall@k and MRR metrics."""

from dataclasses import dataclass
from pathlib import Path

import yaml


class ProbeError(ValueError):
    """probes.yaml is missing, malformed, or incomplete."""


@dataclass(frozen=True)
class Probe:
    query: str
    expect: tuple[str, ...]  # any-of vault-relative note paths


@dataclass(frozen=True)
class ProbeOutcome:
    query: str
    hit_rank: int | None  # 1-based rank of the first expected hit; None = miss


@dataclass(frozen=True)
class EvalReport:
    outcomes: tuple[ProbeOutcome, ...]
    k: int

    @property
    def recall(self) -> float:
        if not self.outcomes:
            return 0.0
        hits = sum(1 for o in self.outcomes if o.hit_rank is not None)
        return hits / len(self.outcomes)

    @property
    def mrr(self) -> float:
        if not self.outcomes:
            return 0.0
        total = sum(1 / o.hit_rank for o in self.outcomes if o.hit_rank is not None)
        return total / len(self.outcomes)


def load_probes(path: Path) -> tuple[Probe, ...]:
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, list) or not data:
        raise ProbeError(f"{path}: expected a non-empty list of probes")
    probes: list[Probe] = []
    for i, item in enumerate(data):
        query = item.get("query") if isinstance(item, dict) else None
        expect = item.get("expect") if isinstance(item, dict) else None
        if not query or not isinstance(expect, list) or not expect:
            raise ProbeError(f"{path}: probe {i} needs 'query' and a non-empty 'expect' list")
        probes.append(Probe(query=str(query), expect=tuple(str(e) for e in expect)))
    return tuple(probes)


def rank_of_first_hit(ranked_paths: list[str], expect: tuple[str, ...]) -> int | None:
    expected = set(expect)
    for rank, path in enumerate(ranked_paths, start=1):
        if path in expected:
            return rank
    return None


def evaluate(
    per_probe_ranked: list[list[str]], probes: tuple[Probe, ...], k: int
) -> EvalReport:
    outcomes = tuple(
        ProbeOutcome(query=p.query, hit_rank=rank_of_first_hit(ranked[:k], p.expect))
        for p, ranked in zip(probes, per_probe_ranked, strict=True)
    )
    return EvalReport(outcomes=outcomes, k=k)
