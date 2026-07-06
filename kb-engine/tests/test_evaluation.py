import pytest

from kb_engine.evaluation import (
    EvalReport,
    Probe,
    ProbeError,
    ProbeOutcome,
    evaluate,
    load_probes,
    rank_of_first_hit,
)


def test_load_probes_parses_query_and_expect(tmp_path):
    f = tmp_path / "probes.yaml"
    f.write_text(
        '- query: "find x"\n  expect:\n    - "Knowledge/a.md"\n    - "Knowledge/b.md"\n'
    )
    probes = load_probes(f)
    assert probes == (Probe(query="find x", expect=("Knowledge/a.md", "Knowledge/b.md")),)


def test_load_probes_rejects_missing_fields(tmp_path):
    f = tmp_path / "probes.yaml"
    f.write_text('- query: "no expect"\n')
    with pytest.raises(ProbeError):
        load_probes(f)


def test_rank_of_first_hit_is_one_based_and_any_of():
    assert rank_of_first_hit(["x", "b", "a"], expect=("a", "b")) == 2
    assert rank_of_first_hit(["x", "y"], expect=("a",)) is None


def test_evaluate_recall_and_mrr():
    probes = (Probe("q1", ("a",)), Probe("q2", ("b",)), Probe("q3", ("c",)))
    ranked = [["a", "x"], ["x", "b"], ["x", "y"]]  # ranks: 1, 2, miss
    report = evaluate(ranked, probes, k=5)
    assert report.outcomes == (
        ProbeOutcome("q1", 1),
        ProbeOutcome("q2", 2),
        ProbeOutcome("q3", None),
    )
    assert report.recall == pytest.approx(2 / 3)
    assert report.mrr == pytest.approx((1 + 0.5 + 0) / 3)


def test_evaluate_respects_k_cutoff():
    probes = (Probe("q", ("deep",)),)
    report = evaluate([["a", "b", "c", "d", "e", "deep"]], probes, k=5)
    assert report.outcomes[0].hit_rank is None
