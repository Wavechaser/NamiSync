"""Repeat the anomalous drain test under CPU load from parallel pytest runs."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
PY = str(REPO / ".venv" / "Scripts" / "python.exe")
ROUNDS = int(sys.argv[1]) if len(sys.argv) > 1 else 20
LOADERS = int(sys.argv[2]) if len(sys.argv) > 2 else 3
SELECT = "copied_dispatcher_partial_pause or copied_verify_uses_ordinary or copied_overlay_admits"
PYTHONPATH = sys.argv[3] if len(sys.argv) > 3 else None

env = dict(os.environ)
if PYTHONPATH:
    env["PYTHONPATH"] = PYTHONPATH
cwd = PYTHONPATH or str(REPO)
load = [
    subprocess.Popen(
        [PY, "-c", "import subprocess,sys\nwhile True:\n subprocess.run([sys.executable,'-m','pytest','tests/interfaces/web/test_drain.py','-q','-p','no:cacheprovider','-x'],capture_output=True)"],
        cwd=cwd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(LOADERS)
]
failures = 0
try:
    time.sleep(3)
    for round_index in range(ROUNDS):
        done = subprocess.run(
            [PY, "-m", "pytest", "tests/interfaces/web/test_drain.py", "-k", SELECT, "-q", "-p",
             "no:cacheprovider", "-rf", "--no-header"],
            cwd=cwd, env=env, capture_output=True, text=True,
        )
        last = done.stdout.strip().splitlines()[-1] if done.stdout.strip() else done.stderr[-200:]
        failed = re.findall(r"^FAILED .*$", done.stdout, re.M)
        if failed:
            failures += 1
            print(f"round {round_index}: {last}")
            for line in failed:
                print("   ", line[:400])
            log = Path(__file__).with_name(f"stress-failure-{round_index}.txt")
            log.write_text(done.stdout, encoding="utf-8")
        elif round_index % 5 == 0:
            print(f"round {round_index}: {last}", flush=True)
finally:
    for process in load:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)], capture_output=True)
        process.wait(30)
print("rounds with failures:", failures, "of", ROUNDS)
