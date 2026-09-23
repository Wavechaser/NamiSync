"""Minimal native CDP transport shared by installed headed witnesses."""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from typing import Callable


def runtime_value(task: object) -> object:
    if task.IsFaulted or task.IsCanceled:
        raise RuntimeError("native CDP task failed")
    envelope = json.loads(str(task.Result))
    if type(envelope) is not dict or "exceptionDetails" in envelope:
        raise RuntimeError("native CDP expression failed")
    result = envelope.get("result")
    if type(result) is not dict:
        raise TypeError("native CDP result is invalid")
    return result.get("value")


def task_envelope(task: object) -> dict[str, object]:
    if task.IsFaulted or task.IsCanceled:
        raise RuntimeError("native CDP task failed")
    envelope = json.loads(str(task.Result))
    if type(envelope) is not dict or "exceptionDetails" in envelope:
        raise RuntimeError("native CDP method failed")
    return envelope


class NativeCdp:
    """Marshal CDP completions to the UI thread and persist native captures."""

    def __init__(
        self,
        native: object,
        core: object,
        retained: list[object],
        fail: Callable[[BaseException, object | None, str, str], None],
    ) -> None:
        self._native = native
        self._core = core
        self._retained = retained
        self._fail = fail

    def call(
        self,
        method: str,
        parameters: dict[str, object],
        then: Callable[[object], None],
        step: str,
    ) -> None:
        from System import Action

        try:
            task = self._core.CallDevToolsProtocolMethodAsync(
                method, json.dumps(parameters),
            )
        except BaseException as error:
            self._fail(error, None, step, method)
            return

        def completed() -> None:
            def finish() -> None:
                try:
                    then(task_envelope(task))
                except BaseException as error:
                    self._fail(error, task, step, method)

            action = Action(finish)
            self._retained.append(action)
            self._native.BeginInvoke(action)

        completion = Action(completed)
        self._retained.append(completion)
        task.GetAwaiter().OnCompleted(completion)

    def evaluate(
        self, expression: str, then: Callable[[object], None], step: str,
    ) -> None:
        self.call(
            "Runtime.evaluate",
            {"expression": expression, "awaitPromise": True, "returnByValue": True},
            lambda envelope: then(_evaluation_value(envelope)),
            step,
        )

    def dispatch(
        self, event: dict[str, object], then: Callable[[], None], step: str,
    ) -> None:
        self.call("Input.dispatchMouseEvent" if "x" in event else "Input.dispatchKeyEvent", event, lambda _value: then(), step)

    def capture(self, target: Path, then: Callable[[], None], step: str) -> None:
        def persist(value: object) -> None:
            data = value.get("data") if type(value) is dict else None
            if type(data) is not str:
                raise TypeError("native screenshot result is invalid")
            target.write_bytes(base64.b64decode(data, validate=True))
            then()

        self.call(
            "Page.captureScreenshot",
            {"format": "png", "fromSurface": True, "captureBeyondViewport": False},
            persist,
            step,
        )


def _evaluation_value(envelope: object) -> object:
    if type(envelope) is not dict:
        raise TypeError("native CDP evaluation envelope is invalid")
    result = envelope.get("result")
    if type(result) is not dict:
        raise TypeError("native CDP evaluation result is invalid")
    return result.get("value")


def decode_png(path: Path) -> tuple[int, int]:
    """Decode a completed capture with the native image stack."""
    import clr

    clr.AddReference("System.Drawing")
    from System.Drawing import Bitmap

    bitmap = Bitmap(str(path))
    try:
        width, height = int(bitmap.Width), int(bitmap.Height)
        if width <= 0 or height <= 0:
            raise ValueError("decoded PNG has invalid dimensions")
        return width, height
    finally:
        bitmap.Dispose()


def failure_site(task: object | None) -> dict[str, object]:
    """Retain bounded source locations, never exception text, URLs or paths."""
    if task is None or task.IsFaulted or task.IsCanceled:
        return {"exception": None, "lines": []}
    try:
        envelope = json.loads(str(task.Result))
        details = envelope.get("exceptionDetails", {})
        exception = details.get("exception", {}).get("className")
        if exception not in {"Error", "TypeError", "ReferenceError", "SyntaxError"}:
            exception = None
        frames = details.get("stackTrace", {}).get("callFrames", [])[:8]
        lines = [frame.get("lineNumber") for frame in frames if type(frame) is dict]
        lines = [line for line in lines if type(line) is int and 0 <= line <= 1000000]
        if not lines:
            description = details.get("exception", {}).get("description", "")
            if type(description) is str:
                lines = [int(match) - 1 for match in re.findall(
                    r"<anonymous>:(\d{1,6}):\d{1,6}", description[:8192],
                )[:8] if int(match) > 0]
        return {"exception": exception, "lines": lines}
    except (AttributeError, TypeError, ValueError):
        return {"exception": None, "lines": []}
