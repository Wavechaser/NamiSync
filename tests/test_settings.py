from __future__ import annotations

import multiprocessing
from pathlib import Path

import pytest

from namisync.core.planning import (
    DeletionPolicy,
    FilterSet,
    PreservationPolicy,
    policy_fingerprint,
)
from namisync.db.settings import (
    SemanticSettings,
    SemanticSettingsPatch,
    SemanticSettingsStore,
    SettingsFormatError,
)
from namisync.interfaces.ui_state import UiState, UiStateFormatError, UiStateStore


def _delayed_filter_commit(
    path: str,
    entered,
    release,
    results,
) -> None:
    import namisync.db.settings as settings_module

    original_write = settings_module._atomic_write

    def delayed_write(target, payload) -> None:
        entered.set()
        if not release.wait(10):
            raise TimeoutError("test did not release delayed settings writer")
        original_write(target, payload)

    settings_module._atomic_write = delayed_write
    try:
        value = SemanticSettingsStore(path).commit(
            SemanticSettingsPatch(filters=FilterSet(("*.tmp",)))
        )
        results.put(("filter", value.filters.patterns, value.deletion_policy.value))
    except BaseException as error:
        results.put(("error", type(error).__name__, str(error)))


def _deletion_commit(path: str, started, results) -> None:
    started.set()
    try:
        value = SemanticSettingsStore(path).commit(
            SemanticSettingsPatch(deletion_policy=DeletionPolicy.ADDITIVE)
        )
        results.put(("deletion", value.filters.patterns, value.deletion_policy.value))
    except BaseException as error:
        results.put(("error", type(error).__name__, str(error)))


def test_semantic_settings_round_trip_and_capture_immutable_options(
    tmp_path: Path,
) -> None:
    store = SemanticSettingsStore(tmp_path / "settings.json")
    original = store.read()
    captured_options = original.to_sync_options()
    captured_fingerprint = policy_fingerprint(captured_options)

    updated = store.commit(
        SemanticSettingsPatch(
            filters=FilterSet(("*.bak", "*.tmp")),
            deletion_policy=DeletionPolicy.ADDITIVE,
            trash_on_update=False,
            preservation=PreservationPolicy(
                preserve_ads=True,
                preserve_created=False,
                preserve_acl=True,
            ),
            propagate_source_casing=True,
        )
    )

    assert store.read() == updated
    assert captured_options == original.to_sync_options()
    assert policy_fingerprint(captured_options) == captured_fingerprint
    assert policy_fingerprint(updated.to_sync_options()) != captured_fingerprint


def test_semantic_settings_reject_hidden_mirror_and_bad_schema(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="mirror"):
        SemanticSettings(deletion_policy=DeletionPolicy.MIRROR)

    path = tmp_path / "settings.json"
    path.write_text(
        '{"deletion_policy":"trash","filters":[],"preservation":'
        '{"preserve_acl":false,"preserve_ads":false,"preserve_created":true},'
        '"propagate_source_casing":false,"schema_version":999,'
        '"trash_on_update":true}',
        encoding="utf-8",
    )
    with pytest.raises(SettingsFormatError, match="unsupported"):
        SemanticSettingsStore(path).read()

    with pytest.raises(ValueError, match="mirror"):
        SemanticSettingsStore(tmp_path / "mirror-settings.json").commit(
            SemanticSettingsPatch(deletion_policy=DeletionPolicy.MIRROR)
        )


def test_concurrent_semantic_commits_reread_under_named_mutex(
    tmp_path: Path,
) -> None:
    context = multiprocessing.get_context("spawn")
    entered = context.Event()
    release = context.Event()
    started = context.Event()
    results = context.Queue()
    path = str(tmp_path / "settings.json")
    first = context.Process(
        target=_delayed_filter_commit,
        args=(path, entered, release, results),
    )
    second = context.Process(
        target=_deletion_commit,
        args=(path, started, results),
    )

    first.start()
    assert entered.wait(10)
    second.start()
    assert started.wait(10)
    release.set()
    first.join(10)
    second.join(10)

    assert first.exitcode == 0
    assert second.exitcode == 0
    outcomes = {results.get(timeout=2)[0], results.get(timeout=2)[0]}
    assert outcomes == {"filter", "deletion"}
    assert SemanticSettingsStore(path).read() == SemanticSettings(
        filters=FilterSet(("*.tmp",)),
        deletion_policy=DeletionPolicy.ADDITIVE,
    )


def test_ui_state_keeps_source_and_target_recents_separate_and_bounded(
    tmp_path: Path,
) -> None:
    value = UiState()
    for index in range(7):
        value = value.remember_source(rf"C:\source-{index}")
    value = value.remember_target(r"D:\target").remember_source(r"C:\source-4")
    store = UiStateStore(tmp_path / "ui-state.json")
    store.write(value)

    decoded = store.read()
    assert decoded.recent_sources == (
        r"C:\source-4",
        r"C:\source-6",
        r"C:\source-5",
        r"C:\source-3",
        r"C:\source-2",
    )
    assert decoded.recent_targets == (r"D:\target",)


def test_ui_state_rejects_unknown_top_level_keys(tmp_path: Path) -> None:
    path = tmp_path / "ui-state.json"
    path.write_text('{"recent_sources":[]}', encoding="utf-8")

    with pytest.raises(UiStateFormatError, match="missing or unknown"):
        UiStateStore(path).read()


def test_ui_state_rejects_non_json_nested_state() -> None:
    with pytest.raises(ValueError, match="string-keyed"):
        UiState(window={"nested": {1: "not-json"}})
    with pytest.raises(ValueError, match="finite"):
        UiState(columns={"width": float("nan")})
