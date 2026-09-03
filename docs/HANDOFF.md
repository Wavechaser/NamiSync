# Session Handoff

Status (2026-09-03): LC-3 is complete on `milestone1-anthony`; its atomic
record-composition commit is the current `HEAD` once this handoff is committed.
LC-4 is the next pending register row.

## LC-3 outcome

- `StoredSessionRecord` is the canonical frozen/slotted metadata and result
  value. It owns the only metadata/result validation.
- Live `SessionRecord` contains that exact stored value plus its opaque
  checkpoint. Its old positional/keyword constructor, frozen/slotted behavior,
  named read-only fields, equality, resource identity, and result identity are
  preserved.
- The registered generic dataclass introspection changes are accepted: live
  fields are now `stored` and `checkpoint`; repr, replace, asdict/astuple,
  pattern matching, annotations, hash nesting, and pickle/copy state may differ.
  A finite 13-file audit found no repository consumer of those old shapes.
- Dispatcher constructs one stored/live pair at admission, replaces the stored
  value for metadata/result transitions, reuses it for checkpoint-only changes,
  and passes `record.stored` itself to the store. The old ten-field projection
  is gone.
- No condition, lock, scheduler, map, worker, reservation, lease, queue, event,
  lifecycle, observer, or persistence-schema behavior changed. The explicit
  compatibility properties make the two production files net 48 lines larger;
  no generic record framework or additional retained graph was introduced.

## Verification

- Core/dispatcher focus: `391 passed`.
- Complete core session/event file after the final validation witness:
  `237 passed`.
- Core/dispatcher departments with bundled Node:
  `1368 passed, 1 skipped, 3605 deselected`.
- Ordinary suite with bundled Node:
  `4943 passed, 4 skipped, 28 deselected`.
- Frozen task-lifecycle T1 corpus: exact baseline match, including persisted
  bytes and public records.
- Import law: `12 kept, 0 broken`.
- Two bounded adversarial/consumer reviews: no blocker or missed consumer.

## Next action

Run LC-4 only as the disposable dispatcher-entry feasibility probe described
in `docs/TASK_LIFECYCLE_SIMPLIFICATION.md`. Production keeps the parallel maps
regardless of probe outcome. Attempt the instrumented-condition ownership check,
record a negative result if it would require a production helper, wider scope,
or control-flow change, then reverse all scratch code before committing only
the observation.

The historical `.codex` plan remains untouched. Old recovery/WIP refs remain
isolated and are not review units.
