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
    owner: SettlementClaim | None = None


@dataclass(frozen=True, slots=True)
class ObservationClaim:
    token: AssociationToken
    claim_id: int


@dataclass(frozen=True, slots=True)
class SettlementReservation:
    token: AssociationToken
    claim_id: int
    close_task: bool


@dataclass(frozen=True, slots=True)
class SettlementClaim:
    token: AssociationToken
    claim_id: int


@dataclass(frozen=True, slots=True)
class LifecycleStep:
    name: str
    session_id: str | None = None
    detail_owner: tuple[str, str] | None = None
    request_id: str | None = None
    plan_token: PlanToken | None = None
    plan_retirement: PlanRetirementClaim | None = None


@dataclass(frozen=True, slots=True)
class AdmissionRollbackClaim:
    token: AdmissionToken
    claim_id: int
    step: LifecycleStep


@dataclass(slots=True)
class _TaskEffect:
    task_id: str
    command_id: str
    signature: tuple[object, ...]
    session_id: str | None = None
    admission_identity: int | None = None
    start_failed: bool = False


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
    admission_cursor: Literal[
        "detail_install", "observation", "publish", "published"
    ]
    detail_owner: tuple[str, str] | None = None
    observation_active: bool = False
    rollback_claim: AdmissionRollbackClaim | None = None
    rollback_last_completed: AdmissionRollbackClaim | None = None
    observation_claim: ObservationClaim | None = None
    observation_last_completed: tuple[ObservationClaim, bool] | None = None
    request_id: str | None = None
    terminal_digest: bytes | None = None
    settlement_target: Literal["session", "task"] | None = None
    settlement_cursor: str | None = None
    settlement_claim: SettlementClaim | None = None
    settlement_reservation: SettlementReservation | None = None
    settlement_last_completed: tuple[SettlementClaim, str] | None = None
    settlement_last_finished: SettlementClaim | None = None


class TaskLifecycle:
    """Own receipts, association, and the next legal lifecycle step.

    This aggregate never calls an adapter, observer, dispatcher, or runtime.
    Callers perform the returned physical step outside the condition and then
    report that exact step as complete.
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
                reservation = association.settlement_reservation
                blocks_replay = (
                    receipt.task_id is None
                    and (
                        reservation is not None
                        or association.settlement_claim is not None
                        or association.settlement_target is not None
                    )
                ) or (
                    receipt.task_id is not None
                    and (
                        (
                            reservation is not None
                            and reservation.close_task
                        )
                        or association.settlement_target == "task"
                    )
                )
                if not blocks_replay:
                    return receipt
                if (
                    reservation is None
                    and association.settlement_claim is None
                ):
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
            )
            return TaskStartClaim(task_id, None)

    def abort_task_start(self, task_id: str) -> None:
        with self._condition:
            task = self._tasks.get(task_id)
            if task is None:
                return
            task.start_failed = True
            if task.session_id is None and task.admission_identity is None:
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

    def begin_plan_retirement(self, token: PlanToken) -> PlanRetirementClaim:
        """Exclude new mutations before the caller retires the runtime plan."""

        with self._condition:
            if self._closed:
                raise RuntimeError("service is closed")
            plan = self._plan_locked(token)
            while plan.retirement_claim is not None:
                self._condition.wait()
                if self._closed:
                    raise RuntimeError("service is closed")
                plan = self._plan_locked(token)
            return self._reserve_plan_retirement_locked(plan, owner=None)

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

    def retire_missing_plan(self, token: PlanToken) -> bool:
        """Retire exact application state after runtime absence is observed."""

        with self._condition:
            if self._closed:
                raise RuntimeError("service is closed")
            plan = self._plans.get(token.request_id)
            if plan is None or plan.identity != token.identity:
                return False
            while plan.retirement_claim is not None:
                self._condition.wait()
                if self._closed:
                    raise RuntimeError("service is closed")
                plan = self._plans.get(token.request_id)
                if plan is None:
                    return False
                if plan.identity != token.identity:
                    return False
            claim = self._reserve_plan_retirement_locked(plan, owner=None)
            self._validate_plan_retirement_locked(plan, claim)
            self._plans.pop(token.request_id, None)
            self._condition.notify_all()
            return True

    def begin_admission(
        self,
        kind: str,
        command_id: str | None,
        signature: tuple[object, ...],
        *,
        task_id: str | None = None,
        detail_owner: tuple[str, str] | None = None,
        expects_observation: bool,
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
        if type(expects_observation) is not bool:
            raise TypeError("expects_observation must be a bool")
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
                    task.command_id != command_id
                    or task.signature != signature
                    or kind != "task-plan"
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
                "detail_install" if detail_owner is not None else "observation",
                detail_owner,
                observation_active=expects_observation,
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
            if admission.session_id is not None:
                raise RuntimeError("admission already has a session")
            if session_id in self._sessions:
                raise RuntimeError("dispatcher reused a session id")
            task = self._task_for_admission_locked(admission)
            admission.session_id = session_id
            if task is not None:
                task.session_id = session_id
            self._sessions[session_id] = admission
            return self._association_token(admission)

    def install_detail_owner(
        self,
        token: AssociationToken,
    ) -> None:
        with self._condition:
            association = self._association_locked(token)
            if (
                association.admission_cursor != "detail_install"
                and association.detail_owner is not None
            ):
                return
            if (
                association.admission_cursor != "detail_install"
                or association.detail_owner is None
            ):
                raise RuntimeError("session detail installation is out of order")
            association.admission_cursor = "observation"

    def complete_admission_observation(
        self,
        token: AssociationToken,
        *,
        active: bool,
    ) -> None:
        if type(active) is not bool:
            raise TypeError("active must be a bool")
        with self._condition:
            association = self._association_locked(token)
            if (
                association.admission_cursor in {"publish", "published"}
                and active == association.observation_active
            ):
                return
            if association.admission_cursor != "observation":
                raise RuntimeError("session observation is out of order")
            if active != association.observation_active:
                raise RuntimeError("session observation liability is unresolved")
            association.admission_cursor = "publish"

    def mark_published(
        self,
        token: AdmissionToken,
        session_id: str,
    ) -> AssociationToken:
        self._require_opaque_id(session_id, "session id")
        with self._condition:
            admission = self._admissions.get(token.identity)
            if admission is None:
                association = self._sessions.get(session_id)
                if (
                    association is not None
                    and association.identity == token.identity
                    and association.admission_cursor == "published"
                ):
                    return self._association_token(association)
                raise LifecycleAssociationError("admission token is retired")
            if admission.session_id != session_id:
                raise LifecycleAssociationError(
                    "dispatcher published another admission session"
                )
            if admission.admission_cursor != "publish":
                raise RuntimeError("session publication is out of order")
            admission.admission_cursor = "published"
            self._admissions.pop(admission.identity, None)
            task = self._task_for_association_locked(admission)
            if task is not None:
                task.admission_identity = None
            return self._association_token(admission)

    def complete_start(
        self,
        token: AssociationToken,
        request_id: str,
    ) -> StartReceipt:
        self._require_opaque_id(request_id, "request id")
        with self._condition:
            association = self._association_locked(token)
            if self._closed:
                task = self._task_for_association_locked(association)
                if task is not None:
                    task.start_failed = True
                raise RuntimeError("service is closed")
            if association.admission_cursor != "published":
                raise RuntimeError("session was not published")
            association.request_id = request_id
            receipt = StartReceipt(
                association.kind,
                association.signature,
                request_id,
                association.session_id,
                association.task_id,
            )
            if association.command_id is not None:
                existing = self._start_receipts.get(association.command_id)
                if existing is not None and existing != receipt:
                    raise LifecycleReceiptConflictError(
                        "command_id raced with a different admitted session"
                    )
            if association.kind in {"plan", "task-plan"}:
                plan = self._plans.get(request_id)
                if plan is None:
                    self._next_identity += 1
                    self._plans[request_id] = _PlanEffect(
                        self._next_identity,
                        request_id,
                        association.session_id,
                        {},
                    )
                elif plan.session_id != association.session_id:
                    raise RuntimeError("plan request id was reused")
            if association.command_id is not None:
                self._start_receipts[association.command_id] = receipt
            self._condition.notify_all()
            return receipt

    def admission_rollback_step(
        self,
        token: AdmissionToken,
    ) -> AdmissionRollbackClaim:
        with self._condition:
            admission = self._admissions.get(token.identity)
            while admission is not None and admission.rollback_claim is not None:
                self._condition.wait()
                if self._closed:
                    raise RuntimeError("service is closed")
                admission = self._admissions.get(token.identity)
            if admission is None:
                return AdmissionRollbackClaim(
                    token,
                    0,
                    LifecycleStep("complete"),
                )
            step = self._admission_step_locked(admission)
            if step.name == "complete":
                return AdmissionRollbackClaim(
                    token,
                    0,
                    step,
                )
            claim = AdmissionRollbackClaim(
                token,
                self._mint_claim_id_locked(),
                step,
            )
            admission.rollback_claim = claim
            return claim

    def complete_admission_rollback_step(
        self,
        claim: AdmissionRollbackClaim,
    ) -> None:
        with self._condition:
            admission = self._admission_locked(claim.token)
            if admission.rollback_last_completed == claim:
                self._apply_admission_rollback_completion_locked(
                    admission,
                    claim,
                )
                return
            admission = self._admission_rollback_claim_locked(claim)
            expected = self._admission_step_locked(admission)
            if claim.step != expected or expected.name == "complete":
                raise RuntimeError("admission rollback step is out of order")
            admission.rollback_last_completed = claim
            self._apply_admission_rollback_completion_locked(admission, claim)

    def finish_admission_rollback(self, token: AdmissionToken) -> None:
        """Retire one admission after all of its physical liabilities clear."""

        with self._condition:
            admission = self._admissions.get(token.identity)
            if admission is None:
                return
            if admission.rollback_claim is not None:
                raise RuntimeError("admission rollback step remains pending")
            if self._admission_step_locked(admission).name != "complete":
                raise RuntimeError("admission rollback remains pending")
            if admission.session_id is not None:
                self._retire_unpublished_association_locked(admission)
            self._retire_admission_locked(admission)
            self._condition.notify_all()

    def abandon_admission_rollback_step(
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
                if association.settlement_reservation is not None:
                    raise LifecycleAssociationError("session is retired")
            if association.settlement_reservation is not None:
                raise LifecycleAssociationError("session is retired")
            claim_id = self._mint_claim_id_locked()
            claim = ObservationClaim(
                self._association_token(association),
                claim_id,
            )
            association.observation_claim = claim
            # Adoption may succeed before its marker call begins. Conservatively
            # retain release liability until the exact claim confirms otherwise.
            association.observation_active = True
            return claim

    def complete_observation(
        self,
        claim: ObservationClaim,
        *,
        active: bool,
    ) -> None:
        if type(active) is not bool:
            raise TypeError("active must be a bool")
        with self._condition:
            association = self._association_locked(claim.token)
            if association.observation_last_completed == (claim, active):
                association.observation_active = active
                association.observation_claim = None
                self._condition.notify_all()
                return
            association = self._observation_claim_locked(claim)
            association.observation_last_completed = (claim, active)
            association.observation_active = active
            association.observation_claim = None
            self._condition.notify_all()

    def abandon_observation(self, claim: ObservationClaim) -> None:
        with self._condition:
            association = self._sessions.get(claim.token.session_id)
            if (
                association is not None
                and association.identity == claim.token.identity
                and association.observation_last_completed is not None
                and association.observation_last_completed[0] == claim
            ):
                association.observation_active = (
                    association.observation_last_completed[1]
                )
                association.observation_claim = None
                self._condition.notify_all()
                return
            if (
                association is None
                or association.identity != claim.token.identity
                or association.observation_claim != claim
            ):
                return
            association.observation_claim = None
            self._condition.notify_all()

    def reserve_settlement(
        self,
        session_id: str,
        *,
        task_id: str | None | object = _ANY_TASK,
        close_task: bool,
    ) -> SettlementReservation:
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
            while (
                association.settlement_claim is not None
                or association.settlement_reservation is not None
            ):
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
            reservation = SettlementReservation(
                self._association_token(association),
                self._mint_claim_id_locked(),
                close_task,
            )
            association.settlement_reservation = reservation
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
                if association.settlement_reservation == reservation:
                    association.settlement_reservation = None
                    self._condition.notify_all()
                raise
            return reservation

    def activate_settlement(
        self,
        reservation: SettlementReservation,
        *,
        terminal_digest: bytes | None = None,
        dispatcher_truth_observed: bool = False,
    ) -> SettlementClaim:
        with self._condition:
            association = self._settlement_reservation_locked(reservation)
            prior_state = (
                association.terminal_digest,
                association.settlement_target,
                association.settlement_cursor,
                association.settlement_claim,
            )
            try:
                if type(dispatcher_truth_observed) is not bool:
                    raise TypeError(
                        "dispatcher_truth_observed must be a bool"
                    )
                if self._closed:
                    raise LifecycleAssociationError(
                        "session is unavailable"
                    )
                self._reconcile_terminal_locked(
                    association,
                    terminal_digest=terminal_digest,
                    dispatcher_truth_observed=dispatcher_truth_observed,
                )
                if reservation.close_task:
                    association.settlement_target = "task"
                elif association.settlement_target is None:
                    association.settlement_target = "session"
                if association.settlement_cursor is None:
                    association.settlement_cursor = (
                        "observer_release"
                        if association.observation_active
                        else "dispatcher_close"
                    )
                elif (
                    reservation.close_task
                    and association.settlement_cursor == "session_complete"
                ):
                    association.settlement_cursor = "plan_retire"
                claim = SettlementClaim(
                    self._association_token(association),
                    self._mint_claim_id_locked(),
                )
                association.settlement_claim = claim
                association.settlement_reservation = None
                self._condition.notify_all()
                return claim
            except BaseException:
                (
                    association.terminal_digest,
                    association.settlement_target,
                    association.settlement_cursor,
                    association.settlement_claim,
                ) = prior_state
                association.settlement_reservation = None
                self._condition.notify_all()
                raise

    def abandon_settlement_reservation(
        self,
        reservation: SettlementReservation,
    ) -> None:
        with self._condition:
            association = self._sessions.get(reservation.token.session_id)
            if (
                association is None
                or association.identity != reservation.token.identity
                or association.settlement_reservation != reservation
            ):
                return
            association.settlement_reservation = None
            self._condition.notify_all()

    def settlement_step(self, claim: SettlementClaim) -> LifecycleStep:
        with self._condition:
            association = self._settlement_claim_locked(claim)
            step = self._settlement_step_locked(association)
            if step.name != "plan_retire" or step.plan_token is None:
                return step
            owner = claim
            plan = self._plan_locked(step.plan_token)
            while plan.retirement_claim is not None:
                if plan.retirement_claim.owner == owner:
                    retirement = plan.retirement_claim
                    return LifecycleStep(
                        "plan_retire",
                        request_id=plan.request_id,
                        plan_token=retirement.token,
                        plan_retirement=retirement,
                    )
                self._condition.wait()
                if self._closed:
                    raise RuntimeError("service is closed")
                association = self._settlement_claim_locked(claim)
                step = self._settlement_step_locked(association)
                if step.plan_token is None:
                    return step
                plan = self._plan_locked(step.plan_token)
            retirement = self._reserve_plan_retirement_locked(
                plan,
                owner=owner,
            )
            return LifecycleStep(
                "plan_retire",
                request_id=plan.request_id,
                plan_token=retirement.token,
                plan_retirement=retirement,
            )

    def complete_settlement_step(
        self,
        claim: SettlementClaim,
        step_name: str,
    ) -> None:
        with self._condition:
            association = self._settlement_claim_locked(claim)
            if association.settlement_last_completed == (claim, step_name):
                self._apply_settlement_completion_locked(
                    association,
                    step_name,
                )
                return
            expected = self._settlement_step_locked(association)
            if step_name != expected.name or step_name == "complete":
                raise RuntimeError("session settlement step is out of order")
            association.settlement_last_completed = (claim, step_name)
            self._apply_settlement_completion_locked(association, step_name)

    def _apply_settlement_completion_locked(
        self,
        association: _SessionAssociation,
        step_name: str,
    ) -> None:
        if step_name == "observer_release":
                association.observation_active = False
                association.settlement_cursor = "dispatcher_close"
        elif step_name == "dispatcher_close":
            association.settlement_cursor = (
                "detail_retire"
                if association.detail_owner is not None
                else self._after_detail_cursor(association)
            )
        elif step_name == "detail_retire":
            association.detail_owner = None
            association.settlement_cursor = self._after_detail_cursor(
                association
            )
        elif step_name == "plan_retire":
            request_id = association.request_id
            if request_id is None:
                raise RuntimeError("task plan identity is unavailable")
            plan = self._plans.get(request_id)
            if plan is not None:
                if plan.session_id != association.session_id:
                    raise RuntimeError(
                        "task plan token belongs to another session"
                    )
                raise RuntimeError("plan retirement remains pending")
            association.settlement_cursor = "complete"
        else:
            raise RuntimeError("session settlement step is invalid")
        self._condition.notify_all()

    def finish_settlement(self, claim: SettlementClaim) -> None:
        with self._condition:
            association = self._sessions.get(claim.token.session_id)
            if association is None:
                return
            if association.identity != claim.token.identity:
                raise LifecycleAssociationError("settlement claim is stale")
            if association.settlement_last_finished == claim:
                self._apply_settlement_finish_locked(association)
                return
            association = self._settlement_claim_locked(claim)
            if self._settlement_step_locked(association).name != "complete":
                raise RuntimeError("session settlement remains pending")
            association.settlement_last_finished = claim
            self._apply_settlement_finish_locked(association)

    def _apply_settlement_finish_locked(
        self,
        association: _SessionAssociation,
    ) -> None:
        association.settlement_claim = None
        if association.settlement_target == "task" or association.task_id is None:
            self._retire_association_locked(association)
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
            if association.request_id is not None:
                plan = self._plans.get(association.request_id)
                owner = claim
                if (
                    plan is not None
                    and plan.retirement_claim is not None
                    and plan.retirement_claim.owner == owner
                ):
                    plan.retirement_claim = None
            association.settlement_claim = None
            self._condition.notify_all()

    def close(self) -> None:
        with self._condition:
            self._closed = True
            for association in self._sessions.values():
                association.settlement_reservation = None
            self._condition.notify_all()

    def mark_observer_shutdown_complete(self) -> None:
        with self._condition:
            for association in self._sessions.values():
                association.observation_active = False
                association.observation_claim = None
                if association.settlement_cursor == "observer_release":
                    association.settlement_cursor = "dispatcher_close"
            self._condition.notify_all()

    def retire_all(self) -> None:
        with self._condition:
            self._start_receipts.clear()
            self._plans.clear()
            self._admissions.clear()
            self._sessions.clear()
            self._tasks.clear()
            self._condition.notify_all()

    def _admission_step_locked(
        self,
        admission: _SessionAssociation,
    ) -> LifecycleStep:
        if admission.session_id is None:
            if admission.detail_owner is not None:
                return LifecycleStep(
                    "detail_retire",
                    detail_owner=admission.detail_owner,
                )
            return LifecycleStep("complete")
        if admission.admission_cursor == "published":
            raise RuntimeError("published session is not an admission rollback")
        if admission.observation_active:
            return LifecycleStep(
                "observer_release",
                session_id=admission.session_id,
            )
        if admission.detail_owner is not None:
            return LifecycleStep(
                "detail_retire",
                session_id=admission.session_id,
                detail_owner=admission.detail_owner,
            )
        return LifecycleStep("complete")

    def _apply_admission_rollback_completion_locked(
        self,
        admission: _SessionAssociation,
        claim: AdmissionRollbackClaim,
    ) -> None:
        if claim.step.name == "observer_release":
            admission.observation_active = False
        elif claim.step.name == "detail_retire":
            admission.detail_owner = None
        else:
            raise RuntimeError("admission rollback step is invalid")
        admission.rollback_claim = None
        self._condition.notify_all()

    def _settlement_step_locked(
        self,
        association: _SessionAssociation,
    ) -> LifecycleStep:
        cursor = association.settlement_cursor
        if cursor in {"observer_release", "dispatcher_close"}:
            return LifecycleStep(cursor)
        if cursor == "detail_retire":
            return LifecycleStep(cursor, detail_owner=association.detail_owner)
        if cursor == "plan_retire":
            if association.request_id is None:
                raise RuntimeError("task plan identity is unavailable")
            plan = self._plans.get(association.request_id)
            if plan is not None and plan.session_id != association.session_id:
                raise RuntimeError("task plan token belongs to another session")
            return LifecycleStep(
                cursor,
                request_id=association.request_id,
                plan_token=None if plan is None else self._plan_token(plan),
            )
        if cursor in {"session_complete", "complete"}:
            return LifecycleStep("complete")
        raise RuntimeError("session settlement cursor is invalid")

    @staticmethod
    def _after_detail_cursor(association: _SessionAssociation) -> str:
        return (
            "plan_retire"
            if association.settlement_target == "task"
            else "session_complete"
        )

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
        if (
            association.terminal_digest != terminal_digest
            or association.settlement_cursor
            not in {"detail_retire", "plan_retire", "session_complete", "complete"}
        ):
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
        return admission

    def _settlement_reservation_locked(
        self,
        reservation: SettlementReservation,
    ) -> _SessionAssociation:
        association = self._association_locked(reservation.token)
        if association.settlement_reservation != reservation:
            raise LifecycleAssociationError("settlement reservation is stale")
        return association

    def _observation_claim_locked(
        self,
        claim: ObservationClaim,
    ) -> _SessionAssociation:
        association = self._association_locked(claim.token)
        if association.observation_claim != claim:
            raise LifecycleAssociationError("observation claim is stale")
        return association

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
        *,
        owner: SettlementClaim | None,
    ) -> PlanRetirementClaim:
        if plan.retirement_claim is not None:
            raise RuntimeError("plan retirement is already reserved")
        claim_id = self._mint_claim_id_locked()
        claim = PlanRetirementClaim(self._plan_token(plan), claim_id, owner)
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

    @staticmethod
    def _validate_association_locked(
        association: _SessionAssociation | None,
        *,
        task_id: str | None | object,
        require_live: bool,
    ) -> None:
        if (
            association is None
            or association.admission_cursor != "published"
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
        self._sessions.pop(association.session_id, None)
        task = self._task_for_association_locked(association)
        if task is not None:
            task.session_id = None
            if task.start_failed:
                self._tasks.pop(task.task_id, None)

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
                self._tasks.pop(task.task_id, None)

    def _retire_association_locked(
        self,
        association: _SessionAssociation,
    ) -> None:
        assert association.session_id is not None
        self._sessions.pop(association.session_id, None)
        if association.command_id is not None:
            self._start_receipts.pop(association.command_id, None)
        task = self._task_for_association_locked(association)
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
    "LifecycleStep",
    "LifecycleTaskCapacityError",
    "ObservationClaim",
    "PlanMutationClaim",
    "PlanRetirementClaim",
    "PlanToken",
    "SettlementClaim",
    "SettlementReservation",
    "StartReceipt",
    "TASK_EFFECT_CAPACITY",
    "TaskLifecycle",
    "TaskStartClaim",
]
