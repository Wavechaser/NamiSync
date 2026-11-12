"""Exercise bridge response admission through a real dispatcher."""

import json
from types import SimpleNamespace

from namisync.interfaces.web.bridge import AdmissionGranted, BridgeDispatcher
from namisync.interfaces.web.commands import (
    CommandAccess, CommandResponsePolicy, CommandRetry, CommandSpec, FieldRequirement,
)
from namisync.interfaces.web.readiness import CommandPhase, ReadinessContext


def dispatch_result(value: object) -> dict[str, object]:
    spec = CommandSpec(
        validate_payload=lambda payload: payload,
        handler=lambda _payload: value,
        access=CommandAccess.READ_ONLY,
        command_id=FieldRequirement.FORBIDDEN,
        revision=FieldRequirement.FORBIDDEN,
        response_policy=CommandResponsePolicy.INTERACTIVE,
        retry=CommandRetry.NONE,
        phase=CommandPhase.OPEN,
    )
    dispatcher = BridgeDispatcher(
        document=SimpleNamespace(require_trusted=lambda: None),
        commands={"probe": spec},
        admit=lambda _name: AdmissionGranted(ReadinessContext(CommandPhase.OPEN, 0)),
    )
    return dispatcher.dispatch(json.dumps({
        "schema_version": 1, "request_id": "a1" * 16,
        "command": "probe", "payload": {},
    }))
