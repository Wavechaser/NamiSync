"""Bounded, current-document host-to-page messages for WebView2."""

from __future__ import annotations

import json
import logging
from threading import Lock
from typing import Callable


_MAX_DOCUMENT_MESSAGE_BYTES = 65_536


class DocumentMessageTooLargeError(ValueError):
    """An outbound document message exceeds the fixed channel ceiling."""


class DocumentStaleError(RuntimeError):
    """The intended document was replaced before its message could be posted."""


class DocumentChannel:
    """Post one bounded message on the UI thread to a still-current document."""

    def __init__(
        self,
        native_window: object,
        *,
        invoke: Callable[[object, Callable[[], None]], None] | None = None,
    ) -> None:
        self._native_window = native_window
        self._invoke = invoke or _invoke_on_ui

    def post(
        self,
        payload: object,
        *,
        still_current: Callable[[], bool],
        completion: Callable[[Exception | None], None],
    ) -> None:
        """Schedule ``payload`` and report its single terminal result."""

        if not callable(still_current):
            raise TypeError("document currency predicate must be callable")
        if not callable(completion):
            raise TypeError("document post completion must be callable")

        complete = _Completion(completion)
        try:
            encoded = json.dumps(
                payload,
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            if len(encoded.encode("utf-8")) > _MAX_DOCUMENT_MESSAGE_BYTES:
                raise DocumentMessageTooLargeError(
                    "document message exceeds the 65536-byte channel ceiling"
                )
        except Exception as error:
            complete(error)
            return

        def publish() -> None:
            try:
                current = still_current()
                if type(current) is not bool:
                    raise TypeError("document currency predicate must return bool")
                if not current:
                    raise DocumentStaleError(
                        "document was replaced before its message was posted"
                    )
                core = self._native_window.browser.webview.CoreWebView2
                core.PostWebMessageAsJson(encoded)
            except Exception as error:
                complete(error)
                return
            complete(None)

        try:
            self._invoke(self._native_window, publish)
        except Exception as error:
            complete(error)


class _Completion:
    """Make a possibly re-entrant channel completion exactly-once."""

    def __init__(self, callback: Callable[[Exception | None], None]) -> None:
        self._callback = callback
        self._lock = Lock()
        self._finished = False

    def __call__(self, error: Exception | None) -> None:
        with self._lock:
            if self._finished:
                return
            self._finished = True
        try:
            self._callback(error)
        except Exception as callback_error:
            logging.getLogger("namisync").error(
                "document_channel.completion_failed exception_type=%s",
                type(callback_error).__name__,
            )


def _invoke_on_ui(
    native_window: object,
    callback: Callable[[], None],
) -> None:
    if not native_window.InvokeRequired:
        callback()
        return
    from System import Action

    native_window.BeginInvoke(Action(callback))
