"""Desktop document-readiness state and exact command contexts."""

from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass
from enum import Enum, StrEnum
from threading import Lock
from typing import Callable


_STARTUP_DEADLINE_SECONDS = 5.0
_CHALLENGE_HEX_LENGTH = 32


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
    """Join native, shell, safe-surface, and bilateral document readiness."""

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
        self._generation = 0
        self._state = _ReadinessState.STARTING
        self._native_loaded = False
        self._shell_acknowledged = False
        self._surface_requested = False
        self._surface_settled = False
        self._challenge: str | None = None
        self._post_requested = False
        self._post_completed = False
        self._echo_seen = False
        self._deadline_started = False
        self._cancel_deadline: Callable[[], None] | None = None
        self._request_surface_settlement: (
            Callable[[Callable[[Exception | None], None]], None] | None
        ) = None
        self._request_challenge_post: (
            Callable[
                [int, str, Callable[[Exception | None], None]],
                None,
            ]
            | None
        ) = None
        self._open_desktop: Callable[[int], bool] | None = None
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
            return ReadinessContext(phase, self._generation)

    def recognizes_echo(self, generation: int, challenge: str) -> bool:
        """Return whether an echo still names this generation's challenge."""

        with self._lock:
            return (
                type(generation) is int
                and generation == self._generation
                and type(challenge) is str
                and challenge == self._challenge
                and self._state
                in {
                    _ReadinessState.STARTING,
                    _ReadinessState.OPENING,
                    _ReadinessState.OPEN,
                }
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
            self._surface_requested = False
            self._surface_settled = False
            self._challenge = None
            self._post_requested = False
            self._post_completed = False
            self._echo_seen = False
            self._deadline_started = False
            cancel = self._cancel_deadline
            self._cancel_deadline = None
        self._cancel_safely(cancel)

    def bind(
        self,
        *,
        request_surface_settlement: Callable[
            [Callable[[Exception | None], None]], None
        ],
        request_challenge_post: Callable[
            [int, str, Callable[[Exception | None], None]], None
        ],
        open_desktop: Callable[[int], bool],
        refuse_desktop: Callable[[Exception], None],
    ) -> None:
        if not all(
            callable(callback)
            for callback in (
                request_surface_settlement,
                request_challenge_post,
                open_desktop,
                refuse_desktop,
            )
        ):
            raise TypeError("readiness gate callbacks must be callable")
        with self._lock:
            if self._request_surface_settlement is not None:
                raise RuntimeError("readiness gate is already bound")
            self._request_surface_settlement = request_surface_settlement
            self._request_challenge_post = request_challenge_post
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

    def acknowledge_echo(self, generation: int, challenge: str) -> bool:
        """Join an exact echo; invalid, stale, or premature echoes return false."""

        with self._lock:
            if (
                type(generation) is not int
                or generation != self._generation
                or type(challenge) is not str
                or challenge != self._challenge
                or self._state
                not in {
                    _ReadinessState.STARTING,
                    _ReadinessState.OPENING,
                    _ReadinessState.OPEN,
                }
            ):
                return False
            if self._state is _ReadinessState.OPEN:
                return True
            self._echo_seen = True
            generation = self._generation
        return self._attempt_open(generation)

    def native_loaded(self) -> None:
        with self._lock:
            if self._state is not _ReadinessState.STARTING:
                return
            generation = self._generation
            self._native_loaded = True
            schedule = not self._deadline_started
            self._deadline_started = True
        if schedule:
            self._start_deadline(generation)
        self._advance(generation)

    def refuse(self, error: Exception) -> None:
        with self._lock:
            generation = self._generation
        self._refuse_generation(generation, error)

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

    def _start_deadline(self, generation: int) -> None:
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
        with self._lock:
            if (
                self._generation == generation
                and self._state is _ReadinessState.STARTING
            ):
                self._cancel_deadline = cancel
                cancel_now = False
            else:
                cancel_now = True
        if cancel_now:
            self._cancel_safely(cancel)

    def _advance(self, generation: int) -> None:
        with self._lock:
            if (
                generation != self._generation
                or self._state is not _ReadinessState.STARTING
                or self._surface_requested
                or not self._native_loaded
                or not self._shell_acknowledged
                or self._request_surface_settlement is None
            ):
                return
            self._surface_requested = True
            request = self._request_surface_settlement
        try:
            request(lambda error: self._surface_settled_result(generation, error))
        except Exception:
            self._refuse_generation(
                generation,
                DesktopStartupError(
                    "NamiSync could not verify its initial window surface"
                ),
            )

    def _surface_settled_result(
        self,
        generation: int,
        error: Exception | None,
    ) -> None:
        if error is not None:
            self._refuse_generation(generation, error)
            return
        try:
            challenge = secrets.token_hex(_CHALLENGE_HEX_LENGTH // 2)
        except Exception:
            self._refuse_generation(
                generation,
                DesktopStartupError(
                    "NamiSync could not create its document challenge"
                ),
            )
            return
        if (
            type(challenge) is not str
            or len(challenge) != _CHALLENGE_HEX_LENGTH
            or any(character not in "0123456789abcdef" for character in challenge)
        ):
            self._refuse_generation(
                generation,
                DesktopStartupError(
                    "NamiSync could not create its document challenge"
                ),
            )
            return
        with self._lock:
            if (
                generation != self._generation
                or self._state is not _ReadinessState.STARTING
                or not self._surface_requested
                or self._surface_settled
            ):
                return
            self._surface_settled = True
            self._challenge = challenge
            self._post_requested = True
            request = self._request_challenge_post
        if request is None:
            self._refuse_generation(
                generation,
                DesktopStartupError("NamiSync document channel is unavailable"),
            )
            return
        try:
            request(
                generation,
                challenge,
                lambda post_error: self._challenge_posted(
                    generation,
                    challenge,
                    post_error,
                ),
            )
        except Exception as error:
            self._log_callback_failure("readiness.challenge_request_failed", error)
            self._refuse_generation(
                generation,
                DesktopStartupError(
                    "NamiSync could not post its document challenge"
                ),
            )

    def _challenge_posted(
        self,
        generation: int,
        challenge: str,
        error: Exception | None,
    ) -> None:
        if error is not None:
            self._log_callback_failure("readiness.challenge_post_failed", error)
            self._refuse_generation(
                generation,
                DesktopStartupError(
                    "NamiSync could not post its document challenge"
                ),
            )
            return
        with self._lock:
            if (
                generation != self._generation
                or challenge != self._challenge
                or self._state is not _ReadinessState.STARTING
                or not self._post_requested
                or self._post_completed
            ):
                return
            self._post_completed = True
        self._attempt_open(generation)

    def _attempt_open(self, generation: int) -> bool:
        with self._lock:
            if generation != self._generation:
                return False
            if self._state is _ReadinessState.OPEN:
                return True
            if (
                self._state is not _ReadinessState.STARTING
                or not self._surface_settled
                or not self._post_completed
                or not self._echo_seen
            ):
                return False
            self._state = _ReadinessState.OPENING
            open_desktop = self._open_desktop
        try:
            if open_desktop is None:
                raise RuntimeError("readiness gate has no open callback")
            opened = open_desktop(generation)
            if type(opened) is not bool:
                raise TypeError("startup open callback must return Boolean")
        except Exception as error:
            with self._lock:
                if (
                    generation == self._generation
                    and self._state is _ReadinessState.OPENING
                ):
                    self._state = _ReadinessState.REFUSED
                    cancel = self._cancel_deadline
                    self._cancel_deadline = None
                    refuse = self._refuse_desktop
                else:
                    cancel = None
                    refuse = None
            self._cancel_safely(cancel)
            if refuse is not None:
                refuse(error)
            return False
        with self._lock:
            if (
                generation == self._generation
                and self._state is _ReadinessState.OPENING
            ):
                self._state = (
                    _ReadinessState.OPEN if opened else _ReadinessState.CLOSING
                )
                cancel = self._cancel_deadline
                self._cancel_deadline = None
                result = self._state is _ReadinessState.OPEN
            else:
                cancel = None
                result = False
        self._cancel_safely(cancel)
        return result

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

    @staticmethod
    def _log_callback_failure(event: str, error: Exception) -> None:
        logging.getLogger("namisync").error(
            "%s exception_type=%s",
            event,
            type(error).__name__,
        )
