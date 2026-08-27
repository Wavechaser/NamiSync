"""Bounded, current-document host-to-page messages for WebView2."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from enum import Enum
from threading import Lock
from typing import Callable

from namisync.dispatcher import retire_exception_graph
from namisync.interfaces.ui_state import MAX_JAVASCRIPT_SAFE_INTEGER


_MAX_DOCUMENT_MESSAGE_BYTES = 65_536
_Acknowledgment = int | tuple[int, str]


class DocumentMessageTooLargeError(ValueError):
    """An outbound document message exceeds the fixed channel ceiling."""


class DocumentStaleError(RuntimeError):
    """The intended document was replaced before its message could be posted."""


class DocumentRetiredError(DocumentStaleError):
    """The channel explicitly retired ownership for the prior document."""


class DocumentChannelBusyError(RuntimeError):
    """A required post is already waiting for the one native dispatch owner."""


class DocumentPostKind(Enum):
    REQUIRED = "required"
    REPLACEABLE = "replaceable"


class DocumentChannel:
    """Own one native dispatch and bounded required/replaceable post slots."""

    def __init__(
        self,
        native_window: object,
        *,
        invoke: Callable[[object, Callable[[], None]], None] | None = None,
        require_acknowledgment: bool = False,
    ) -> None:
        if type(require_acknowledgment) is not bool:
            raise TypeError("document acknowledgment policy must be Boolean")
        self._native_window = native_window
        self._invoke = invoke or _invoke_on_ui
        self._require_acknowledgment = require_acknowledgment
        self._lock = Lock()
        self._required: _PendingPost | None = None
        self._replaceable: _PendingPost | None = None
        self._in_flight: _PendingPost | _AwaitingAcknowledgment | None = None
        self._scheduled_token: object | None = None
        self._document_epoch = object()
        self._closed = False

    def post(
        self,
        payload: object,
        *,
        still_current: Callable[[], bool],
        completion: Callable[[Exception | None], None],
        kind: DocumentPostKind = DocumentPostKind.REQUIRED,
        acknowledgment: _Acknowledgment | None = None,
    ) -> None:
        """Schedule ``payload`` and report its single terminal result."""

        if not callable(still_current):
            raise TypeError("document currency predicate must be callable")
        if not callable(completion):
            raise TypeError("document post completion must be callable")
        if type(kind) is not DocumentPostKind:
            raise TypeError("document post kind has the wrong type")
        if acknowledgment is not None and not _is_acknowledgment(
            kind,
            acknowledgment,
        ):
            raise ValueError("document acknowledgment token is invalid")
        if self._require_acknowledgment and acknowledgment is None:
            raise ValueError("document acknowledgment token is required")

        complete = _Completion(completion)
        with self._lock:
            document_epoch = self._document_epoch
            closed = self._closed
        if closed:
            complete(DocumentRetiredError("document channel is closed"))
            return
        try:
            encoded = json.dumps(
                payload,
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            # ensure_ascii makes character count the exact UTF-8 byte count and
            # avoids constructing a second full message merely to measure it.
            if len(encoded) > _MAX_DOCUMENT_MESSAGE_BYTES:
                raise DocumentMessageTooLargeError(
                    "document message exceeds the 65536-byte channel ceiling"
                )
        except Exception as error:
            retire_exception_graph(error)
            complete(error)
            return

        if not self._require_acknowledgment:
            self._post_without_acknowledgment(
                encoded,
                still_current,
                complete,
                document_epoch,
            )
            return

        pending = _PendingPost(
            encoded,
            still_current,
            complete,
            kind,
            acknowledgment,
            document_epoch,
        )
        superseded: _PendingPost | None = None
        refused: Exception | None = None
        with self._lock:
            if self._closed:
                refused = DocumentRetiredError("document channel is closed")
                schedule = None
            elif document_epoch is not self._document_epoch:
                refused = DocumentRetiredError(
                    "document was replaced during message construction"
                )
                schedule = None
            elif kind is DocumentPostKind.REPLACEABLE:
                superseded = self._replaceable
                self._replaceable = pending
                schedule = self._claim_dispatch_locked()
            elif self._required is not None or (
                self._in_flight is not None
                and self._in_flight.kind is DocumentPostKind.REQUIRED
            ):
                refused = DocumentChannelBusyError(
                    "a required document post is already outstanding"
                )
                schedule = None
            else:
                self._required = pending
                schedule = self._claim_dispatch_locked()

        if superseded is not None:
            superseded.complete(
                DocumentStaleError("document post was superseded before dispatch")
            )
        if refused is not None:
            complete(refused)
            return
        if schedule is None:
            return
        self._schedule_dispatch(schedule)

    def _post_without_acknowledgment(
        self,
        encoded: str,
        still_current: Callable[[], bool],
        complete: _Completion,
        document_epoch: object,
    ) -> None:
        """Preserve the ordinary independent post path for local consumers."""

        def publish() -> None:
            complete(
                self._post_to_current_document(
                    encoded,
                    still_current,
                    document_epoch,
                )
            )

        try:
            self._invoke(self._native_window, publish)
        except Exception as error:
            retire_exception_graph(error)
            complete(error)

    def acknowledge(
        self,
        kind: DocumentPostKind,
        acknowledgment: _Acknowledgment,
    ) -> bool:
        """Retire one sent post only after its exact browser round trip."""

        if type(kind) is not DocumentPostKind:
            return False
        if not _is_acknowledgment(kind, acknowledgment):
            return False
        with self._lock:
            pending = self._in_flight
            if (
                pending is None
                or pending.kind is not kind
                or type(pending.acknowledgment) is not type(acknowledgment)
                or pending.acknowledgment != acknowledgment
            ):
                return False
            self._in_flight = None
            schedule = self._claim_dispatch_locked()
        pending.complete(None)
        if schedule is not None:
            self._schedule_dispatch(schedule)
        return True

    def replace_document(self) -> None:
        """Retire old-document custody at the synchronous replacement seam."""

        with self._lock:
            if self._closed:
                return
            self._document_epoch = object()
            required = self._required
            replaceable = self._replaceable
            in_flight = self._in_flight
            self._required = None
            self._replaceable = None
            self._in_flight = None
        self._complete_retired((required, replaceable, in_flight))

    def _schedule_dispatch(self, token: object) -> None:
        try:
            self._invoke(
                self._native_window,
                lambda: self._drain(token),
            )
        except Exception as error:
            retire_exception_graph(error)
            self._dispatch_failed(token, error)

    def close(self) -> None:
        """Retire every message still owned by this document channel."""

        with self._lock:
            if self._closed:
                return
            self._closed = True
            required = self._required
            replaceable = self._replaceable
            in_flight = self._in_flight
            self._required = None
            self._replaceable = None
            self._in_flight = None
        self._complete_retired((required, replaceable, in_flight))

    def _claim_dispatch_locked(self) -> object | None:
        if (
            self._scheduled_token is not None
            or self._in_flight is not None
            or (self._required is None and self._replaceable is None)
        ):
            return None
        token = object()
        self._scheduled_token = token
        return token

    def _drain(self, token: object) -> None:
        with self._lock:
            if token is not self._scheduled_token:
                return
            pending = self._required
            if pending is not None:
                self._required = None
            else:
                pending = self._replaceable
                self._replaceable = None
            self._scheduled_token = None
            if pending is None:
                return
            self._in_flight = pending
        self._publish(pending)

    def _publish(self, pending: _PendingPost) -> None:
        failure = self._post_to_current_document(
            pending.encoded,
            pending.still_current,
            pending.document_epoch,
        )
        if failure is not None:
            self._finish_in_flight(pending, failure)
            return
        with self._lock:
            if self._in_flight is pending:
                self._in_flight = _AwaitingAcknowledgment(
                    pending.complete,
                    pending.kind,
                    pending.acknowledgment,
                )

    def _post_to_current_document(
        self,
        encoded: str,
        still_current: Callable[[], bool],
        document_epoch: object,
    ) -> Exception | None:
        try:
            current = still_current()
            if type(current) is not bool:
                raise TypeError("document currency predicate must return bool")
            if not current:
                raise DocumentStaleError(
                    "document was replaced before its message could be posted"
                )
            with self._lock:
                if self._closed or document_epoch is not self._document_epoch:
                    raise DocumentRetiredError(
                        "document was replaced before its message could be posted"
                    )
                core = self._native_window.browser.webview.CoreWebView2
                core.PostWebMessageAsJson(encoded)
        except Exception as error:
            retire_exception_graph(error)
            return error
        return None

    def _finish_in_flight(
        self,
        pending: _PendingPost,
        error: Exception | None,
    ) -> None:
        with self._lock:
            if self._in_flight is not pending:
                return
            self._in_flight = None
            schedule = self._claim_dispatch_locked()
        pending.complete(error)
        if schedule is not None:
            self._schedule_dispatch(schedule)

    def _dispatch_failed(self, token: object, error: Exception) -> None:
        with self._lock:
            if token is not self._scheduled_token:
                return
            self._scheduled_token = None
            required = self._required
            replaceable = self._replaceable
            self._required = None
            self._replaceable = None
        if required is not None:
            required.complete(error)
        if replaceable is not None:
            replaceable.complete(error)

    @staticmethod
    def _complete_retired(posts: tuple[_CompletablePost | None, ...]) -> None:
        for pending in posts:
            if pending is not None:
                pending.complete(
                    DocumentRetiredError(
                        "document was replaced before post acknowledgment"
                    )
                )


@dataclass(frozen=True, slots=True)
class _PendingPost:
    encoded: str
    still_current: Callable[[], bool]
    complete: _Completion
    kind: DocumentPostKind
    acknowledgment: _Acknowledgment | None
    document_epoch: object


@dataclass(frozen=True, slots=True)
class _AwaitingAcknowledgment:
    complete: _Completion
    kind: DocumentPostKind
    acknowledgment: _Acknowledgment | None


_CompletablePost = _PendingPost | _AwaitingAcknowledgment


def _is_acknowledgment(kind: DocumentPostKind, value: object) -> bool:
    if kind is DocumentPostKind.REPLACEABLE:
        return type(value) is int and 0 <= value <= MAX_JAVASCRIPT_SAFE_INTEGER
    return (
        type(value) is tuple
        and len(value) == 2
        and type(value[0]) is int
        and 0 <= value[0] <= MAX_JAVASCRIPT_SAFE_INTEGER
        and type(value[1]) is str
        and len(value[1]) == 32
        and all(character in "0123456789abcdef" for character in value[1])
    )


class _Completion:
    """Make a possibly re-entrant channel completion exactly-once."""

    def __init__(self, callback: Callable[[Exception | None], None]) -> None:
        self._callback: Callable[[Exception | None], None] | None = callback
        self._lock = Lock()
        self._finished = False

    def __call__(self, error: Exception | None) -> None:
        with self._lock:
            if self._finished:
                return
            self._finished = True
            callback = self._callback
            self._callback = None
        if callback is None:
            return
        try:
            callback(error)
        except Exception as callback_error:
            try:
                logging.getLogger("namisync").error(
                    "document_channel.completion_failed exception_type=%s",
                    type(callback_error).__name__,
                )
            finally:
                retire_exception_graph(callback_error)


def _invoke_on_ui(
    native_window: object,
    callback: Callable[[], None],
) -> None:
    if not native_window.InvokeRequired:
        callback()
        return
    from System import Action

    native_window.BeginInvoke(Action(callback))
