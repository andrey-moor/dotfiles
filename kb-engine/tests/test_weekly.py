import numpy as np

from kb_engine.models import TopicMember
from kb_engine.store import Store
from kb_engine.topics.weekly import WeeklyTopicsResult, weekly_topic_pass


class NoiseClusterer:
    """All-noise clusterer sized to its input (FakeClusterer needs exact-length
    labels known upfront; the weekly residual size varies with geometry)."""

    def cluster(self, vectors: np.ndarray) -> np.ndarray:
        return np.full(len(vectors), -1, dtype=int)


def _store_with_topicked_corpus(tmp_path, real_vectors):
    """Two manual topics seeded from fixture groups + a handful of loose notes."""
    store = Store(tmp_path / "t.db")
    store.init_schema()
    groups: dict[str, list[tuple[str, np.ndarray]]] = {}
    for entry, row in zip(real_vectors.entries, real_vectors.matrix):
        if entry["group"].startswith("topic:"):
            groups.setdefault(entry["group"], []).append((entry["path"], row))
    two = [g for g in groups.values() if len(g) >= 2][:2]
    for i, members in enumerate(two):
        slug = f"seed{i}"
        anchor = np.mean([v for _, v in members], axis=0)
        store.add_manual_topic(
            slug, slug.upper(), "d", (anchor / np.linalg.norm(anchor)).astype(np.float32)
        )
        rows = []
        for path, vec in members:
            store.upsert_note(path, path, f"sha-{path}", [])
            store.replace_chunks(path, [(0, path, vec)])
            rows.append(TopicMember(note_path=path, score=0.8, source="auto"))
        store.set_members(slug, rows)
    for path, vec in real_vectors.by_group("unfiled"):
        store.upsert_note(path, path, f"sha-{path}", [])
        store.replace_chunks(path, [(0, path, vec)])
    return store


def _store_with_wide_topics(tmp_path, real_vectors):
    """Two manual topics each seeded from THREE related fixture groups (6 members
    apiece) — a spread wide enough that the first derive's p25 bar sheds each
    topic's bottom quartile on pass 1. Six members keep the survivors >= 3, so
    re-anchoring stays stable and the threshold is the only contraction lever."""
    store = Store(tmp_path / "t.db")
    store.init_schema()
    seeds = {
        "aiwide": ("topic:ai-agents", "topic:ai-industry", "topic:ai-memory-mcp"),
        "bookswide": ("topic:books-ml-ai", "topic:books-writing", "topic:career-ai"),
    }
    for slug, groups in seeds.items():
        members = [mv for g in groups for mv in real_vectors.by_group(g)]
        anchor = np.mean([v for _, v in members], axis=0)
        store.add_manual_topic(
            slug, slug.upper(), "d", (anchor / np.linalg.norm(anchor)).astype(np.float32)
        )
        rows = []
        for path, vec in members:
            store.upsert_note(path, path, f"sha-{path}", [])
            store.replace_chunks(path, [(0, path, vec)])
            rows.append(TopicMember(note_path=path, score=0.8, source="auto"))
        store.set_members(slug, rows)
    for path, vec in real_vectors.by_group("unfiled"):
        store.upsert_note(path, path, f"sha-{path}", [])
        store.replace_chunks(path, [(0, path, vec)])
    return store


def _member_snapshot(store):
    return {
        t.slug: sorted(m.note_path for m in store.topic_members(t.slug))
        for t in store.load_topics()
    }


def test_weekly_pass_does_not_contract_membership(tmp_path, real_vectors):
    """The no-contraction property (the whole point of growth-gated re-derive):
    two consecutive passes over an UNCHANGED corpus assign the SAME notes. The
    first pass's derive tightens the bar and sheds each topic's bottom quartile;
    the second pass must NOT re-derive off the shrunken membership and shed
    again — assignment is a fixed point after pass 1."""
    store = _store_with_wide_topics(tmp_path, real_vectors)

    result1 = weekly_topic_pass(store, NoiseClusterer())
    snap1 = _member_snapshot(store)

    result2 = weekly_topic_pass(store, NoiseClusterer())
    snap2 = _member_snapshot(store)

    # Pass 1 genuinely tightened: each seeded topic shed from its 6 seeds.
    assert all(len(snap1[slug]) < 6 for slug in ("aiwide", "bookswide"))
    # No further shed on pass 2 — same count, same exact note-sets per topic.
    assert result2.assigned == result1.assigned
    assert snap2 == snap1
    store.close()


def test_weekly_pass_end_to_end(tmp_path, real_vectors):
    store = _store_with_topicked_corpus(tmp_path, real_vectors)
    n_notes = store.count_notes()
    result = weekly_topic_pass(store, NoiseClusterer())
    assert isinstance(result, WeeklyTopicsResult)
    # both seeded topics have <3 members? no — each has >=2; only >=3 reanchor.
    assert result.thresholds_set >= 1
    assert result.assigned >= 2  # at minimum the seeded members re-assign home
    assert result.assigned + result.queued + result.unfiled <= n_notes
    # members were written with real primary/secondary semantics
    primaries = [
        m for t in store.load_topics() for m in store.topic_members(t.slug)
        if m.is_primary
    ]
    assert len({m.note_path for m in primaries}) == len(primaries), (
        "a note must be primary in at most one topic"
    )
    store.close()


def test_weekly_pass_skips_user_pinned_notes(tmp_path, real_vectors):
    store = _store_with_topicked_corpus(tmp_path, real_vectors)
    pinned = store.topic_members("seed0")[0].note_path
    store.set_members(
        "seed1", [TopicMember(note_path=pinned, score=1.0, source="user", is_primary=True)]
    )
    weekly_topic_pass(store, NoiseClusterer())
    members1 = {m.note_path: m for m in store.topic_members("seed1")}
    assert members1[pinned].source == "user"
    seed0_auto = [
        m for m in store.topic_members("seed0")
        if m.note_path == pinned and m.source == "auto" and m.is_primary
    ]
    assert seed0_auto == [], "user-pinned note must not be auto-primaried elsewhere"
    store.close()


def test_weekly_pass_queues_borderline(tmp_path, real_vectors):
    store = _store_with_topicked_corpus(tmp_path, real_vectors)
    weekly_topic_pass(store, NoiseClusterer())
    for entry in store.load_review_queue():
        assert entry.reason == "borderline"
        assert entry.candidates
    store.close()


def test_weekly_pass_annotates_queue_reason_when_hook_given(tmp_path, real_vectors):
    # The pipeline supplies an LLM closure only when a key is set; here a fake
    # hook stands in — each borderline reason passes through it.
    store = _store_with_topicked_corpus(tmp_path, real_vectors)
    weekly_topic_pass(
        store,
        NoiseClusterer(),
        annotate=lambda reason, cands: f"{reason}; llm: x (0.90)",
    )
    queue = store.load_review_queue()
    assert queue  # this corpus reliably produces borderline entries
    for entry in queue:
        assert entry.reason == "borderline; llm: x (0.90)"
    store.close()
