"""Shared command helpers: env-driven embedder/clusterer builders and JSON/human emit."""
import json
import os

import click

from kb_engine.config import Config
from kb_engine.embeddings import Embedder, FakeEmbedder, LocalJinaEmbedder
from kb_engine.topics.clustering import Clusterer, FakeClusterer, UmapHdbscanClusterer

DEFAULT_SEARCH_LIMIT = 10


def _build_embedder(cfg: Config) -> Embedder:
    """Use the deterministic FakeEmbedder when KB_FAKE_EMBED=1, else real jina-v3."""
    if os.environ.get("KB_FAKE_EMBED") == "1":
        return FakeEmbedder(dim=cfg.embed_dim)
    return LocalJinaEmbedder(model_name=cfg.model_name, dim=cfg.embed_dim)


def _build_clusterer(
    cluster_selection_method: str = "leaf", min_cluster_size: int | None = None
) -> Clusterer:
    """Use a deterministic FakeClusterer when KB_FAKE_CLUSTER is set, else real UMAP/HDBSCAN.

    KB_FAKE_CLUSTER is a comma-separated list of int labels (-1 = noise), e.g.
    "0,0,-1". An empty/unset value falls back to the real clusterer.
    ``cluster_selection_method`` is "leaf" (finer topics) or "eom" (broader).
    ``min_cluster_size`` overrides the adaptive ladder when set (must be >= 2).
    """
    raw = os.environ.get("KB_FAKE_CLUSTER", "").strip()
    if raw:
        labels = [int(part) for part in raw.split(",")]
        return FakeClusterer(labels=labels)
    return UmapHdbscanClusterer(
        cluster_selection_method=cluster_selection_method,
        min_cluster_size=min_cluster_size,
    )


def _emit(payload: dict, as_json: bool, human: str) -> None:
    if as_json:
        click.echo(json.dumps(payload))
    else:
        click.echo(human)
