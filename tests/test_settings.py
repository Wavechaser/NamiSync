from __future__ import annotations

import json
import multiprocessing
from pathlib import Path

import pytest

import namisync.db.settings as settings_module

from namisync.core.planning import (
    DeletionPolicy,
    FilterSet,
    PreservationPolicy,
    policy_fingerprint,
)
from namisync.db.settings import (
    SETTINGS_MAX_BYTES,
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


def test_settings_read_admits_exact_byte_limit_and_rejects_n_plus_one_before_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "settings.json"
    calls: list[int] = []
    decoded = {
        "schema_version": 1,
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

    def accepted_loads(payload: str, **_kwargs):
        calls.append(len(payload))
        return decoded

    path.write_bytes(b" " * SETTINGS_MAX_BYTES)
    monkeypatch.setattr(settings_module.json, "loads", accepted_loads)
    assert SemanticSettingsStore(path).read() == SemanticSettings()
    assert calls == [SETTINGS_MAX_BYTES]

    path.write_bytes(b" " * (SETTINGS_MAX_BYTES + 1))

    def forbidden_loads(*_args, **_kwargs):
        raise AssertionError("oversized settings must not reach json.loads")

    monkeypatch.setattr(settings_module.json, "loads", forbidden_loads)
    with pytest.raises(SettingsFormatError, match="document byte limit"):
        SemanticSettingsStore(path).read()


def test_settings_filter_decode_rejects_n_plus_one_before_filter_construction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "settings.json"
    payload = {
        "schema_version": 1,
        "filters": [str(index) for index in range(65)],
        "deletion_policy": "trash",
        "trash_on_update": True,
        "preservation": {
            "preserve_ads": False,
            "preserve_created": True,
            "preserve_acl": False,
        },
        "propagate_source_casing": False,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")

    def forbidden_filter(*_args, **_kwargs):
        raise AssertionError("excess filters must not construct FilterSet")

    monkeypatch.setattr(settings_module, "FilterSet", forbidden_filter)
    with pytest.raises(SettingsFormatError, match="pattern limit"):
        SemanticSettingsStore(path).read()


def test_settings_derived_document_limit_is_attained_by_the_writer() -> None:
    patterns = tuple(
        "".join(chr(1 + ((index >> bit) & 1)) for bit in range(6))
        + (chr(1) * 250)
        for index in range(64)
    )
    settings = SemanticSettings(
        filters=FilterSet(patterns),
        deletion_policy=DeletionPolicy.ADDITIVE,
        trash_on_update=False,
        preservation=PreservationPolicy(
            preserve_ads=False,
            preserve_created=False,
            preserve_acl=False,
        ),
        propagate_source_casing=False,
    )

    assert sum(len(pattern.encode("utf-8")) for pattern in patterns) == 16_384
    assert len(settings_module._encode_settings(settings)) == SETTINGS_MAX_BYTES


def test_settings_commit_revalidates_a_forged_exact_patch_before_locking(
    tmp_path: Path,
) -> None:
    patch = SemanticSettingsPatch()
    object.__setattr__(patch, "trash_on_update", 1)

    with pytest.raises(TypeError, match="trash_on_update"):
        SemanticSettingsStore(tmp_path / "settings.json").commit(patch)


def test_semantic_settings_reject_aliasable_contract_values() -> None:
    class FilterSubclass(FilterSet):
        pass

    class PatchSubclass(SemanticSettingsPatch):
        pass

    with pytest.raises(TypeError, match="FilterSet"):
        SemanticSettings(filters=FilterSubclass())
    with pytest.raises(TypeError, match="SemanticSettingsPatch"):
        SemanticSettingsStore("settings.json").commit(PatchSubclass())


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
