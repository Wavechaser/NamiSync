"""Desktop document-readiness state and exact command contexts."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum, StrEnum
from threading import Lock
from typing import Callable


_STARTUP_DEADLINE_SECONDS = 5.0


class DesktopStartupError(RuntimeError):
    """The primary desktop host could not safely open its product window."""


class CommandPhase(StrEnum):
    BOOTSTRAP = "bootstrap"
    OPEN = "open"


@dataclass(frozen=True, slots=True)
class ReadinessContext:
    phase: CommandPhase
    generation: int

    def __post_init__(self) -> None:
        if type(self.phase) is not CommandPhase:
            raise TypeError("command phase must be exact")
        if type(self.generation) is not int or self.generation < 0:
            raise ValueError("command generation must be a nonnegative integer")


class _ReadinessState(Enum):
    STARTING = "starting"
    OPENING = "opening"
    OPEN = "open"
    REFUSED = "refused"
    CLOSING = "closing"
    CANCELED = "canceled"


class DesktopReadinessGate:
    """Open normal commands only after native, shell, and appearance readiness."""

    def __init__(
        self,
        schedule_deadline: Callable[
            [float, Callable[[], None]], Callable[[], None]
        ],
    ) -> None:
        if not callable(schedule_deadline):
            raise TypeError("startup deadline scheduler must be callable")
        self._schedule_deadline = schedule_deadline
        self._lock = Lock()
        self._native_loaded = False
        self._shell_acknowledged = False
        self._publication_requested = False
        self._deadline_started = False
        self._cancel_deadline: Callable[[], None] | None = None
        self._generation = 0
        self._state = _ReadinessState.STARTING
        self._request_publication: (
            Callable[[int, Callable[[Exception | None], None]], None] | None
        ) = None
        self._open_desktop: Callable[[], bool] | None = None
        self._refuse_desktop: Callable[[Exception], None] | None = None

    def is_open(self) -> bool:
        with self._lock:
            return self._state is _ReadinessState.OPEN

    def command_context(self) -> object:
        with self._lock:
            if self._state is _ReadinessState.STARTING:
                phase = CommandPhase.BOOTSTRAP
            elif self._state is _ReadinessState.OPEN:
                phase = CommandPhase.OPEN
            else:
                return None
            return ReadinessContext(
                phase,
                self._generation,
            )

    def begin_generation(self) -> None:
        with self._lock:
            if self._state in {
                _ReadinessState.REFUSED,
                _ReadinessState.CANCELED,
                _ReadinessState.CLOSING,
            }:
                return
            self._generation += 1
            self._state = _ReadinessState.STARTING
            self._native_loaded = False
            self._shell_acknowledged = False
            self._publication_requested = False
            self._deadline_started = False
            cancel = self._cancel_deadline
            self._cancel_deadline = None
        self._cancel_safely(cancel)

    def bind(
        self,
        *,
        request_publication: Callable[
            [int, Callable[[Exception | None], None]], None
        ],
        open_desktop: Callable[[], bool],
        refuse_desktop: Callable[[Exception], None],
    ) -> None:
        if not all(
            callable(callback)
            for callback in (
                request_publication,
                open_desktop,
                refuse_desktop,
            )
        ):
            raise TypeError("startup gate callbacks must be callable")
        with self._lock:
            if self._request_publication is not None:
                raise RuntimeError("startup gate is already bound")
            self._request_publication = request_publication
            self._open_desktop = open_desktop
            self._refuse_desktop = refuse_desktop
            generation = self._generation
        self._advance(generation)

    def acknowledge_shell(self, generation: int) -> None:
        with self._lock:
            if (
                type(generation) is not int
                or generation != self._generation
                or self._state is not _ReadinessState.STARTING
            ):
                return
            self._shell_acknowledged = True
            generation = self._generation
        self._advance(generation)

    def native_loaded(self) -> None:
        with self._lock:
            if self._state is not _ReadinessState.STARTING:
                return
            generation = self._generation
            self._native_loaded = True
            schedule = not self._deadline_started
            self._deadline_started = True
        if schedule:
            try:
                cancel = self._schedule_deadline(
                    _STARTUP_DEADLINE_SECONDS,
                    lambda: self._deadline_expired(generation),
                )
                if not callable(cancel):
                    raise TypeError("startup deadline cancel handle must be callable")
            except Exception:
                self._refuse_generation(
                    generation,
                    DesktopStartupError(
                        "NamiSync could not establish its startup deadline"
                    ),
                )
                return
            cancel_now = False
            with self._lock:
                if (
                    self._generation == generation
                    and self._state is _ReadinessState.STARTING
                ):
                    self._cancel_deadline = cancel
                else:
                    cancel_now = True
            if cancel_now:
                self._cancel_safely(cancel)
        self._advance(generation)

    def appearance_published(self, error: Exception | None) -> None:
        with self._lock:
            generation = self._generation
        self._appearance_published(generation, error)

    def _appearance_published(
        self,
        generation: int,
        error: Exception | None,
    ) -> None:
        if error is not None:
            self._refuse_generation(
                generation,
                DesktopStartupError(
                    "NamiSync could not publish its initial appearance"
                ),
            )
            return
        with self._lock:
            if (
                generation != self._generation
                or self._state is not _ReadinessState.STARTING
                or not self._publication_requested
            ):
                return
            open_desktop = self._open_desktop
            self._state = _ReadinessState.OPENING
            open_error: Exception | None = None
            refuse_desktop: Callable[[Exception], None] | None = None
            try:
                if open_desktop is None:
                    raise RuntimeError("startup gate has no open callback")
                opened = open_desktop()
                if type(opened) is not bool:
                    raise TypeError("startup open callback must return Boolean")
            except Exception as error:
                self._state = _ReadinessState.REFUSED
                refuse_desktop = self._refuse_desktop
                open_error = error
            else:
                self._state = (
                    _ReadinessState.OPEN
                    if opened
                    else _ReadinessState.CLOSING
                )
            cancel = self._cancel_deadline
            self._cancel_deadline = None
        self._cancel_safely(cancel)
        if open_error is not None and refuse_desktop is not None:
            refuse_desktop(open_error)

    def refuse(self, error: Exception) -> None:
        with self._lock:
            generation = self._generation
        self._refuse_generation(generation, error)

    def _refuse_generation(self, generation: int, error: Exception) -> None:
        with self._lock:
            if (
                generation != self._generation
                or self._state
                not in {_ReadinessState.STARTING, _ReadinessState.OPENING}
            ):
                return
            self._state = _ReadinessState.REFUSED
            cancel = self._cancel_deadline
            self._cancel_deadline = None
            refuse_desktop = self._refuse_desktop
        self._cancel_safely(cancel)
        if refuse_desktop is not None:
            refuse_desktop(error)

    def cancel(self) -> None:
        with self._lock:
            if self._state not in {
                _ReadinessState.REFUSED,
                _ReadinessState.CLOSING,
            }:
                self._state = _ReadinessState.CANCELED
            cancel = self._cancel_deadline
            self._cancel_deadline = None
        self._cancel_safely(cancel)

    def _advance(self, generation: int) -> None:
        with self._lock:
            if (
                generation != self._generation
                or self._state is not _ReadinessState.STARTING
                or self._publication_requested
                or not self._native_loaded
                or not self._shell_acknowledged
                or self._request_publication is None
            ):
                return
            self._publication_requested = True
            request_publication = self._request_publication
        try:
            request_publication(
                generation,
                lambda error: self._appearance_published(generation, error),
            )
        except Exception as error:
            self._refuse_generation(generation, error)

    def _deadline_expired(self, generation: int) -> None:
        self._refuse_generation(
            generation,
            DesktopStartupError(
                "NamiSync shell did not become ready before the startup deadline"
            ),
        )

    @staticmethod
    def _cancel_safely(cancel: Callable[[], None] | None) -> None:
        if cancel is None:
            return
        try:
            cancel()
        except Exception as error:
            logging.getLogger("namisync").error(
                "%s exception_type=%s",
                "startup.deadline_cancel_failed",
                type(error).__name__,
                exc_info=(type(error), error, error.__traceback__),
            )
