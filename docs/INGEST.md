# Ingest Workflow

Status: latent draft. Priority: after the M0 sync pipeline is proven. No ingest
behavior is required for M0/M1; its protocol shapes and annotation namespace
are provisioned now without an unused runtime implementation.

## Purpose

Ingest copies media from a temporary card/mirror into a tracked library using
capture metadata to compute destination paths. It reuses scan, plan, review,
preflight, executor, recorder, verifier, dispatcher, and history contracts. It
does not create card-side ledger inventory, mutate the source, or touch
target-only library files.

## Pipeline

1. Scan the source in memory with a card-specific ignore snapshot.
2. Scan/inventory the destination library.
3. Enrich source records through injected `MetadataExtractor` in cancellable
   batch mode.
4. Apply a batch-shaped template `DestinationPolicy` to compute all final paths,
   collision suffixes, and companion groups.
5. Produce an immutable additive-only plan and terminate the plan session.
6. Show source, computed destination, fallback/collision/group reasons, and
   capacity for mandatory review.
7. Bind the reviewed plan fingerprint and selection digest into a `Commitment`,
   then start a separate execution session which freshly observes/preflights and
   executes through the ordinary executor.
8. Record destination-side origin provenance after successful publish.
9. Optionally run honest post-execution verification against the source before
   the card is declared safe to format.

No-gate ingest is prohibited. Scripted or queued ingest may replay an existing
commitment but may not generate a plan and execute it without human review.

## Destination And Enrichment Contract

Metadata extraction performs IO but makes no destination decision. Missing or
unreadable metadata yields a typed fallback input; it does not fail the run.
Templates are versioned, path-safe, deterministic, and composed from a bounded
token vocabulary. Destination policy receives the whole batch so it can resolve
collisions and companion groups globally.

The plan snapshots extractor version, relevant extracted fields, template and
policy version, fallback decisions, collision sequence, companion group id, and
final path. Execution never reruns ExifTool or recomputes assignments.

ExifTool's intended first implementation uses `-stay_open` batch mode with
bounded request/result correlation, stderr capture, cancellation/termination,
and no shell interpolation of paths.

## Additive And Stateless Safety

Ingest permits copy, mkdir, conflict/skip, and optional verification; it emits
no target trash/delete/move of unrelated library content and no source mutation.
Re-ingest derives no-op from current library evidence plus origin provenance.
Collision-suffixed prior results must be discoverable through a provenance
index, not by trying suffixes until something exists.

Origin annotation keys live under the reserved `ingest.origin.*` namespace and
are normalized/unique per entity/key. Template/extractor/policy versions and
assignment inputs are snapshotted into the plan. A changed template cannot
silently duplicate or relocate earlier imports; provenance lookup must surface
the prior destination for re-review. Content dedup remains a later policy and
is not inferred from annotations alone.

## Provenance

After successful target publish, record original filename, capture time source,
source size, optional source digest, extractor/template versions, and origin
group through namespaced annotations attached to the destination row. Annotation
writes are idempotent by run/op token and cannot precede file success.

An ingest profile is destination-anchored configuration, not a source-target
mapping. Presenting a new card never triggers volume rebind or missing-state
cleanup for an old card.

## Expectations

- Scanner treats source as an untracked observation.
- Planner uses destination policy for all paths and enforces additive policy.
- Executor uses ordinary atomic copy and final guards.
- Recorder writes only destination evidence/provenance.
- Verifier reports offload confidence separately from copy-stream hashing.
- Interfaces never tell the user a card is safe to format from copy success
  alone when verified offload was requested.

## Acceptance Criteria

- Ingest creates no source location, mapping, missing rows, or source mutation.
- Every final destination is visible before execution and is identical during
  execution; metadata/template changes after planning cause refusal or replan.
- Missing metadata follows the reviewed deterministic fallback and records why.
- RAW/JPEG/XMP/THM companion fixtures remain grouped with consistent renames.
- Batch collision assignments are unique, deterministic across input ordering,
  and stable on immediate rerun.
- Existing unrelated target files are never trashed, deleted, overwritten, or
  moved; collisions remain blocked or receive reviewed deterministic suffixes.
- Partial-card rerun finds prior collision-suffixed results through provenance
  and converges without card-side state.
- Template/version change consults recorded origin provenance, surfaces the
  prior destination for review, and never silently creates a second copy.
- Origin annotations appear only after successful publish and point to the
  correct destination row.
- ExifTool failure/cancel cannot hang the session, inject shell arguments, or
  fail unrelated extractable files.
- Verified offload performs honest reads and distinguishes copy-attested from
  readback/verify-attested results.
- Formatting guidance is enabled only after the explicitly required scope has
  the requested verification outcome.
