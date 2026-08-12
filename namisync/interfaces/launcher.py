"""Operating-system-classified console and desktop launchers."""

from __future__ import annotations

import ctypes
import sys
from dataclasses import dataclass
from pathlib import Path


STARTUP_ERROR_CAPTION = "NamiSync - Startup Error"
_EXIT_SUCCESS = 0
_EXIT_STARTUP = 1
_EXIT_USAGE = 2


class GuiArgumentError(ValueError):
    """The closed GUI argument grammar was not satisfied."""


@dataclass(frozen=True, slots=True)
class GuiArguments:
    data_dir: Path | None


def main(argv: list[str] | None = None) -> int:
    """Run the console adapter without importing the desktop host."""

    arguments = sys.argv[1:] if argv is None else argv
    from namisync.interfaces import cli

    if not arguments:
        cli.build_parser().print_usage(sys.stderr)
        print("For the desktop app, run nami-sync-gui.", file=sys.stderr)
        return cli.EXIT_USAGE
    return cli.main(arguments)


def gui_main(argv: list[str] | None = None) -> int:
    """Validate GUI composition input, then lazily enter the desktop host."""

    arguments = sys.argv[1:] if argv is None else argv
    try:
        parsed = _parse_gui_arguments(arguments)
        from namisync.interfaces.web.paths import AppPaths

        paths = (
            AppPaths.production()
            if parsed.data_dir is None
            else AppPaths.from_root(parsed.data_dir)
        )
    except (GuiArgumentError, OSError, ValueError) as error:
        _report_startup_error(str(error))
        return _EXIT_USAGE

    try:
        from namisync.interfaces.web.host import run_desktop

        return int(run_desktop(paths, startup_error=_report_startup_error))
    except Exception as error:
        _report_startup_error(_startup_failure_message(error))
        return _EXIT_STARTUP


def _parse_gui_arguments(arguments: list[str]) -> GuiArguments:
    if not arguments:
        return GuiArguments(data_dir=None)
    if len(arguments) == 1 and arguments[0].startswith("--data-dir="):
        value = arguments[0].partition("=")[2]
        if not value:
            raise GuiArgumentError("--data-dir requires an absolute local path")
        return GuiArguments(data_dir=Path(value))
    if len(arguments) == 2 and arguments[0] == "--data-dir":
        value = arguments[1]
        if not value or value.startswith("--"):
            raise GuiArgumentError("--data-dir requires an absolute local path")
        return GuiArguments(data_dir=Path(value))
    if sum(
        argument == "--data-dir" or argument.startswith("--data-dir=")
        for argument in arguments
    ) > 1:
        raise GuiArgumentError("--data-dir may be supplied only once")
    raise GuiArgumentError(
        "NamiSync desktop accepts only one optional --data-dir PATH argument"
    )


def _startup_failure_message(error: Exception) -> str:
    message = str(error).strip()
    return message or "NamiSync could not start the desktop host"


def _report_startup_error(message: str) -> None:
    try:
        _native_startup_error(message)
    except Exception:
        pass


def _native_startup_error(message: str) -> None:
    ctypes.windll.user32.MessageBoxW(
        None,
        message,
        STARTUP_ERROR_CAPTION,
        0x00000000 | 0x00000010,
    )
