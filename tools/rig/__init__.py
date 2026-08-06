"""In-vivo measurement rig for the executor and verifier modules.

The rig stands in for the workflow layer only. It fakes the two ledger seams
(``Recorder`` and ``IntegrityRecorder``) and the run seam (``RunContext``), and
runs every other collaborator exactly as the product does: the real scanner,
planner, native filesystem, native copy backend, and unbuffered reader.

It imports ``namisync.core`` and ``namisync.modules`` plus the pure
``workflows.selection`` safe-subset helper, and nothing else. It is not part of
the shipped package and pytest does not collect it.
"""
