# Retired resource-model ledger entries

Archived 2026-09-06: these entries tracked absent aggregate graph/reservation
acceptance rather than a verified runtime fix. BR-G-45 is retired; their old
closure instructions are historical only. Active admission and supported risk
policy remain in ../DEFENSE.md, and focused resource acceptance remains open.
This archive does not claim that runtime leaks or growth are impossible.

- MODERATE - OPEN (2026-08-27). Task-adjacent owner-count gap. The desktop
  registry caps live cards, but the complete runtime/service/dispatcher graphs
  and close-time owners do not yet share one task-wide byte reservation.
  Unpublished desktop session attachment is now structural: every desktop start
  binds its exact reservation before scheduling, observer timeout keeps that
  capacity charged under Dispatcher retry, and exact-session release detaches
  only after observer/detail retirement. Malformed return cleanup cannot drop
  an unauthenticated plan. The remaining cause is the absent task-wide graph
  charge and multi-session lifecycle; closure must bind those owners, and no
  formula may treat a timeout as retirement.

- SEVERE - OPEN (2026-08-27). Inventory complete-graph admission gap. Raw scan
  rows, returned repository rows, and tree input members now stop before first
  excess; requested paths, row ids, and mapping identities independently stop
  before their first raw excess and before normalization/deduplication/sorting,
  closing the inherited path-key `limit + 1` error. Integrity checks the exact
  candidate-row tuple before construction, and no valid excess publishes
  partial work. Synthetic tree/index and candidate construction, their finite
  preprocessing transients, old/new task generations, and the complete byte
  authority remain outside active admission. `DEFENSE.md` §1.3 owns the walls;
  The historical bridge proposal described a complete task/artifact graph; no active graph contract remains.
