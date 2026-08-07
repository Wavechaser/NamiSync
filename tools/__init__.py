"""Development tools for measuring the executor and verifier modules.

The measurement harness stands in for the workflow layer only. It fakes the two
ledger seams (``Recorder`` and ``IntegrityRecorder``) and the run seam
(``RunContext``), while retaining the real scanner, planner, native filesystem,
native copy backend, and unbuffered reader. Executor planning uses explicit
empty correspondence and therefore represents a first-run/no-history plan.

It imports ``namisync.core`` and ``namisync.modules`` plus the pure
``workflows.selection`` safe-subset helper, and nothing else. It is not part of
the shipped package.
"""
