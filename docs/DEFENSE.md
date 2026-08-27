# NamiSync Threat, Fault, and Tolerance Model

This document is the normative security, safety, and failure-tolerance policy.
It defines the environment in which NamiSync's guarantees hold, the outcomes
that are forbidden there, the degradations that are acceptable, and the tests
used to decide whether a new finding requires engineering work.

`BUGS.md` records concrete defects and their residual technical boundaries.
`FEATURES.md` records product behavior. `ARCHITECTURE.md` records the durable
contracts that implement that behavior. None of those documents accepts a
residual risk merely by describing it; acceptance and exclusion are decisions
owned here.

The product contract determines which outcomes are forbidden. The supported-
environment model determines when those guarantees apply. The tolerance policy
determines how NamiSync may degrade when it cannot complete a guarantee.
NamiSync therefore owes **authorization, containment, recoverability, bounded
operation, and truthful evidence**. It does not promise universal mutual
exclusion with external software or protection from a compromised same-user
trusted computing base.

---

## 1. Contract, assets, and hard walls

The product thesis is:

> reviewed plan -> execution matches the review -> durable evidence truthfully
> describes the effects that occurred

Atomic publication, fresh preflight, selection-bound commitment, effect
settlement, and separate result axes exist to preserve that chain. Evidence is
truthful at the observation or effect time it records; an external writer may
make it stale immediately afterward. "Never wrong, only behind" is a temporal
truth rule, not a claim that the filesystem remains frozen.

### 1.1 Protected assets and properties

The protected assets are:

- **user data** inside reviewed source and target roots, including recoverable
  versions NamiSync intentionally moves to owned trash;
- **mutation authority** derived from reviewed roots, plan, selection, and
  current root/volume evidence;
- **execution integrity** connecting the reviewed plan to the operations that
  actually run;
- **filesystem, integrity, ledger, and audit truth**, kept as independent axes;
- **host availability and bounded resources** at documented valid scale; and
- **local operational privacy** against accidental interface or diagnostic
  disclosure, without a confidentiality claim against the same Windows user,
  administrators, backups, or screen access.

### 1.2 Hard walls under the supported baseline

NamiSync must not:

1. mutate managed user data without the exact reviewed plan and selection;
2. mutate outside the reviewed roots or an exact owned-artifact location;
3. cause silent, permanent loss of file bytes;
4. publish partial content at a live destination;
5. assert false success, integrity, recording, audit, or durability evidence;
6. infer destructive absence from an incomplete scan;
7. let untrusted data become executable content, command authority, URL
   authority, presentation structure, or filesystem authority;
8. let the GUI commit a materially different plan or selection from the
   backend-bound view; or
9. admit unbounded externally triggered work at documented valid scale.

Probability does not excuse a hard-wall violation. Convergence is not a remedy
after irreversible loss, and another process having similar authority does not
excuse NamiSync crossing a hard wall during supported use.

### 1.3 Stage 6 scalar and retention walls

The scalar/native-identity walls are active from Stage 6 checkpoint 3.2. The
complete-graph and process-live retention walls remain accepted design until
their named later checkpoints land. `M1_BRIDGE.md` owns the mapped decision
records, exact wire shapes, accounting graph, reservation order, and refusal
schemas; other active documents point here instead of reproducing these limits.

- Every durable or externally presented byte quantity and filesystem
  nanosecond is in `0..9_223_372_036_854_775_807`. Typed relational values use
  checked SQLite `INTEGER`; bridge values use canonical unsigned-decimal text.
  Sequence numbers, bounded counts, offsets, and revisions remain
  JavaScript-safe integers. Native file indices are an opaque exception: their
  full Windows 128-bit value is canonical unsigned-decimal `TEXT`, never an
  arithmetic scalar or JSON number.
- Source primitives are admitted before they enter scans, plans, task roots,
  persistence projections, or codec projections. Complete paths use the
  Windows 32,767-UTF-16-unit ceiling; native volume label/filesystem buffers
  retain at most 260 units and native volume paths at most 32,767. Optional
  scan/resolution diagnostics retain a complete value of at most 1,024 UTF-8
  bytes or omit the whole value. Filters accept an exact tuple of at most 64
  nonempty valid-Unicode spellings, each at most 1,024 UTF-8 bytes and together
  at most 16,384 bytes, charged before slash normalization, deduplication, or
  sorting. One scan scope charges at most 120,000 supplied selected/subtree
  entries before canonical maps or sets are allocated. Root ids are nonempty
  valid Unicode and use a mechanically derived byte ceiling: the request-id
  maximum plus the UTF-8 lengths of the longest inventory namespace/suffix and
  the decimal width of `MAX_SAFE_INTEGER`.
- Verifier read chunks are exact integers in `1..4,194,304`. The Windows reader
  may simultaneously own one aligned native buffer and one Python `bytes`
  materialization at that maximum; a runtime default is not accepted as a
  substitute for this public component bound.
- A complete canonical bridge success envelope is at most 8,388,608 UTF-8
  bytes. The approved-view projection counts the exact compact, sorted-key,
  `ensure_ascii=False` representation incrementally and stops before the first
  excess instead of constructing an oversized duplicate graph.
- Destination-policy name/version and optional assignment annotations have no
  narrower production grammar yet. Constructors and projections enforce only
  the plan-domain ceiling per value; the checkpoint-4 completed-plan graph wall
  must still admit their combined retained occurrences before publication.
  Neither boundary is claimed as an empirical source-primitive maximum.
- A plan-capacity refusal requires an exact PLAN fact issued by the current
  workflow's opaque admission family. Workflow copies that fact, consumes its
  issuer marker, retires the raw exception, and saves no plan. An unissued,
  malformed, wrong-tree, or subtype signal is an ordinary internal failure,
  including when it escapes a nested collaborator inside an admitted module.
- Reachability determines whether the signed-domain guard is a product branch
  or an assertion; the two are not presented as equivalent risks:

  | Value or calculation | Reachability on supported NTFS/ReFS | Required treatment |
  | --- | --- | --- |
  | Native file index | Reachable through the full unsigned 128-bit Windows/Python domain | Keep canonical unsigned-decimal `TEXT` from one complete `FILE_ID_128` adapter and compare only as opaque identity; when the complete identifier is unavailable, record no identity rather than coerce it into `Scalar64`, a JSON number, legacy 64-bit handle fields, or SQLite arithmetic. |
  | Filesystem timestamp converted to Unix nanoseconds | Reachable | Reject the stat before ledger construction when it is negative or above the signed domain; never clamp a preservable timestamp. |
  | One file size, volume capacity, free-space observation, or `free + reclaimable` | Unreachable under the supported filesystem maxima | Validate at the native boundary and assertion-check the sum. Unavailable probes remain typed unavailable, but scalar overflow is not a user-facing capacity state or dedicated preflight refusal. |
  | Aggregate logical bytes across admitted rows | Reachable because sparse or cloned files can make apparent-size totals exceed physical volume capacity | Use checked accumulation. Refuse an unrepresentable plan before publication with the plan/domain `logical-bytes` review-limit witness; expose the inventory rollup's existing null-plus-overflow witness. |
  | Post-admission byte counters, bounded counts, and retention-budget arithmetic | Unreachable after their owning aggregate/capacity admission | Keep checked assertions that fail closed as an internal invariant violation; do not add ordinary overflow UX or a second refusal vocabulary. |
  | Bridge or persistence scalar supplied by an untrusted/corrupt producer | Reachable at the trust boundary | Strictly reject Boolean, signed, noncanonical, or above-domain values before state, cursor, queue, or ledger mutation. |

  The platform basis is explicit: Microsoft's [ReFS limits and feature
  table](https://learn.microsoft.com/en-us/windows-server/storage/refs/refs-overview)
  caps one file and one volume at 35 PB while supporting sparse files and block
  cloning; Windows [`FILETIME`](https://learn.microsoft.com/en-us/windows/win32/sysinfo/file-times)
  is a 64-bit 100-nanosecond value, and
  [`SYSTEMTIME`](https://learn.microsoft.com/en-us/windows/win32/api/minwinbase/ns-minwinbase-systemtime)
  accepts years through 30827. Python 3.13 documents that Windows
  [`st_ino` may reach 128 bits](https://docs.python.org/3.13/library/os.html#os.stat_result).
  CPython 3.13 derives that integer from the low/high halves of Windows
  [`FILE_ID_128`](https://github.com/python/cpython/blob/3.13/Python/fileutils.c#L1014-L1049),
  and Windows defines the file identifier plus volume serial as the comparison
  identity in
  [`FILE_ID_INFO`](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_id_info).
  Therefore individual size/capacity overflow is not reachable, aggregate
  apparent-size overflow is, timestamp conversion can exceed signed Unix
  nanoseconds, and file identity must stay outside the scalar domain. Values are
  never clamped, wrapped, or narrowed.

The remaining complete-graph and process-live containment walls below are not
active until their owning checkpoints:

- A plan or inventory tree admits at most 120,000 domain rows plus 120,000
  informational rows. The complete retained-graph ceilings are 128 MiB for a
  plan domain and 192 MiB independently for an inventory domain and either
  informational population. Collection stops before the first excess and
  never publishes a partial artifact.
- A standalone-integrity candidate independently admits at most 120,000 unique
  inventory-domain rows and 192 MiB for its complete identity-deduplicated
  candidate-custody graph. This wall is neither shared with nor implied by an
  inventory tree: a combined task charges every simultaneous refresh,
  candidate, continuation, outcome, and completion owner. Candidate collection
  stops before the first excess, with row precedence over retained bytes, and
  never publishes a partial selection or begins verifier work.
- One dispatcher session admits at most 240,000 ordered reliable result-item
  occurrences across its complete paused/resumed lifetime. This is the sum of
  the separately admitted 120,000-operation execution population and 120,000
  linked-integrity population; a repeated reference is still a retained
  occurrence. Admission checks the next item before event publication, audit
  observation, or accumulator mutation, and rejects an already-excess resume
  accumulator before workflow re-entry. The first producer excess is an
  internal workflow failure, not a user review-limit or truncation path; items
  already produced retain their honest ran-work truth, while no result, event,
  or audit owner may acquire an occurrence above the wall.
- Process-live task custody is capped at 48 tasks and a mechanically derived
  byte budget that must admit at least four simultaneously complete
  maximum-scale combined tasks. The separate immutable-projection cache holds
  at most six generations, and bridge work admits at most 64 handlers.
- Each task reserves at most 4,096 mutation receipts, including one cell that
  ordinary commands cannot consume so an accepted close remains recoverable.
  Setup retains at most 128 receipts for 30 minutes and 32 admitted location
  slots; each task retains at most 64 release tombstones for five minutes, and
  completed close tombstones are separately byte-budgeted for five minutes.
- Admission reserves the next phase's maximum reachable permanent and
  transient graph before work begins. It never evicts an open task or pinned
  generation, and capacity exhaustion may refuse new work but cannot make an
  admitted release or close fail for capacity.

An activated wall is a production-enforced containment claim, not a sampled
memory ceiling. Its implementation constants must be derived from the complete
reachable graph and independently validated under §7 before the owning gate
can close.

---

## 2. Supported baseline and threat ceiling

Adversaries and failures are classified by capability and consequence, not by
guessed intent. An editor, cloud client, test harness, confused user, and
malicious process can produce the same filesystem transition.

### 2.1 Supported environment and trusted computing base

The M1 baseline is a headed or headless, standard-integrity process for one
authorized Windows user, using supported local Windows filesystem semantics.
The trusted computing base includes installed NamiSync Python and packaged web
assets, CPython and pinned Python dependencies, WebView2 and its native host
stack when the desktop is used, Windows, and the documented behavior of the
filesystem primitives on which an operation relies.

The desktop task-artifact containment claim has a narrower executable premise:
64-bit CPython 3.13 on Windows x64, a release build with the standard GIL,
pymalloc compiled in, and no nonstandard `PYTHONMALLOC` override. The host checks
that source-derived profile before constructing the task registry and gives an
action-guiding startup refusal on drift. Debug, free-threaded, 32-bit, ARM64,
PyPy, CPython 3.14+, and alternate allocator profiles are unsupported for the
desktop claim rather than silently interpreted through the frozen object-graph
coefficients. This predicate is contract admission, not calibration evidence.

The desktop host must remain at standard integrity. Before headed beta release,
an elevated launch must be refused before command exposure unless a revision of
this model explicitly supports it; until that gate exists, elevated launch is
an unsupported configuration. Live application databases and browser state are
supported only on local, non-cloud-synchronized storage.

The authorized user establishes a root anchor through an interface path-
admission flow — currently an explicit CLI path or native picker — and reviews
the resulting mapping. Volume identity and filesystem type detect ordinary
substitution; they do not resist deliberate spoofing by a higher-authority
actor. Exact dependency pins establish tested behavior, not security-patch
freshness, so release maintenance must separately require a security-supported
runtime and dependency set.

The following are untrusted inputs even when no adversary exists:

- filenames, file bytes, metadata, directory shape, reparse state, and changes
  observed between filesystem calls;
- persisted database, settings, UI-state, and history values;
- command-line arguments, bridge envelopes, opaque identifiers, and all values
  rendered by the desktop; and
- timing, cancellation, OS notifications, exceptions, and partial native-call
  outcomes.

`RootAuthority`, plan fingerprints, selection commitments, receipts, hashes,
and opaque identifiers are consistency and anti-confusion evidence. They are
not secret bearer tokens and do not authenticate against compromised
same-principal code.

### 2.2 Threat and fault classes

- **Data and structure author — in scope.** An input author may pre-place
  arbitrary bytes, names, directory shapes, reparse points, collisions, and
  malformed values before NamiSync arrives. These are not race-window attacks;
  a planted trap can wait indefinitely and must be refused, isolated, or
  handled without crossing a hard wall.
- **Ordinary user and ambient faults — in scope for safe handling.** Mistakes,
  stale gestures, access denial, sharing violations, disk exhaustion,
  disconnects, process crashes, malformed state, and ordinary filesystem drift
  must produce a bounded result described by the tolerance policy.
- **Concurrent external writer — conditionally supported.** NamiSync detects
  and refuses drift where its checks observe it. The full data-preservation
  guarantee, however, requires managed roots to remain quiescent from
  non-NamiSync mutation while execution is touching them. A writer that wins
  after the final path-based guard is outside that full guarantee.
- **Same-principal hostile code — outside the security guarantee.** A process
  or injected code already running with the user's authority can alter the same
  files, databases, installed assets, process messages, or mutex namespace.
  NamiSync does not claim to isolate secrets or data from it, but must not
  amplify it into elevation, another user's authority, off-origin bridge
  authority, or broader filesystem reach.
- **Higher-authority compromise — outside the security guarantee.** An
  administrator, compromised kernel or driver, lying filesystem, deliberately
  violated atomic primitive, tampered runtime, or deliberate cryptographic or
  non-cryptographic hash collision is outside the M1 model.

XXH3-128 is accidental-corruption and consistency evidence, not adversarial
authenticity. Unkeyed SHA-256 plan and history digests bind structure and detect
ordinary drift; they do not authenticate records against same-principal code.

### 2.3 User authorization boundary

Before an accurate and complete review is explicitly committed, operator
mistakes are in scope. The product owns safe defaults, exact display, selection
integrity, stale-action refusal, and confirmation that cannot silently change
meaning.

After the trusted interface accurately presents the complete material effect
and the user commits that exact plan and selection, a harmful choice is
authorized intent rather than an attack. NamiSync must still provide the
recoverability it promised, but it cannot infer regret or distinguish a poor
choice from a deliberate one.

### 2.4 Capability and safety tests

The original capability test remains useful:

> Does a proposed defense raise the capability required to cause the harm, or
> does the actor already have a strictly easier path to the same harm?

It prevents expensive security theater against an already compromised
same-principal trusted base. It is not, by itself, a safety acceptance test.
Every finding is decided with four questions:

1. **Supported-assumption test.** Did it occur in the supported environment and
   mode, including the applicable quiescence and filesystem preconditions?
2. **Hard-wall test.** Did it cross any invariant in §1.2?
3. **Amplification test.** Did NamiSync grant greater authority, reach,
   persistence, or ambiguity than the actor already possessed?
4. **Degradation test.** Is the maximum outcome bounded, visible, and
   recoverable, or availability-only?

A supported-use hard-wall failure requires a fix even when the same user could
cause similar harm by another route. The capability test decides the security
ceiling; the other tests preserve product safety beneath it.

### 2.5 Reopen triggers

This model must be reviewed before introducing:

- an elevated desktop host, privileged helper, service account, or any split-
  integrity design;
- RPC or another command surface reachable by a different Windows user;
- a network peer, remotely authorized API, browser-hosted frontend, or remote
  asset authority;
- automatic or unattended destructive execution;
- supported network-share coordination or filesystem semantics not covered by
  the current local-volume contract;
- executable plugins, third-party scripts, or package update authority; or
- a guarantee that external writers may safely mutate managed roots during the
  same operation.

Elevation is not an M1 mitigation. Adding a new principal or authority channel
is an architecture review, not an implementation detail.

---

## 3. Tolerance policy

Severity in `BUGS.md` describes the worst supported consequence. The following
classes separately decide what disposition is allowed.

| Class | Meaning | Required product behavior | Representative outcomes |
| --- | --- | --- | --- |
| **T0 — hard invariant** | No tolerance under supported assumptions | Prevent or refuse before effect; if a native effect may already have committed, settle conservatively and expose uncertainty | unreviewed or out-of-root mutation, silent permanent byte loss, partial live publication, false durable truth, duplicate mutation, executable-data injection, unbounded valid-scale work |
| **T1 — safe degradation** | Bounded failure is acceptable | Keep independent safe work isolated, report the affected axis and actionable recovery, and preserve exact owned artifacts | refusal, bounded retry, stale-plan re-review, per-item failure, partial run, degraded recording/audit, explicit progress gap, renderer restart, exact temp/trash retention |
| **T2 — disclosed capability limit** | The platform or selected mode cannot supply a promised semantic | Refuse, warn before commitment, or require explicit opt-in; never imply preservation or verification that was not delivered | unsupported reparse/network behavior, unavailable metadata semantics, unproved power-loss durability, over-scale request |
| **T3 — equal/higher-authority actor outside model** | Prevention is not promised against an already compromised or stronger authority | Do not amplify authority; keep the exclusion explicit and reopen the model if the architecture adds a boundary | same-user code compromise, administrator/kernel/driver compromise, tampered trusted assets, post-final-guard external race outside the quiescent baseline |
| **T4 — informed user authorization** | The trusted UI accurately showed the exact consequence and the user approved it | Preserve commitment integrity, safe defaults, promised recovery, and truthful outcome; do not reinterpret informed intent | knowingly replacing or trashing reviewed files, explicit rebaseline, choosing a lossy but accurately disclosed option |

### 3.1 Probable failures and allowed outcomes

| Trigger | Minimum response | Maximum tolerable consequence |
| --- | --- | --- |
| Access denial, sharing violation, full disk, disconnect | Bounded retry where defined, then refusal or per-item failure | No mutation, or a truthful partial result with exact owned recovery artifacts |
| Stale plan, root, volume, selection, or UI revision | Refuse and return to review | Delay and repeated user review |
| Incomplete or hostile enumeration | Preserve typed uncertainty and continue only independent safe work | Skipped/incomplete scope; never absence-dependent destruction |
| Process cancellation or crash | Settle confirmed effects, preserve atomic live names, and rescan/replan after restart | Partial operation set, exact temp/trash artifacts, process-local task loss |
| Power loss | Claim durability only for barriers known to have succeeded | Explicitly unknown durability; never an invented power-loss guarantee |
| Recorder, history, or audit failure | Keep filesystem truth separate and visibly degrade the failed axis | Bounded ledger lag or audit loss under its owning retention contract |
| Renderer crash, reload, timeout, or uncertain response | Recover through receipts, sequence replay, or safe retry | Lost cosmetic state, delayed feedback, or bounded task refusal |
| Malformed or oversized interface value | Reject before handler/domain authority or large presentation construction | Request/item refusal only |
| Unsupported filesystem semantics | Refuse or disclose before commitment | Loss of the unsupported feature only when the user explicitly accepted it |
| External mutation observed before the final effect | Refuse, retry where safe, or fail the item | Availability loss or truthful partial completion |
| External mutation after the final path guard | Apply conservative settlement when detectable; document the exact residual | T3 when the writer violated the explicit quiescent-root precondition; without that precondition, an open defect |

### 3.2 "Best effort" is not a complete policy

Every active guarantee described as "best effort" must state, directly or by a
clear reference to its owning mechanism:

1. what action is attempted;
2. what failure is allowed;
3. the maximum data consequence;
4. the user-visible signal; and
5. the recovery or next action.

Without all five, "best effort" is an unresolved requirement, not an accepted
tolerance.

---

## 4. Desktop and WebView boundary

The packaged NamiSync document is trusted code. Everything it displays,
receives, or sends is validated as untrusted data. Remote and off-origin
content receives no NamiSync bridge authority.

The desktop trusted computing base includes the packaged HTML, CSS, and
JavaScript, the Python host and dependencies, pythonnet, WebView2, and Windows.
Origin validation proves which origin is currently committed; it does not prove
that a human clicked a genuine control or saw an accurate plan. Any JavaScript
executing in the allowed packaged origin can invoke every allowlisted command.
Opaque ids, commitments, revisions, and request ids prevent confusion and stale
execution; they are not authentication secrets or proof of user gesture.
The desktop readiness challenge has the same non-authority status. It is an
ephemeral, unlogged current-generation liveness nonce proving only that the
trusted host-to-page message path and page-to-host dispatch path both completed.
It never substitutes for committed-origin trust, command validation, handler
admission, or backend task/session authority.

Consequently, arbitrary same-origin script execution is a trusted-base
compromise and is outside M1. If a hostile renderer ever becomes in scope,
irreversible approval must move to an OS-native surface or separately trusted
broker that displays the backend-bound immutable summary. Origin checking alone
cannot provide that property.

The current containment obligations are still strict:

- off-origin or non-package content never receives dispatch authority;
- filesystem and persisted text remains inert text and cannot select markup,
  script, URL, class, style, command, or path authority;
- the complete inbound command envelope is bounded and exactly validated before
  domain dispatch;
- ordinary command availability remains composition-gated on the current
  document's bilateral readiness exchange, independently of bridge trust and
  handler reservation;
- commands are allowlisted and future mutations remain subject to backend plan,
  commitment, revision, and receipt rules;
- navigation, frames, popups, downloads, and runtime fallback fail closed under
  their owning bridge contract; and
- renderer failure, malformed requests, expired slots, saturation, and teardown
  may degrade only through bounded T1 outcomes.

Appearance enhancement and publication are T1-degradable after the window's
opaque base surface is known safe. Configuration, observation, read, or
host-to-page appearance-publication failure does not create command authority
and does not by itself refuse startup. If enhancement may have made the native
surface transparent and an opaque rollback cannot be confirmed, readable UI
cannot be claimed; that surface-safety failure is a hard startup refusal.

Filesystem-derived review labels have an additional layout-integrity wall at
their final DOM sink. The sink replaces U+0000-U+001F, U+007F-U+009F,
U+00AD, U+061C, U+200B, U+200E-U+200F, U+2028-U+202E,
U+2060-U+206F, U+FEFF, and input U+27E6-U+27E7 with the visible uppercase
four-hex marker `⟦U+XXXX⟧`. Escaping both marker delimiters makes the mapping
injective: an input spelling such as `⟦U+202E⟧` cannot be mistaken for the
marker produced from an input U+202E. The marker delimiters that the sink
itself emits are syntax; none of the listed active layout controls survives in
the rendered or accessibility label. Each label is also a CSS bidi isolate so
ordinary strong-direction text cannot reorder adjacent UI.

This is a presentation boundary, not sanitization or authority rewriting.
Filename display stays raw valid Unicode in workflow nodes, visible sequences,
bridge views, and literal case-folded search. Separately, callbacks receive the
raw opaque node ids supplied by the authoritative view. Marker spelling is not
decoder or query syntax, and the sink adds no filename byte/character cap or
truncation. Generic trusted interface copy continues through the ordinary
inert `textContent` sink; only filesystem-derived labels use the layout-control
projection.

The wall deliberately preserves ZWNJ/ZWJ, variation selectors, supplementary
tag characters, and the legitimate direction of Arabic and Hebrew text. It
does not claim universal spoof protection or defeat homoglyphs, ordinary
confusables, Unicode normalization differences, or grapheme ambiguity. These
remain outside this narrow transform and retain their Unicode rendering
semantics; no freedom from their visual ambiguity is claimed. Expanding the
escaped set, changing marker spelling, decoding markers in search, or using a
filesystem display value in any non-text sink reopens this boundary.

A browser timeout does not cancel an admitted Python handler. Receipts and
server-owned idempotency therefore remain mandatory for every retryable or
mutating command. The native host also does not presently supply an independent
deny policy for every browser permission or a complete native subresource
allowlist; the CSP, packaged-asset discipline, and trusted-renderer assumption
are the current boundary. Adding a browser capability or admitting new resource
classes reopens this review.

The 64-handler admission ceiling bounds work after NamiSync admission; pinned
pywebview creates an exposed-call thread before that gate. It therefore does
not prove a bound on raw WebMessage thread creation. Outbound bridge values also
require an aggregate byte/depth policy before a valid-scale terminal result can
claim complete runtime containment. These are availability/scale boundaries,
not authority claims, and remain governed by the owning bridge gates.

The loopback asset origin is not a claim that no listener exists. It is a local
asset and dependency parser surface with no externally authorized NamiSync
domain API. Same-origin authority applies to the origin, not proof of one exact
page path. The document policy and native navigation guards prevent untrusted
data or remote pages from acquiring that authority; installed assets and their
serving/runtime dependencies remain trusted.

---

## 5. Operational floor — TOCTOU and filesystem races

The threat ceiling says which actors are not defeated. The operational floor
says when a remaining race has enough containment and truth to stop consuming
engineering work.

### 5.1 Detection is general; prevention follows consequence

Point-of-touch revalidation, conditional primitives, atomic publication, and
conservative settlement often detect a lost race rather than excluding every
writer. Detection plus honest settlement is sufficient only when the maximum
result stays within T1. Prevention or stronger binding is required when a
supported-use loss can cross T0.

Final guards are especially important around replace, delete, trash, rename,
and evidence publication, but destruction is not the only reason to prevent a
race. Out-of-root effects, unreviewed mutation, false evidence, executable-data
injection, and unbounded work also require prevention or refusal.

### 5.2 Preplaced traps and live racers

Timing does not establish safety. A preplaced trap requires no race and can
wait indefinitely; a live substitution requires a concurrent writer. Neither
is acceptable merely because an observed interval is short. Scheduling can
stretch any path-based guard-to-use interval, and quantitative timing or
likelihood claims must satisfy the measurement authority in §7.

Preplaceable data and namespace structures are in scope and must be handled.
Live post-final-guard substitution is classified by the supported preconditions
and maximum consequence, not by a "microsecond window" argument.

### 5.3 Stopping rule

A residual is closed only when all of the following hold:

1. its trigger, required capability, supported preconditions, and maximum
   consequence are explicit;
2. it crosses no hard wall under supported assumptions;
3. its allowed result is bounded, visible, and recoverable or availability-
   only;
4. NamiSync does not amplify the triggering actor's authority;
5. the next mitigation rung is named; and
6. the residual register assigns an explicit disposition and revisit trigger.

A real-time racer is not automatically acceptable. Convergence is acceptable
only if no irreversible loss or false evidence has already occurred.

### 5.4 Windows mitigation ladder

Bottom to top, each rung closes more of the path-to-use gap at rising cost:

1. **Lexical validation and no-follow admission.** Reject escapes and reparse
   components before physical resolution. *Implemented baseline.*
2. **Re-stat or revalidate at point of touch.** Recheck root, parent, leaf,
   identity, and relevant metadata immediately before the operation.
   *Implemented where the current operation has evidence to compare.*
3. **Atomic conditional primitives.** Prefer operations such as `CREATE_NEW`,
   non-replacing rename, or `RemoveDirectory` emptiness whose condition is
   enforced by the same syscall that applies the effect. *Implemented where the
   operation has a matching Windows primitive.*
4. **Handle-bound operations.** Open once, verify identity on the handle, and
   mutate through it where Windows supplies an appropriate supported primitive.
   *Partially implemented:* the executor and verifier climb this rung
   selectively.
5. **Handle-relative traversal.** Use root/parent-handle-relative opens for the
   complete walk when path-based revalidation cannot meet a supported hard
   wall. This is the terminal path-race rung and carries architectural cost.
   *Not adopted as the general traversal model.*

Rungs 1–3 are the default. Rungs 4–5 are justified per operation by a supported
hard-wall requirement or demonstrated field consequence, not by a generic wish
to eliminate all races.

### 5.5 When to climb

Climb when a supported path can cross T0, when a supposedly T1 result is not
actually bounded/visible/recoverable, or when field evidence shows that a
probable supported failure makes the feature unusable. Do not climb solely to
exclude an already compromised same-principal trusted base when the mitigation
adds no boundary and prevents no authority amplification.

When the remaining result is genuinely T1 or T2, record it and stop. When it is
T3, state the precondition that places it outside the model. Never convert an
open T0 defect into an accepted residual through documentation alone.

---

## 6. Residual-risk register and triage

Every residual entry records:

- stable id and owning operation/component;
- supported precondition and triggering capability;
- maximum consequence and affected hard wall, if any;
- visible signal and recovery path;
- current mitigation rung and next closing rung;
- disposition: `accepted-safe-degradation`, `disclosed-capability-limit`,
  `out-of-supported-model`, or `open-defect`; and
- owner plus the architecture, feature, field-evidence, or principal change
  that reopens it.

Current external-writer classes are decided as follows:

| ID | Residual | Disposition |
| --- | --- | --- |
| **EW-1** | A live source-leaf substitution is moved to a still-verified owned-trash destination; the substituted item remains recoverable and the result is truthful | `accepted-safe-degradation` only for the bounded recoverable outcome; handle-bound rename is the closing rung |
| **EW-2** | Destination-parent substitution after the final path guard can relocate bytes outside owned trash and invalidate location/recovery truth | `out-of-supported-model` because the writer violated the explicit quiescent-root precondition; without that precondition, `open-defect`; handle-relative traversal is the closing rung |
| **EW-3** | A live target is replaced after the final guard and an update or internal mirror delete destroys the replacement | `out-of-supported-model` because the writer violated the explicit quiescent-root precondition; without that precondition, `open-defect`; a suitable handle-bound conditional mutation is the closing rung |
| **EW-4** | Identity-weak substitution or same-object mutation defeats path/stat evidence before content attestation | `out-of-supported-model` because the writer violated the quiescent-root precondition; without that precondition, `open-defect`; handle-bound content verification/publication or byte reread is the closing rung |

Future findings use this triage:

1. **Preplaceable or live?** Preplaceable input/structure is in scope; a live
   race proceeds to the supported-assumption test.
2. **Which hard wall and consequence?** A supported T0 path is a defect.
3. **Which tolerance class?** T1/T2 require the exact signal and recovery;
   T3 requires the excluding precondition; T4 requires accurate commitment.
4. **Which rung closes it?** Record the next real mitigation rather than an
   unspecified promise to harden later.

A residual sentence in `BUGS.md`, `FEATURES.md`, or a component document is
technical context, not acceptance. Only a disposition here closes the policy
decision.

---

## 7. Quantitative evidence and measurement authority

Quantitative evidence supports a product consequence or release decision; it
does not choose that consequence. This section is the normative authority for
classifying quantitative claims, selecting an evidence tier, and deciding what
may close a gate.

- Classify every quantitative claim before building its evidence. First decide
  from the consequence model above whether the number is a hard invariant, a
  release SLO, a soft drift guard, or a diagnostic. Evidence strength cannot
  promote a diagnostic or soft guard into acceptance evidence. A guard may
  still fail closed pending explicit adjudication under its owning consequence
  and release policy.
- Before selecting a tier, decide whether production can enforce the proposed
  bound. An enforceable containment bound must first become production policy
  derived entirely from enforced maxima over the complete admitted domain,
  with every assumption checked. That analytical or source-derived bound may
  close outside the empirical tiers; empirical characterization may guard its
  implementation but cannot substitute for containment. Any irreducible term
  sampled from an allocator, runtime, or environment remains a separately
  classified empirical claim.
- Then distinguish deterministic quantities from noisy ones. An exact
  measurement function proven free of variable terms produces one deterministic
  value from frozen source, corpus, runtime, dependencies, and representation.
  Protected authority for that value uses an independently authored oracle or
  expected result and a protected baseline or contract. Repeat runs are
  required only when stability or nondeterminism is itself part of the claim;
  byte-identical fresh children add provenance and drift confidence, not
  statistical samples, and do not justify calibration, holdout, headroom, or a
  sampled ceiling.
- Evidence tiers describe how a quantitative claim is used. **Tier 0** is a
  reasoned target and never closes a gate. **Tier 1** is a current-source live
  drift guard against an already accepted contract or claim and is not
  acceptance evidence. **Tier 2** is named-reference acceptance for an
  independently predeclared budget: exact fixture and profile; expected result
  plus evaluation count for a deterministic quantity, or statistic plus run
  count for a noisy one; committed raw evidence; and a separate validator.
  **Tier 3** is protected authority with the empirical and deterministic forms
  below.
- Empirical Tier 3 is required, after the consequence and enforceability
  decisions above, when calibration derives a release ceiling, release-gating
  acceptance authority failed or was invalidated, an empirical number without
  an analytical bound closes a cross-slice user-operation gate, or an
  unversioned runtime-dependent result would otherwise become a release limit.
  Use the lowest sufficient tier for every other number; compatible Tier 2
  measurements may share one vertical-slice harness.
- Empirical Tier 3 requires disjoint calibration and holdout data, derivation,
  rounding, headroom, and fresh-process count committed before holdout;
  verdict-free raw artifacts; exact source, instrument, fixture, runtime, and
  dependency authority plus immutable validator/contract blob identity; and
  fail-closed unknown-input handling. Calibration never validates its own
  limit, and a frozen limit is never retuned after holdout. Accepted contracts,
  validators, and artifacts are append/version-only rather than edited in
  place.
- Deterministic protected Tier 3 uses the oracle/expected-result form above
  rather than empirical calibration and holdout. The executor settlement
  oracle additionally declares repeated identical normalized runs because
  stability is part of that gate's claim.
- Every measured quantity names its roots, scaling axes, aggregation/retention
  policy, tier, artifacts, and rerun/version trigger in the owning component
  authority. Before accepting a new or changed retained-memory representation,
  its corpus must classify every retained dataclass field and reachable mapping
  family/key as populated at its declared envelope or intentionally absent/non-
  retained. An unclassified representation change invalidates that acceptance
  evidence.

---

## 8. Documentation ownership

- `DEFENSE.md` owns supported assumptions, trusted boundaries, hard walls,
  tolerance classes, quantitative-evidence authority, residual dispositions,
  and model-reopen triggers.
- `ARCHITECTURE.md` owns the durable contracts and layering that enforce them.
- `FEATURES.md` owns implemented and planned user-visible behavior and links
  any limitation to its defense disposition.
- `BUGS.md` owns concrete defect incidents, fixes, severity, and only the
  residual detail necessary to identify the technical boundary.
- Module documents own operation-specific mechanisms, limits, and extension
  policy. `M1_BRIDGE.md` owns exact desktop envelopes, commands, limits, and
  acceptance gates beneath the trusted-base decision in §4.
- `CHANGELOG.md` records dated adoption or revision of this policy;
  `HANDOFF.md` carries only immediate session context.

When behavior, an authority boundary, a supported precondition, or a residual
disposition changes, update this document and the owning behavior/mechanism
document together. A new principal or hard-wall exception requires explicit
architecture review before implementation.
