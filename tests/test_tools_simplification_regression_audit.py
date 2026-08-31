from __future__ import annotations

import json

from tools import simplification_regression_audit as audit


def test_frozen_corpus_paths_are_closed_and_present() -> None:
    assert audit.FROZEN_CORPUS_PATHS == (
        "tests/_event_v5_fixtures.py",
        "tests/test_tools_simplification_regression_audit.py",
        "tools/simplification_regression_audit.py",
        "tools/simplification_regression_baseline.json",
    )
    assert all(
        (audit._REPOSITORY_ROOT / path).is_file()
        for path in audit.FROZEN_CORPUS_PATHS
    )


def test_event_corpus_freezes_all_v5_bodies_and_exact_reliable_wall() -> None:
    corpus = audit.build_event_corpus()

    assert set(corpus) == {
        "StateChanged",
        "PhaseChanged",
        "Progress",
        "ItemOutcome",
        "IntegrityOutcome",
        "Gap",
        "Terminal",
        "Terminal.review-limit",
        "ItemOutcome.maximum-reliable",
    }
    assert corpus["ItemOutcome.maximum-reliable"]["bytes"] == 1_048_576
    for name, row in corpus.items():
        assert row["bytes"] > 0, name
        assert len(row["sha256"]) == 64, name
        if "json" in row:
            assert json.loads(row["json"])["schema_version"] == 5


def test_committed_simplification_corpus_matches_production() -> None:
    audit.check(audit.DEFAULT_BASELINE, repeat=1)
