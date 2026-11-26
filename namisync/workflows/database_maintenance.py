"""Check, backup and restore of the database pair under both exclusive claims.

The one place the two roles meet for maintenance. Each call holds both
maintenance claims, ledger first, for its whole run, so no NamiSync process
writes either database meanwhile and new work is refused at admission.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3

from namisync.core.clock import Clock
from namisync.db.claims import DatabaseClaimRefused, MaintenanceClaims, hold_maintenance_claims
from namisync.db.contracts import DATABASE_UNAVAILABLE_DIRECTION
from namisync.db.maintenance import (
    BACKUP_KEEP,
    DatabaseCheck,
    DatabaseCheckState,
    DatabaseRestore,
    DatabaseRestoreFailed,
    DatabaseRestoreRefused,
    backup_database,
    check_database,
    restore_database,
    rotate_backups,
)
from namisync.db.migration import DatabaseBackupFailed

from .database_pair import (
    DatabasePairContract,
    DatabasePairState,
    _refused,
    validate_database_pair,
)


ROLES = ("ledger", "history")


@dataclass(frozen=True, slots=True)
class DatabasePairCheck:
    """The pair's admission contract and each role's own check."""

    contract: DatabasePairContract
    checks: tuple[DatabaseCheck, ...] = ()


@dataclass(frozen=True, slots=True)
class DatabaseBackup:
    """One published maintenance backup."""

    role: str
    path: Path


@dataclass(frozen=True, slots=True)
class DatabasePairBackup:
    """Backups published, rotated backups removed, and removals that failed.

    A refused or failed call changed nothing but the ``backups`` it lists.
    """

    contract: DatabasePairContract
    backups: tuple[DatabaseBackup, ...] = ()
    removed: tuple[Path, ...] = ()
    removal_failures: tuple[tuple[Path, str], ...] = ()


@dataclass(frozen=True, slots=True)
class DatabasePairRestore:
    """The pair's contract after a restore, and the restore when one completed.

    ``kept`` names a pre-restore backup or replaced set a failed call left;
    the guidance does not repeat it. Whether a failed call changed anything is
    told by the result, not the guidance: with no ``kept`` and any reason but
    ``restore-unconfirmed``, nothing did.
    """

    contract: DatabasePairContract
    restore: DatabaseRestore | None = None
    kept: Path | None = None


# History states beside which a ledger is not restored. A restored ledger
# never stamps an older History's runs (only a ledger migrated in the same
# pair upgrade does), so a damaged, unreadable or older History does not
# block it, and either role can be repaired first. A newer History is beyond
# what this version can judge; another role means the paths are wrong.
_LEDGER_RESTORE_HISTORY = {
    DatabaseCheckState.NEWER: (
        "history-newer",
        "The History database beside this ledger was written by a newer NamiSync. "
        "Restore the ledger with that NamiSync version.",
    ),
    DatabaseCheckState.WRONG_ROLE: (
        "history-wrong-role",
        "The History database path does not hold a History database; the database "
        "paths look swapped. Check them (for the command line, --database and "
        "--history-database), then restore again.",
    ),
}
# Advice, not protection: a healthy older pair needs updating, and replacing
# its readable ledger with a current-schema backup is almost certainly a
# mistake. It applies only when both databases check older with nothing
# listed; any other ledger target, beside a History not refused above, goes
# on to restore's own checks of the target and the backup.
_LEDGER_RESTORE_OLDER_PAIR = (
    "pair-older",
    "The ledger and History databases were written by an earlier NamiSync and "
    "are not updated yet, and the ledger reads cleanly. Start NamiSync, or run a "
    "sync or inventory command, once to update the pair, then restore the ledger "
    "if it is still needed.",
)


def _ledger_restore_refusal(
    ledger: Path, history: Path, claims: MaintenanceClaims,
) -> DatabasePairContract | None:
    beside = check_database(history, history=True, claim=claims.history)
    refusal = _LEDGER_RESTORE_HISTORY.get(beside.state)
    if refusal is None and _healthy_older(beside) and _healthy_older(
        check_database(ledger, history=False, claim=claims.ledger),
    ):
        refusal = _LEDGER_RESTORE_OLDER_PAIR
    return None if refusal is None else _refused(refusal[0], guidance=refusal[1])


def _healthy_older(check: DatabaseCheck) -> bool:
    return check.state is DatabaseCheckState.OLDER and not check.problems


def _in_use(error: DatabaseClaimRefused) -> DatabasePairContract:
    return _refused("database-in-use", guidance=str(error))


def _unavailable(reason: str, error: BaseException) -> DatabasePairContract:
    return _refused(reason, guidance=(
        f"{DATABASE_UNAVAILABLE_DIRECTION} ({type(error).__name__}: {error})"
    ))


def check_database_pair(ledger_path: str | Path, history_path: str | Path) -> DatabasePairCheck:
    """Report the pair's contract and check each role, in any pair state."""

    ledger = Path(ledger_path).resolve()
    history = Path(history_path).resolve()
    try:
        with hold_maintenance_claims(ledger, history) as claims:
            checks = (
                check_database(ledger, history=False, claim=claims.ledger),
                check_database(history, history=True, claim=claims.history),
            )
            contract = validate_database_pair(ledger, history)
    except DatabaseClaimRefused as error:
        return DatabasePairCheck(_in_use(error))
    return DatabasePairCheck(contract, checks)


def backup_database_pair(
    ledger_path: str | Path, history_path: str | Path, *, clock: Clock,
) -> DatabasePairBackup:
    """Back up a ready pair, ledger then History, then rotate each role's backups.

    Both backups take one cut time read once both claims are held. A refused
    pair or a failed backup rotates nothing; a ledger backup published before
    History's failed is kept and reported.
    """

    ledger = Path(ledger_path).resolve()
    history = Path(history_path).resolve()
    backups: list[DatabaseBackup] = []
    try:
        with hold_maintenance_claims(ledger, history) as claims:
            now = clock.now()
            contract = validate_database_pair(ledger, history)
            if contract.state is not DatabasePairState.READY:
                return DatabasePairBackup(contract)
            for role, path, claim in (
                ("ledger", ledger, claims.ledger), ("history", history, claims.history),
            ):
                backups.append(DatabaseBackup(role, backup_database(
                    path, history=role == "history", claim=claim, now=now,
                )))
            removed: list[Path] = []
            failures: list[tuple[Path, str]] = []
            for role, path, claim in (
                ("ledger", ledger, claims.ledger), ("history", history, claims.history),
            ):
                published = next(backup.path for backup in backups if backup.role == role)
                # A custom main may be named like the other role's backups.
                rotation = rotate_backups(
                    path, claim=claim, keep=BACKUP_KEEP, protect=(published, ledger, history),
                )
                removed.extend(rotation.removed)
                failures.extend(rotation.failures)
    except DatabaseClaimRefused as error:
        return DatabasePairBackup(_in_use(error), tuple(backups))
    except DatabaseBackupFailed as error:
        return DatabasePairBackup(_refused("backup-failed", guidance=str(error)), tuple(backups))
    except (sqlite3.Error, OSError) as error:
        return DatabasePairBackup(_unavailable("backup-failed", error), tuple(backups))
    return DatabasePairBackup(contract, tuple(backups), tuple(removed), tuple(failures))


def restore_database_from_backup(
    ledger_path: str | Path,
    history_path: str | Path,
    role: str,
    backup: str | Path,
    *,
    clock: Clock,
) -> DatabasePairRestore:
    """Restore the ledger or History from a current-schema backup.

    The pair need not be ready: restore also replaces a database that fails
    admission. A ledger is not restored beside a History of another role or
    a newer one, nor over the readable ledger of an older pair that needs
    updating (``_ledger_restore_refusal``); History is restored beside a
    ledger in any state, since a restored History is already stamped and no
    later step stamps it again. The returned contract is the pair's after the
    call.
    """

    if role not in ROLES:
        raise ValueError("restore replaces the ledger or History")
    ledger = Path(ledger_path).resolve()
    history = Path(history_path).resolve()
    try:
        with hold_maintenance_claims(ledger, history) as claims:
            now = clock.now()
            if role == "ledger":
                refusal = _ledger_restore_refusal(ledger, history, claims)
                if refusal is not None:
                    return DatabasePairRestore(refusal)
            restored = restore_database(
                ledger if role == "ledger" else history, backup,
                history=role == "history",
                claim=claims.ledger if role == "ledger" else claims.history,
                now=now,
            )
            contract = validate_database_pair(ledger, history)
    except DatabaseClaimRefused as error:
        # DatabaseRestoreInUse carries the pre-restore backup it left.
        return DatabasePairRestore(_in_use(error), kept=getattr(error, "kept", None))
    except DatabaseRestoreRefused as error:
        return DatabasePairRestore(_refused(error.reason, guidance=str(error)))
    except DatabaseBackupFailed as error:
        return DatabasePairRestore(_refused("backup-failed", guidance=(
            f"{error} The {role} database was not restored."
        )))
    except DatabaseRestoreFailed as error:
        reason = "restore-unconfirmed" if error.unconfirmed else "restore-failed"
        return DatabasePairRestore(_refused(reason, guidance=str(error)), kept=error.kept)
    except (sqlite3.Error, OSError) as error:
        # Met before the point of no return: restore_database reports any
        # later failure as unconfirmed.
        return DatabasePairRestore(_unavailable("restore-failed", error))
    return DatabasePairRestore(contract, restored)
