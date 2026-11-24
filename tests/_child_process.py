"""A Python child process with pipe-synchronized, bounded line reads."""

from __future__ import annotations

from pathlib import Path
from queue import Empty, Queue
import subprocess
import sys
from threading import Thread

import pytest


PROJECT_ROOT = Path(__file__).parents[1]
WAIT_SECONDS = 20.0


class Child:
    """Runs ``python -c script *arguments``; the caller kills it in ``finally``."""

    def __init__(self, script: str, *arguments: str) -> None:
        self.process = subprocess.Popen(
            [sys.executable, "-c", script, *arguments],
            cwd=PROJECT_ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self._lines: Queue[str | None] = Queue()
        Thread(target=self._pump, daemon=True).start()

    def _pump(self) -> None:
        assert self.process.stdout is not None
        for line in self.process.stdout:
            self._lines.put(line.strip())
        self._lines.put(None)

    def read(self) -> str:
        try:
            line = self._lines.get(timeout=WAIT_SECONDS)
        except Empty:
            pytest.fail("child process did not answer within the bound")
        if line is None:
            self.process.wait(WAIT_SECONDS)
            assert self.process.stderr is not None
            pytest.fail(f"child process exited early: {self.process.stderr.read()}")
        return line

    def kill(self) -> None:
        if self.process.poll() is None:
            self.process.kill()
        self.process.wait(WAIT_SECONDS)


def run_child(script: str, *arguments: str) -> str:
    """Run a short child to completion and return its stripped stdout."""

    completed = subprocess.run(
        [sys.executable, "-c", script, *arguments],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=WAIT_SECONDS,
    )
    assert completed.returncode == 0, completed.stderr
    return completed.stdout.strip()
