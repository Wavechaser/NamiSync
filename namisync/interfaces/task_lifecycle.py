"""Private application ownership for task and session lifecycle effects."""

from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass
from hashlib import sha256
import re
from threading import Condition, Lock
from typing import Literal
from uuid import uuid4


TASK_EFFECT_CAPACITY = 48
_OPAQUE_ID = re.compile(r"[0-9a-f]{32}")
_ANY_TASK = object()


class LifecycleReceiptConflictError(ValueError):
    """A lifecycle command id was reused for a different effect."""


class LifecycleAssociationError(LookupError):
    """A session or task does not name one live application association."""


class LifecycleTaskCapacityError(RuntimeError):
    """The bounded application task-effect set is full."""


@dataclass(frozen=True, slots=True)
class StartReceipt:
    kind: str
    signature: tuple[object, ...]
    request_id: str
    session_id: str
    task_id: str | None


@dataclass(frozen=True, slots=True)
class TaskStartClaim:
    task_id: str
    replay: StartReceipt | None
    attached_shell: bool = False


@dataclass(frozen=True, slots=True)
class TaskShellClaim:
    task_id: str
    replay: bool


@dataclass(frozen=True, slots=True)
class AdmissionToken:
    identity: int


@dataclass(frozen=True, slots=True)
class AssociationToken:
    session_id: str
    identity: int


@dataclass(frozen=True, slots=True)
class PlanToken:
    request_id: str
    identity: int


@dataclass(frozen=True, slots=True)
class PlanMutationClaim:
    token: PlanToken
    claim_id: int
    replay: bool
    command_id: str | None
    signature: tuple[object, ...]


@dataclass(frozen=True, slots=True)
class PlanRetirementClaim:
    token: PlanToken
    claim_id: int


@dataclass(frozen=True, slots=True)
class ObservationClaim:
    token: AssociationToken
    claim_id: int


@dataclass(frozen=True, slots=True)
class SettlementClaim:
    token: AssociationToken
    claim_id: int
    close_task: bool


@dataclass(frozen=True, slots=True)
class AdmissionRollbackClaim:
    token: AdmissionToken
    claim_id: int
    session_id: str | None
    detail_owner: tuple[str, str] | None


@dataclass(frozen=True, slots=True)
class SettlementWork:
    claim: SettlementClaim
    session_id: str
    detail_owner: tuple[str, str] | None
    plan_token: PlanToken | None
    replay: bool


@dataclass(slots=True)
class _TaskEffect:
    task_id: str
    command_id: str
    signature: tuple[object, ...]
    session_id: str | None = None
    admission_identity: int | None = None
    start_failed: bool = False
    shell_published: bool = False
    start_command_id: str | None = None
    start_signature: tuple[object, ...] | None = None
    start_kind: str | None = None


@dataclass(slots=True)
class _PlanEffect:
    identity: int
    request_id: str
    session_id: str
    mutation_receipts: dict[str, tuple[object, ...]]
    mutation_claim: PlanMutationClaim | None = None
    retirement_claim: PlanRetirementClaim | None = None


@dataclass(slots=True)
class _SessionAssociation:
    identity: int
    kind: str
    command_id: str | None
    signature: tuple[object, ...]
    task_id: str | None
    session_id: str | None
    detail_owner: tuple[str, str] | None = None
    rollback_claim: AdmissionRollbackClaim | None = None
    observation_claim: ObservationClaim | None = None
    request_id: str | None = None
    plan_token: PlanToken | None = None
    terminal_digest: bytes | None = None
    settlement_target: Literal["session", "task"] | None = None
    session_released: bool = False
    settlement_claim: SettlementClaim | None = None


class TaskLifecycle:
    """Own receipts, exact association, and logical lifecycle settlement.

    This aggregate never calls an adapter, observer, dispatcher, or runtime.
    Callers perform retry-safe physical cleanup outside the condition.
    """

    def __init__(
        self,
        *,
        task_capacity: int = TASK_EFFECT_CAPACITY,
    ) -> None:
        if isinstance(task_capacity, bool) or type(task_capacity) is not int:
            raise TypeError("task capacity must be an integer")
        if task_capacity <= 0 or task_capacity > TASK_EFFECT_CAPACITY:
            raise ValueError(
                f"task capacity must be between 1 and {TASK_EFFECT_CAPACITY}"
            )
        self._task_capacity = task_capacity
        self._condition = Condition(Lock())
        self._command_locks = tuple(Lock() for _ in range(64))
        self._start_receipts: dict[str, StartReceipt] = {}
        self._plans: dict[str, _PlanEffect] = {}
        self._admissions: dict[int, _SessionAssociation] = {}
        self._sessions: dict[str, _SessionAssociation] = {}
        self._tasks: dict[str, _TaskEffect] = {}
        self._next_identity = 0
        self._next_claim_id = 0
        self._closed = False

    def command_guard(self, command_id: str | None):
        self._require_open()
        if command_id is None:
            return nullcontext()
        self._require_command_id(command_id)
        digest = sha256(
            command_id.encode("utf-8", errors="surrogatepass")
        ).digest()
        return self._command_locks[
            int.from_bytes(digest[:2], "big") % len(self._command_locks)
        ]

    def _require_open(self) -> None:
        with self._condition:
            if self._closed:
                raise RuntimeError("service is closed")

    def replay_start(
        self,
        command_id: str | None,
        kind: str,
        signature: tuple[object, ...],
    ) -> StartReceipt | None:
        self._require_signature(signature)
        if command_id is None:
            return None
        self._require_command_id(command_id)
        with self._condition:
            while True:
                if self._closed:
                    raise RuntimeError("service is closed")
                receipt = self._start_receipts.get(command_id)
                if receipt is None:
                    return None
                if receipt.kind != kind or receipt.signature != signature:
                    raise LifecycleReceiptConflictError(
                        "command_id was reused for a different command"
                    )
                association = self._sessions.get(receipt.session_id)
                if association is None:
                    self._start_receipts.pop(command_id, None)
                    return None
                if (
                    association.command_id != command_id
                    or association.request_id != receipt.request_id
                    or association.task_id != receipt.task_id
                ):
                    raise RuntimeError(
                        "start receipt belongs to another association"
                    )
                settlement = association.settlement_claim
                blocks_replay = (
                    receipt.task_id is None
                    and (
                        settlement is not None
                        or association.settlement_target is not None
                    )
                ) or (
                    receipt.task_id is not None
                    and (
                        (
                            settlement is not None
                            and settlement.close_task
                        )
                        or association.settlement_target == "task"
                    )
                )
                if not blocks_replay:
                    return receipt
                if settlement is None:
                    raise LifecycleAssociationError(
                        "session settlement remains pending"
                    )
                self._condition.wait()

    def begin_task_start(
        self,
        command_id: str,
        signature: tuple[object, ...],
    ) -> TaskStartClaim:
        self._require_command_id(command_id)
        replay = self.replay_start(command_id, "task-plan", signature)
        if replay is not None:
            if replay.task_id is None:
                raise LifecycleReceiptConflictError(
                    "task command replay has no task identity"
                )
            return TaskStartClaim(replay.task_id, replay)
        with self._condition:
            if self._closed:
                raise RuntimeError("service is closed")
            if any(
                task.command_id == command_id for task in self._tasks.values()
            ):
                raise LifecycleTaskCapacityError(
                    "task start cleanup remains pending"
                )
            if len(self._tasks) >= self._task_capacity:
                raise LifecycleTaskCapacityError("task capacity is exhausted")
            task_id = self._mint_task_id_locked()
            self._tasks[task_id] = _TaskEffect(
                task_id,
                command_id,
                signature,
                start_command_id=command_id,
                start_signature=signature,
                start_kind="task-plan",
            )
            return TaskStartClaim(task_id, None)

    def begin_task_shell_start(
        self,
        task_id: str,
        command_id: str,
        kind: str,
        signature: tuple[object, ...],
    ) -> TaskStartClaim:
        """Atomically claim the first session of one published blank task."""

        self._require_command_id(command_id)
        self._require_signature(signature)
        if type(kind) is not str or not kind:
            raise ValueError("task start kind must be a nonempty string")
        replay = self.replay_start(command_id, kind, signature)
        if replay is not None:
            if replay.task_id != task_id:
                raise LifecycleReceiptConflictError(
                    "task command replay belongs to another task"
                )
            return TaskStartClaim(task_id, replay, True)
        with self._condition:
            if self._closed:
                raise RuntimeError("service is closed")
            if any(
                task.start_command_id == command_id
                for task in self._tasks.values()
            ):
                raise LifecycleReceiptConflictError(
                    "command_id was reused for a different task start"
                )
            task = self._tasks.get(task_id)
            if (
                task is None
                or task.signature != ("task-shell",)
                or not task.shell_published
                or task.session_id is not None
                or task.admission_identity is not None
                or task.start_command_id is not None
            ):
                raise LifecycleAssociationError("task shell is unavailable")
            task.start_command_id = command_id
            task.start_signature = signature
            task.start_kind = kind
            task.start_failed = False
            return TaskStartClaim(task_id, None, True)

    def abort_task_start(self, task_id: str) -> None:
        with self._condition:
            task = self._tasks.get(task_id)
            if task is None:
                return
            task.start_failed = True
            if task.session_id is None and task.admission_identity is None:
                self._finish_failed_task_start_locked(task)
            self._condition.notify_all()

    def begin_task_shell(self, command_id: str) -> TaskShellClaim:
        """Reserve or replay one process-live task without domain work."""

        self._require_command_id(command_id)
        signature = ("task-shell",)
        with self._condition:
            if self._closed:
                raise RuntimeError("service is closed")
            if command_id in self._start_receipts:
                raise LifecycleReceiptConflictError(
                    "command_id was reused for a different command"
                )
            for task in self._tasks.values():
                if task.command_id != command_id:
                    continue
                if task.signature != signature or not task.shell_published:
                    raise LifecycleReceiptConflictError(
                        "command_id was reused for a different command"
                    )
                if task.session_id is not None or task.admission_identity is not None:
                    raise LifecycleAssociationError("task shell is unavailable")
                return TaskShellClaim(task.task_id, True)
            if len(self._tasks) >= self._task_capacity:
                raise LifecycleTaskCapacityError("task capacity is exhausted")
            task_id = self._mint_task_id_locked()
            self._tasks[task_id] = _TaskEffect(
                task_id,
                command_id,
                signature,
            )
            return TaskShellClaim(task_id, False)

    def complete_task_shell(self, claim: TaskShellClaim) -> None:
        if claim.replay:
            return
        with self._condition:
            task = self._tasks.get(claim.task_id)
            if (
                task is None
                or task.signature != ("task-shell",)
                or task.shell_published
                or task.session_id is not None
                or task.admission_identity is not None
                or task.start_command_id is not None
            ):
                raise LifecycleAssociationError("task shell claim is stale")
            task.shell_published = True
            self._condition.notify_all()

    def abort_task_shell(self, claim: TaskShellClaim) -> None:
        if claim.replay:
            return
        with self._condition:
            task = self._tasks.get(claim.task_id)
            if (
                task is not None
                and task.signature == ("task-shell",)
                and not task.shell_published
                and task.session_id is None
                and task.admission_identity is None
            ):
                self._tasks.pop(claim.task_id, None)
                self._condition.notify_all()

    def close_task_shell(self, task_id: str) -> None:
        """Retire one exact published task that never owned a session."""

        if type(task_id) is not str or re.fullmatch(r"task-[0-9a-f]{32}", task_id) is None:
            raise LifecycleAssociationError("task shell is unavailable")
        with self._condition:
            if self._closed:
                raise LifecycleAssociationError("task shell is unavailable")
            task = self._tasks.get(task_id)
            if (
                task is None
                or task.signature != ("task-shell",)
                or not task.shell_published
                or task.session_id is not None
                or task.admission_identity is not None
                or task.start_command_id is not None
            ):
                raise LifecycleAssociationError("task shell is unavailable")
            self._tasks.pop(task_id, None)
            self._condition.notify_all()

    def require_plan(self, request_id: str) -> PlanToken:
        """Return the token installed by an admitted plan start."""

        self._require_opaque_id(request_id, "plan request id")
        with self._condition:
            if self._closed:
                raise RuntimeError("service is closed")
            plan = self._plans.get(request_id)
            if plan is None:
                raise LifecycleAssociationError("plan token is retired")
            identity = plan.identity
            while plan.retirement_claim is not None:
                self._condition.wait()
                if self._closed:
                    raise RuntimeError("service is closed")
                plan = self._plans.get(request_id)
                if plan is None or plan.identity != identity:
                    raise LifecycleAssociationError("plan token is retired")
            return self._plan_token(plan)

    def begin_plan_mutation(
        self,
        token: PlanToken,
        command_id: str | None,
        signature: tuple[object, ...],
    ) -> PlanMutationClaim:
        self._require_signature(signature)
        if command_id is not None:
            self._require_command_id(command_id)
        with self._condition:
            if self._closed:
                raise RuntimeError("service is closed")
            plan = self._plan_locked(token)
            while (
                plan.retirement_claim is not None
                or plan.mutation_claim is not None
            ):
                self._condition.wait()
                if self._closed:
                    raise RuntimeError("service is closed")
                plan = self._plan_locked(token)
            if command_id is not None:
                prior = plan.mutation_receipts.get(command_id)
                if prior is not None:
                    if prior != signature:
                        raise LifecycleReceiptConflictError(
                            "command_id was reused for a different "
                            "selection mutation"
                        )
                    return PlanMutationClaim(
                        token,
                        0,
                        True,
                        command_id,
                        signature,
                    )
            claim = PlanMutationClaim(
                token,
                self._mint_claim_id_locked(),
                False,
                command_id,
                signature,
            )
            plan.mutation_claim = claim
            return claim

    def complete_plan_mutation(self, claim: PlanMutationClaim) -> None:
        if claim.replay:
            raise RuntimeError("replayed mutation has no effect claim")
        with self._condition:
            plan = self._plan_mutation_claim_locked(claim)
            if claim.command_id is not None:
                prior = plan.mutation_receipts.get(claim.command_id)
                if prior is not None and prior != claim.signature:
                    raise LifecycleReceiptConflictError(
                        "command_id raced with a different selection mutation"
                    )
                plan.mutation_receipts[claim.command_id] = claim.signature
            plan.mutation_claim = None
            self._condition.notify_all()

    def abandon_plan_mutation(self, claim: PlanMutationClaim) -> None:
        if claim.replay:
            return
        with self._condition:
            plan = self._plans.get(claim.token.request_id)
            if (
                plan is None
                or plan.identity != claim.token.identity
                or plan.mutation_claim != claim
            ):
                return
            plan.mutation_claim = None
            self._condition.notify_all()

    def begin_plan_retirement(
        self,
        token: PlanToken,
    ) -> PlanRetirementClaim | None:
        """Reserve the exact plan, or report that its token is retired."""

        with self._condition:
            if self._closed:
                raise RuntimeError("service is closed")
            plan = self._plans.get(token.request_id)
            while (
                plan is not None
                and plan.identity == token.identity
                and plan.retirement_claim is not None
            ):
                self._condition.wait()
                if self._closed:
                    raise RuntimeError("service is closed")
                plan = self._plans.get(token.request_id)
            if plan is None or plan.identity != token.identity:
                return None
            return self._reserve_plan_retirement_locked(plan)

    def complete_plan_retirement(self, claim: PlanRetirementClaim) -> None:
        with self._condition:
            plan = self._plans.get(claim.token.request_id)
            if plan is None:
                return
            self._validate_plan_retirement_locked(plan, claim)
            self._plans.pop(claim.token.request_id, None)
            self._condition.notify_all()

    def abandon_plan_retirement(self, claim: PlanRetirementClaim) -> None:
        with self._condition:
            plan = self._plans.get(claim.token.request_id)
            if (
                plan is None
                or plan.identity != claim.token.identity
                or plan.retirement_claim != claim
            ):
                return
            plan.retirement_claim = None
            self._condition.notify_all()

    def begin_admission(
        self,
        kind: str,
        command_id: str | None,
        signature: tuple[object, ...],
        *,
        task_id: str | None = None,
        detail_owner: tuple[str, str] | None = None,
    ) -> AdmissionToken:
        if type(kind) is not str or not kind:
            raise ValueError("effect kind must be a nonempty string")
        if command_id is not None:
            self._require_command_id(command_id)
        self._require_signature(signature)
        if detail_owner is not None and (
            type(detail_owner) is not tuple
            or len(detail_owner) != 2
            or any(type(part) is not str for part in detail_owner)
        ):
            raise TypeError("detail owner must be an exact string pair")
        with self._condition:
            if self._closed:
                raise RuntimeError("service is closed")
            if task_id is not None:
                task = self._tasks.get(task_id)
                if (
                    task is None
                    or task.session_id is not None
                    or task.admission_identity is not None
                ):
                    raise LifecycleAssociationError(
                        "task is unavailable for admission"
                    )
                if (
                    task.start_command_id != command_id
                    or task.start_signature != signature
                    or task.start_kind != kind
                ):
                    raise LifecycleReceiptConflictError(
                        "task admission does not match its effect"
                    )
            self._next_identity += 1
            admission = _SessionAssociation(
                self._next_identity,
                kind,
                command_id,
                signature,
                task_id,
                None,
                detail_owner,
            )
            self._admissions[admission.identity] = admission
            if task_id is not None:
                task.admission_identity = admission.identity
            return AdmissionToken(admission.identity)

    def attach_session(
        self,
        token: AdmissionToken,
        session_id: str,
    ) -> AssociationToken:
        self._require_opaque_id(session_id, "session id")
        with self._condition:
            if self._closed:
                raise RuntimeError("service is closed")
            admission = self._admission_locked(token)
            if admission.rollback_claim is not None:
                raise LifecycleAssociationError("admission rollback is pending")
            if admission.session_id is not None:
                if admission.session_id == session_id:
                    return self._association_token(admission)
                raise RuntimeError("admission already has a session")
            if session_id in self._sessions:
                raise RuntimeError("dispatcher reused a session id")
            task = self._task_for_admission_locked(admission)
            admission.session_id = session_id
            if task is not None:
                task.session_id = session_id
            self._sessions[session_id] = admission
            return self._association_token(admission)

    def publish_start(
        self,
        token: AdmissionToken,
        session_id: str,
        request_id: str,
    ) -> tuple[AssociationToken, StartReceipt]:
        self._require_opaque_id(session_id, "session id")
        self._require_opaque_id(request_id, "request id")
        with self._condition:
            admission = self._admissions.get(token.identity)
            if admission is None:
                association = self._sessions.get(session_id)
                if (
                    association is not None
                    and association.identity == token.identity
                    and association.request_id == request_id
                ):
                    receipt = StartReceipt(
                        association.kind,
                        association.signature,
                        request_id,
                        session_id,
                        association.task_id,
                    )
                    if association.command_id is not None:
                        if self._start_receipts.get(
                            association.command_id
                        ) != receipt:
                            raise LifecycleAssociationError(
                                "published start receipt is unavailable"
                            )
                    return self._association_token(association), receipt
                raise LifecycleAssociationError("admission token is retired")
            if admission.rollback_claim is not None:
                raise LifecycleAssociationError("admission rollback is pending")
            if admission.session_id != session_id:
                raise LifecycleAssociationError(
                    "dispatcher published another admission session"
                )
            if self._closed:
                task = self._task_for_association_locked(admission)
                if task is not None:
                    task.start_failed = True
                raise RuntimeError("service is closed")
            receipt = StartReceipt(
                admission.kind,
                admission.signature,
                request_id,
                session_id,
                admission.task_id,
            )
            if admission.command_id is not None:
                existing = self._start_receipts.get(admission.command_id)
                if existing is not None and existing != receipt:
                    raise LifecycleReceiptConflictError(
                        "command_id raced with a different admitted session"
                    )
            task = self._task_for_association_locked(admission)
            if admission.kind in {"plan", "task-plan"}:
                # Plan request IDs are minted fresh by the service. Another
                # session under this ID is a collision, not a retirement
                # waiter or a reusable key.
                plan = self._plans.get(request_id)
                if plan is None:
                    self._next_identity += 1
                    plan = _PlanEffect(
                        self._next_identity,
                        request_id,
                        session_id,
                        {},
                    )
                    self._plans[request_id] = plan
                elif plan.session_id != session_id:
                    raise RuntimeError("plan request id was reused")
                admission.plan_token = self._plan_token(plan)
            admission.request_id = request_id
            if admission.command_id is not None:
                self._start_receipts[admission.command_id] = receipt
            if task is not None:
                task.admission_identity = None
            self._admissions.pop(admission.identity, None)
            self._condition.notify_all()
            return self._association_token(admission), receipt

    def begin_admission_rollback(
        self,
        token: AdmissionToken,
    ) -> AdmissionRollbackClaim | None:
        with self._condition:
            admission = self._admissions.get(token.identity)
            while admission is not None and admission.rollback_claim is not None:
                self._condition.wait()
                if self._closed:
                    raise RuntimeError("service is closed")
                admission = self._admissions.get(token.identity)
            if admission is None:
                return None
            claim = AdmissionRollbackClaim(
                token,
                self._mint_claim_id_locked(),
                admission.session_id,
                admission.detail_owner,
            )
            admission.rollback_claim = claim
            return claim

    def complete_admission_rollback(
        self,
        claim: AdmissionRollbackClaim,
    ) -> None:
        with self._condition:
            admission = self._admissions.get(claim.token.identity)
            if admission is None:
                return
            admission = self._admission_rollback_claim_locked(claim)
            if admission.session_id is not None:
                self._retire_unpublished_association_locked(admission)
            self._retire_admission_locked(admission)
            self._condition.notify_all()

    def abandon_admission_rollback(
        self,
        claim: AdmissionRollbackClaim,
    ) -> None:
        with self._condition:
            admission = self._admissions.get(claim.token.identity)
            if (
                admission is None
                or admission.rollback_claim != claim
            ):
                return
            admission.rollback_claim = None
            self._condition.notify_all()

    def require_session(
        self,
        session_id: str,
        *,
        task_id: str | None | object = _ANY_TASK,
        live: bool = True,
    ) -> AssociationToken:
        with self._condition:
            if self._closed and live:
                raise LifecycleAssociationError("session is unavailable")
            association = self._sessions.get(session_id)
            self._validate_association_locked(
                association,
                task_id=task_id,
                require_live=live,
            )
            assert association is not None
            return self._association_token(association)

    def begin_observation(
        self,
        session_id: str,
        *,
        task_id: str | None | object = _ANY_TASK,
    ) -> ObservationClaim:
        with self._condition:
            if self._closed:
                raise LifecycleAssociationError("session is unavailable")
            association = self._sessions.get(session_id)
            self._validate_association_locked(
                association,
                task_id=task_id,
                require_live=True,
            )
            assert association is not None
            identity = association.identity
            while association.observation_claim is not None:
                self._condition.wait()
                if self._closed:
                    raise LifecycleAssociationError("session is unavailable")
                association = self._sessions.get(session_id)
                if association is None or association.identity != identity:
                    raise LifecycleAssociationError("session is unavailable")
                self._validate_association_locked(
                    association,
                    task_id=task_id,
                    require_live=True,
                )
                if association.settlement_claim is not None:
                    raise LifecycleAssociationError("session is retired")
            if association.settlement_claim is not None:
                raise LifecycleAssociationError("session is retired")
            claim_id = self._mint_claim_id_locked()
            claim = ObservationClaim(
                self._association_token(association),
                claim_id,
            )
            association.observation_claim = claim
            return claim

    def end_observation(self, claim: ObservationClaim) -> None:
        with self._condition:
            association = self._sessions.get(claim.token.session_id)
            if (
                association is None
                or association.identity != claim.token.identity
                or association.observation_claim != claim
            ):
                return
            association.observation_claim = None
            self._condition.notify_all()

    def begin_settlement(
        self,
        session_id: str,
        *,
        task_id: str | None | object = _ANY_TASK,
        close_task: bool,
    ) -> SettlementClaim:
        if type(close_task) is not bool:
            raise TypeError("close_task must be a bool")
        with self._condition:
            if self._closed:
                raise LifecycleAssociationError("session is unavailable")
            association = self._sessions.get(session_id)
            self._validate_association_locked(
                association,
                task_id=task_id,
                require_live=False,
            )
            assert association is not None
            identity = association.identity
            while association.settlement_claim is not None:
                self._condition.wait()
                if self._closed:
                    raise LifecycleAssociationError("session is unavailable")
                association = self._sessions.get(session_id)
                if association is None or association.identity != identity:
                    raise LifecycleAssociationError("session is unavailable")
                self._validate_association_locked(
                    association,
                    task_id=task_id,
                    require_live=False,
                )
            if close_task and association.task_id is None:
                raise LifecycleAssociationError("direct session has no task")
            if not close_task and association.settlement_target == "task":
                raise LifecycleAssociationError("task close remains pending")
            claim = SettlementClaim(
                self._association_token(association),
                self._mint_claim_id_locked(),
                close_task,
            )
            association.settlement_claim = claim
            try:
                while association.observation_claim is not None:
                    self._condition.wait()
                    if self._closed:
                        raise LifecycleAssociationError(
                            "session is unavailable"
                        )
                    current = self._sessions.get(session_id)
                    if current is not association:
                        raise LifecycleAssociationError(
                            "session is unavailable"
                        )
            except BaseException:
                if association.settlement_claim == claim:
                    association.settlement_claim = None
                    self._condition.notify_all()
                raise
            return claim

    def confirm_settlement(
        self,
        claim: SettlementClaim,
        *,
        terminal_digest: bytes | None = None,
        dispatcher_truth_observed: bool = False,
    ) -> SettlementWork:
        with self._condition:
            association = self._settlement_claim_locked(claim)
            if type(dispatcher_truth_observed) is not bool:
                raise TypeError("dispatcher_truth_observed must be a bool")
            if self._closed:
                raise LifecycleAssociationError("session is unavailable")
            if (
                claim.close_task
                and association.kind in {"plan", "task-plan"}
                and association.plan_token is None
            ):
                raise RuntimeError("task plan identity is unavailable")
            self._reconcile_terminal_locked(
                association,
                terminal_digest=terminal_digest,
                dispatcher_truth_observed=dispatcher_truth_observed,
            )
            if claim.close_task:
                association.settlement_target = "task"
            elif association.settlement_target is None:
                association.settlement_target = "session"
            replay = (
                not claim.close_task
                and association.task_id is not None
                and association.session_released
            )
            return SettlementWork(
                claim,
                claim.token.session_id,
                association.detail_owner,
                association.plan_token if claim.close_task else None,
                replay,
            )

    def complete_settlement(self, work: SettlementWork) -> None:
        with self._condition:
            association = self._settlement_claim_locked(work.claim)
            target = "task" if work.claim.close_task else "session"
            replay = (
                not work.claim.close_task
                and association.task_id is not None
                and association.session_released
            )
            expected = SettlementWork(
                work.claim,
                work.claim.token.session_id,
                association.detail_owner,
                association.plan_token if work.claim.close_task else None,
                replay,
            )
            if work != expected:
                raise LifecycleAssociationError("settlement work is stale")
            if association.settlement_target != target:
                raise RuntimeError("session settlement target is not sealed")
            if association.task_id is None:
                if association.terminal_digest is not None:
                    raise RuntimeError("direct session has terminal delivery state")
            elif association.terminal_digest is None:
                raise RuntimeError("task terminal truth is unavailable")
            if work.replay:
                association.settlement_claim = None
                self._condition.notify_all()
                return
            if work.claim.close_task:
                token = association.plan_token
                if work.plan_token != token:
                    raise RuntimeError("task plan identity changed")
                if token is not None:
                    plan = self._plans.get(token.request_id)
                    if plan is not None and plan.identity == token.identity:
                        raise RuntimeError("plan retirement remains pending")
                self._retire_association_locked(association)
            elif association.task_id is None:
                self._retire_association_locked(association)
            else:
                association.session_released = True
                association.settlement_claim = None
            self._condition.notify_all()

    def abandon_settlement(self, claim: SettlementClaim) -> None:
        with self._condition:
            association = self._sessions.get(claim.token.session_id)
            if (
                association is None
                or association.identity != claim.token.identity
                or association.settlement_claim != claim
            ):
                return
            association.settlement_claim = None
            self._condition.notify_all()

    def close(self) -> None:
        with self._condition:
            self._closed = True
            self._condition.notify_all()

    def retire_all(self) -> None:
        with self._condition:
            self._start_receipts.clear()
            self._plans.clear()
            self._admissions.clear()
            self._sessions.clear()
            self._tasks.clear()
            self._condition.notify_all()

    @staticmethod
    def _reconcile_terminal_locked(
        association: _SessionAssociation,
        *,
        terminal_digest: bytes | None,
        dispatcher_truth_observed: bool,
    ) -> None:
        if association.task_id is None:
            if terminal_digest is not None or dispatcher_truth_observed:
                raise RuntimeError(
                    "direct session settlement has no adapter terminal fact"
                )
            return
        if type(terminal_digest) is not bytes or len(terminal_digest) != 32:
            raise RuntimeError(
                "delivered terminal truth disagrees with dispatcher truth"
            )
        if dispatcher_truth_observed:
            if association.terminal_digest is None:
                association.terminal_digest = terminal_digest
            elif association.terminal_digest != terminal_digest:
                raise RuntimeError(
                    "delivered terminal truth disagrees with dispatcher truth"
                )
            return
        if association.terminal_digest != terminal_digest:
            raise RuntimeError(
                "delivered terminal truth disagrees with dispatcher truth"
            )

    def _settlement_claim_locked(
        self,
        claim: SettlementClaim,
    ) -> _SessionAssociation:
        association = self._association_locked(claim.token)
        if association.settlement_claim != claim:
            raise LifecycleAssociationError("settlement claim is stale")
        return association

    def _admission_locked(self, token: AdmissionToken) -> _SessionAssociation:
        admission = self._admissions.get(token.identity)
        if admission is None:
            raise LifecycleAssociationError("admission token is retired")
        return admission

    def _admission_rollback_claim_locked(
        self,
        claim: AdmissionRollbackClaim,
    ) -> _SessionAssociation:
        admission = self._admission_locked(claim.token)
        if admission.rollback_claim != claim:
            raise LifecycleAssociationError("admission rollback claim is stale")
        if (
            admission.session_id != claim.session_id
            or admission.detail_owner != claim.detail_owner
        ):
            raise LifecycleAssociationError("admission rollback subject changed")
        return admission

    def _plan_locked(self, token: PlanToken) -> _PlanEffect:
        plan = self._plans.get(token.request_id)
        if plan is None or plan.identity != token.identity:
            raise LifecycleAssociationError("plan token is retired")
        return plan

    def _plan_mutation_claim_locked(
        self,
        claim: PlanMutationClaim,
    ) -> _PlanEffect:
        plan = self._plan_locked(claim.token)
        if (
            plan.mutation_claim != claim
        ):
            raise LifecycleAssociationError("plan mutation claim is stale")
        return plan

    def _reserve_plan_retirement_locked(
        self,
        plan: _PlanEffect,
    ) -> PlanRetirementClaim:
        if plan.retirement_claim is not None:
            raise RuntimeError("plan retirement is already reserved")
        claim_id = self._mint_claim_id_locked()
        claim = PlanRetirementClaim(self._plan_token(plan), claim_id)
        plan.retirement_claim = claim
        try:
            while plan.mutation_claim is not None:
                self._condition.wait()
                if self._closed:
                    raise RuntimeError("service is closed")
                current = self._plans.get(plan.request_id)
                if current is not plan:
                    raise LifecycleAssociationError("plan token is retired")
            return claim
        except BaseException:
            if (
                self._plans.get(plan.request_id) is plan
                and plan.retirement_claim == claim
            ):
                plan.retirement_claim = None
                self._condition.notify_all()
            raise

    @staticmethod
    def _validate_plan_retirement_locked(
        plan: _PlanEffect,
        claim: PlanRetirementClaim,
    ) -> None:
        if (
            plan.identity != claim.token.identity
            or plan.retirement_claim != claim
        ):
            raise LifecycleAssociationError("plan retirement claim is stale")

    def _association_locked(
        self,
        token: AssociationToken,
    ) -> _SessionAssociation:
        association = self._sessions.get(token.session_id)
        if association is None or association.identity != token.identity:
            raise LifecycleAssociationError("session association is stale")
        return association

    def _validate_association_locked(
        self,
        association: _SessionAssociation | None,
        *,
        task_id: str | None | object,
        require_live: bool,
    ) -> None:
        if (
            association is None
            or self._admissions.get(association.identity) is association
        ):
            raise LifecycleAssociationError("session is unavailable")
        if task_id is not _ANY_TASK and association.task_id != task_id:
            raise LifecycleAssociationError("task/session association is invalid")
        if require_live and association.settlement_target is not None:
            raise LifecycleAssociationError("session is retired")

    def _retire_unpublished_association_locked(
        self,
        association: _SessionAssociation,
    ) -> None:
        assert association.session_id is not None
        if self._sessions.get(association.session_id) is not association:
            raise LifecycleAssociationError("session association is stale")
        task = self._task_for_association_locked(association)
        self._sessions.pop(association.session_id)
        if task is not None:
            task.session_id = None
            if task.start_failed:
                self._finish_failed_task_start_locked(task)

    def _retire_admission_locked(
        self,
        admission: _SessionAssociation,
    ) -> None:
        if self._admissions.get(admission.identity) is admission:
            self._admissions.pop(admission.identity, None)
        task = (
            None
            if admission.task_id is None
            else self._tasks.get(admission.task_id)
        )
        if task is not None:
            if task.admission_identity != admission.identity:
                raise LifecycleAssociationError("task admission is stale")
            task.admission_identity = None
            if task.start_failed and task.session_id is None:
                self._finish_failed_task_start_locked(task)

    def _retire_association_locked(
        self,
        association: _SessionAssociation,
    ) -> None:
        assert association.session_id is not None
        if self._sessions.get(association.session_id) is not association:
            raise LifecycleAssociationError("session association is stale")
        task = self._task_for_association_locked(association)
        self._sessions.pop(association.session_id)
        if association.command_id is not None:
            self._start_receipts.pop(association.command_id, None)
        if task is not None:
            self._tasks.pop(task.task_id, None)

    def _task_for_association_locked(
        self,
        association: _SessionAssociation,
    ) -> _TaskEffect | None:
        if association.task_id is None:
            return None
        task = self._tasks.get(association.task_id)
        if task is None or task.session_id != association.session_id:
            raise LifecycleAssociationError("task/session association is stale")
        return task

    def _task_for_admission_locked(
        self,
        admission: _SessionAssociation,
    ) -> _TaskEffect | None:
        if admission.task_id is None:
            return None
        task = self._tasks.get(admission.task_id)
        if (
            task is None
            or task.admission_identity != admission.identity
        ):
            raise LifecycleAssociationError("task admission is stale")
        return task

    @staticmethod
    def _association_token(
        association: _SessionAssociation,
    ) -> AssociationToken:
        if association.session_id is None:
            raise LifecycleAssociationError("admission has no session")
        return AssociationToken(association.session_id, association.identity)

    @staticmethod
    def _plan_token(plan: _PlanEffect) -> PlanToken:
        return PlanToken(plan.request_id, plan.identity)

    def _mint_claim_id_locked(self) -> int:
        self._next_claim_id += 1
        return self._next_claim_id

    def _mint_task_id_locked(self) -> str:
        while True:
            token = uuid4().hex
            task_id = f"task-{token}"
            if task_id not in self._tasks:
                return task_id

    def _finish_failed_task_start_locked(self, task: _TaskEffect) -> None:
        if task.signature == ("task-shell",) and task.shell_published:
            task.start_command_id = None
            task.start_signature = None
            task.start_kind = None
            task.start_failed = False
            return
        self._tasks.pop(task.task_id, None)

    @staticmethod
    def _require_command_id(command_id: str) -> None:
        if type(command_id) is not str or not command_id:
            raise ValueError("command_id must be nonempty")

    @staticmethod
    def _require_signature(signature: tuple[object, ...]) -> None:
        if type(signature) is not tuple:
            raise TypeError("lifecycle signature must be an exact tuple")
        pending = list(signature)
        while pending:
            value = pending.pop()
            if type(value) is tuple:
                pending.extend(value)
            elif type(value) not in {str, int, bool, type(None)}:
                raise TypeError(
                    "lifecycle signature values must be immutable scalars"
                )

    @staticmethod
    def _require_opaque_id(value: str, label: str) -> None:
        if type(value) is not str or _OPAQUE_ID.fullmatch(value) is None:
            raise ValueError(f"{label} must be 32 lowercase hex digits")


__all__ = [
    "AdmissionRollbackClaim",
    "AdmissionToken",
    "AssociationToken",
    "LifecycleAssociationError",
    "LifecycleReceiptConflictError",
    "LifecycleTaskCapacityError",
    "ObservationClaim",
    "PlanMutationClaim",
    "PlanRetirementClaim",
    "PlanToken",
    "SettlementClaim",
    "SettlementWork",
    "StartReceipt",
    "TASK_EFFECT_CAPACITY",
    "TaskLifecycle",
    "TaskStartClaim",
]
