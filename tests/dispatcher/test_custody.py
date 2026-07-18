from __future__ import annotations

import os
import subprocess
import sys
from threading import Event, Thread

import pytest

from namisync.core.session import ResourceId
from namisync.core.session import Canceled
from namisync.dispatcher.custody import WindowsNamedMutexProvider


pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows custody contract")


def test_named_mutex_contends_across_processes_and_recovers_abandoned_holder() -> None:
    resource = ResourceId("volume", "process-kill-test")
    code = """
import sys
from namisync.core.session import ResourceId
from namisync.dispatcher.custody import WindowsNamedMutexProvider
lease = WindowsNamedMutexProvider().acquire([ResourceId('volume', 'process-kill-test')], lambda: False)
print('acquired', flush=True)
sys.stdin.read()
lease.release()
"""
    process = subprocess.Popen(
        [sys.executable, "-c", code],
        cwd=os.getcwd(),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert process.stdout is not None
        assert process.stdout.readline().strip() == "acquired"
        acquired = Event()
        release = Event()

        def acquire() -> None:
            lease = WindowsNamedMutexProvider().acquire([resource], lambda: False)
            acquired.set()
            assert release.wait(2)
            lease.release()

        thread = Thread(target=acquire)
        thread.start()
        assert not acquired.wait(0.2)
        process.kill()
        process.wait(2)
        assert acquired.wait(2)
        release.set()
        thread.join(2)
        assert not thread.is_alive()
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(2)


def test_cancel_during_multi_resource_acquisition_releases_partial_lease() -> None:
    code = """
import sys
from namisync.core.session import ResourceId
from namisync.dispatcher.custody import WindowsNamedMutexProvider
lease = WindowsNamedMutexProvider().acquire([ResourceId('volume', 'partial-b')], lambda: False)
print('acquired', flush=True)
sys.stdin.read()
lease.release()
"""
    process = subprocess.Popen(
        [sys.executable, "-c", code],
        cwd=os.getcwd(),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert process.stdout is not None
        assert process.stdout.readline().strip() == "acquired"
        cancel = Event()
        finished = Event()
        errors = []

        def acquire_both() -> None:
            try:
                WindowsNamedMutexProvider().acquire(
                    [ResourceId("volume", "partial-a"), ResourceId("volume", "partial-b")],
                    cancel.is_set,
                )
            except BaseException as error:
                errors.append(error)
            finally:
                finished.set()

        thread = Thread(target=acquire_both)
        thread.start()
        assert not finished.wait(0.2)
        cancel.set()
        assert finished.wait(2)
        assert len(errors) == 1 and isinstance(errors[0], Canceled)
        lease = WindowsNamedMutexProvider().acquire(
            [ResourceId("volume", "partial-a")], lambda: False
        )
        lease.release()
        thread.join(2)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(2)
