from __future__ import annotations

import json
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


@pytest.mark.parametrize("schema_version", [True, 1.0, "1"])
def test_semantic_settings_schema_version_requires_an_exact_integer(
    tmp_path: Path,
    schema_version: object,
) -> None:
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": schema_version,
                "filters": [],
                "deletion_policy": "trash",
                "trash_on_update": True,
                "preservation": {
                    "preserve_ads": False,
                    "preserve_created": True,
                    "preserve_acl": False,
                },
                "propagate_source_casing": False,
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(SettingsFormatError, match="unsupported"):
        SemanticSettingsStore(path).read()


def test_semantic_settings_reject_duplicate_json_keys(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(
        '{"schema_version":1,"schema_version":1,"filters":[],'
        '"deletion_policy":"trash","trash_on_update":true,'
        '"preservation":{"preserve_ads":false,"preserve_created":true,'
        '"preserve_acl":false},"propagate_source_casing":false}',
        encoding="utf-8",
    )

    with pytest.raises(SettingsFormatError, match="duplicate"):
        SemanticSettingsStore(path).read()


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
