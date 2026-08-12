"""Local artifact paths owned by the headed NamiSync application."""

from __future__ import annotations

import ctypes
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


_LOCAL_DRIVE = re.compile(r"(?:\\\\\?\\)?[A-Za-z]:", re.ASCII)
_LOCAL_DRIVE_TYPES = frozenset({2, 3, 5, 6})


class AppPathError(ValueError):
    """The GUI application root is unavailable or is not a local path."""


@dataclass(frozen=True, slots=True)
class AppPaths:
    """Every local artifact used by one GUI composition."""

    root: Path
    ledger: Path
    history: Path
    settings: Path
    ui_state: Path
    logs: Path
    log_file: Path
    webview2: Path

    @classmethod
    def production(
        cls,
        environment: Mapping[str, str] | None = None,
    ) -> AppPaths:
        values = os.environ if environment is None else environment
        local_app_data = values.get("LOCALAPPDATA")
        if not local_app_data:
            raise AppPathError("LOCALAPPDATA is unavailable")
        return cls.from_root(Path(local_app_data) / "NamiSync")

    @classmethod
    def from_root(cls, root: str | Path) -> AppPaths:
        resolved = _resolve_local_root(root)
        logs = resolved / "logs"
        return cls(
            root=resolved,
            ledger=resolved / "ledger.db",
            history=resolved / "history.db",
            settings=resolved / "settings.json",
            ui_state=resolved / "ui-state.json",
            logs=logs,
            log_file=logs / "namisync.log",
            webview2=resolved / "webview2",
        )

    def ensure_directories(self) -> None:
        """Create the root and directory artifacts; safe to call repeatedly."""

        self.root.mkdir(parents=True, exist_ok=True)
        self._require_physical_containment()
        self.logs.mkdir(exist_ok=True)
        self.webview2.mkdir(exist_ok=True)
        self._require_physical_containment()

    def _require_physical_containment(self) -> None:
        root = self.root.resolve(strict=True)
        for artifact in (
            self.ledger,
            self.history,
            self.settings,
            self.ui_state,
            self.logs,
            self.log_file,
            self.webview2,
        ):
            if not (
                artifact.exists()
                or artifact.is_symlink()
                or artifact.is_junction()
            ):
                continue
            resolved = artifact.resolve(strict=False)
            if not resolved.is_relative_to(root):
                raise AppPathError(
                    "GUI artifact path resolves outside the application data root"
                )


def _resolve_local_root(value: str | Path) -> Path:
    path = Path(value)
    _require_absolute_local(path)
    try:
        resolved = path.resolve(strict=False)
    except OSError as error:
        raise AppPathError("application data root could not be resolved") from error
    _require_absolute_local(resolved)
    return resolved


def _require_absolute_local(path: Path) -> None:
    if (
        not path.is_absolute()
        or _LOCAL_DRIVE.fullmatch(path.drive) is None
        or _drive_type(path) not in _LOCAL_DRIVE_TYPES
    ):
        raise AppPathError("application data root must be an absolute local path")


def _drive_type(path: Path) -> int:
    root = f"{path.drive}\\"
    return int(ctypes.windll.kernel32.GetDriveTypeW(root))
