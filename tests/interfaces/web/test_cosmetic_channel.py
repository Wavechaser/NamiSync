"""Native/browser evidence for the typed cosmetic bridge channel."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

import namisync.interfaces.web.bridge as bridge_module
from namisync.interfaces.ui_state import (
    AppearanceValue,
    ThemeMode,
    UiStateOwner,
)
from namisync.interfaces.web.bridge import (
    AdmissionGranted,
    AdmissionRefused,
    BridgeDispatcher,
)
from namisync.interfaces.web.commands import production_command_specs
from namisync.interfaces.web.readiness import CommandPhase, ReadinessContext
from _frontend_test_support import _node_executable


def _bridge_source() -> str:
    return (
        Path(bridge_module.__file__).parent / "assets" / "bridge.js"
    ).read_text(encoding="utf-8")


class _Document:
    def __init__(self, *, trusted: bool = True) -> None:
        self.trusted = trusted

    def require_trusted(self) -> None:
        if not self.trusted:
            raise PermissionError("private origin detail")


def _commands(cosmetics: UiStateOwner):
    return production_command_specs(
        picker=lambda: None,
        slots=object(),  # type: ignore[arg-type]
        registry=object(),  # type: ignore[arg-type]
        cosmetics=cosmetics,
        shell_ready=lambda _generation: None,
        readiness_echo=lambda _generation, _challenge: False,
    )


def _request(command: str, payload: object, *, request_id: str) -> str:
    return json.dumps(
        {
            "schema_version": 1,
            "request_id": request_id,
            "command": command,
            "payload": payload,
        },
        separators=(",", ":"),
    )


def _dispatcher(
    cosmetics: UiStateOwner,
    *,
    trusted: bool = True,
    open_phase: bool = True,
) -> BridgeDispatcher:
    context = ReadinessContext(CommandPhase.OPEN, 1)
    return BridgeDispatcher(
        document=_Document(trusted=trusted),  # type: ignore[arg-type]
        commands=_commands(cosmetics),
        admit=(
            (lambda _name: AdmissionGranted(context))
            if open_phase
            else (lambda _name: AdmissionRefused())
        ),
    )


def test_br_g_46_native_bridge_round_trips_only_typed_cosmetic_state(
    tmp_path: Path,
) -> None:
    path = tmp_path / "ui-state.json"
    owner = UiStateOwner(path, write_delay_seconds=60.0)
    dispatcher = _dispatcher(owner)
    try:
        read = dispatcher.dispatch(
            _request(
                "read_cosmetic_section",
                {
                    "section": "appearance",
                    "value_version": 1,
                    "applied_presentation_revision": None,
                },
                request_id="11" * 16,
            )
        )
        assert read == {
            "schema_version": 1,
            "request_id": "11" * 16,
            "ok": True,
            "result": {
                "section": "appearance",
                "value_version": 1,
                "revision": 0,
                "dirty": False,
                "value": {"theme": "system"},
            },
        }

        replaced = dispatcher.dispatch(
            _request(
                "replace_cosmetic_section",
                {
                    "section": "appearance",
                    "value_version": 1,
                    "expected_revision": 0,
                    "value": {"theme": "light"},
                },
                request_id="22" * 16,
            )
        )
        assert replaced["ok"] is True
        assert replaced["result"] == {
            "section": "appearance",
            "value_version": 1,
            "revision": 1,
            "dirty": True,
            "value": {"theme": "light"},
            "disposition": "applied",
        }
        assert owner.read_section("appearance", 1).value == AppearanceValue(
            ThemeMode.LIGHT
        )
    finally:
        owner.close()

    assert json.loads(path.read_text(encoding="utf-8")) == {
        "schema_version": 1,
        "sections": {
            "appearance": {
                "value_version": 1,
                "value": {"theme": "light"},
            }
        },
    }


@pytest.mark.parametrize(
    ("trusted", "open_phase", "payload", "expected_code"),
    [
        (
            False,
            True,
            {
                "section": "appearance",
                "value_version": 1,
                "expected_revision": 0,
                "value": {"theme": "dark"},
            },
            "bridge_unavailable",
        ),
        (
            True,
            False,
            {
                "section": "appearance",
                "value_version": 1,
                "expected_revision": 0,
                "value": {"theme": "dark"},
            },
            "bridge_unavailable",
        ),
        (
            True,
            True,
            {
                "section": "appearance",
                "value_version": 1,
                "expected_revision": True,
                "value": {"theme": "dark"},
            },
            "invalid_payload",
        ),
    ],
)
def test_br_g_46_refused_cosmetic_requests_cannot_mutate_state_or_file(
    tmp_path: Path,
    trusted: bool,
    open_phase: bool,
    payload: object,
    expected_code: str,
) -> None:
    path = tmp_path / "ui-state.json"
    owner = UiStateOwner(path)
    dispatcher = _dispatcher(owner, trusted=trusted, open_phase=open_phase)
    try:
        response = dispatcher.dispatch(
            _request(
                "replace_cosmetic_section",
                payload,
                request_id="33" * 16,
            )
        )
        assert response["ok"] is False
        assert response["error"]["code"] == expected_code  # type: ignore[index]
        snapshot = owner.read_section("appearance", 1)
        assert snapshot.revision == 0
        assert snapshot.dirty is False
        assert snapshot.value == AppearanceValue(ThemeMode.SYSTEM)
    finally:
        owner.close()

    assert not path.exists()


def test_br_g_46_oversized_cosmetic_envelope_cannot_mutate_state_or_file(
    tmp_path: Path,
) -> None:
    path = tmp_path / "ui-state.json"
    owner = UiStateOwner(path)
    try:
        response = _dispatcher(owner).dispatch("x" * 65_537)
        assert response["ok"] is False
        assert response["error"]["code"] == "request_too_large"  # type: ignore[index]
        assert owner.read_section("appearance", 1).dirty is False
    finally:
        owner.close()

    assert not path.exists()


def test_br_g_46_browser_cosmetic_rows_are_exact_and_locally_bounded() -> None:
    source = _bridge_source()
    match = re.search(
        r"const COMMAND_POLICY_JSON = `([\s\S]*?)`;",
        source,
    )
    assert match is not None
    policy = json.loads(match.group(1))

    assert policy["read_cosmetic_section"] == {
        "timeout": "local-5-seconds",
        "retry": "same-payload-once",
        "phase": "open",
    }
    assert policy["replace_cosmetic_section"] == {
        "timeout": "local-5-seconds",
        "retry": "none",
        "phase": "open",
    }
    assert '"local-5-seconds": 5000' in source
    assert (
        "export async function readCosmeticSection("
        "appliedPresentationRevision = null)" in source
    )
    assert (
        "export function replaceCosmeticSection(expectedRevision, theme)"
        in source
    )


@pytest.mark.supplemental_node
def test_supplemental_node_cosmetic_wrapper_and_validator_contract() -> None:
    node = _node_executable()
    if node is None:
        pytest.skip("Node.js is unavailable for the supplemental bridge probe")
    probe = Path(__file__).parents[2] / "assets" / "cosmetic_bridge_probe.mjs"
    bridge = Path(bridge_module.__file__).parent / "assets" / "bridge.js"

    completed = subprocess.run(
        [str(node), str(probe), str(bridge)],
        capture_output=True,
        check=False,
        text=True,
        timeout=15,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
