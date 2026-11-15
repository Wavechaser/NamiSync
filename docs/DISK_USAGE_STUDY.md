# Disk Usage View — Future Feature Study

Status: **study only**, indexed from [M2_PROPOSAL](M2_PROPOSAL.md). Nothing here
is accepted scope, activates implementation, or changes an M1 limit. The user's
direction from 2026-11-15 is recorded under [Decisions](#decisions-2026-11-15);
a few questions remain open. Inspected revision: `ebf72fbe`.

## Prompt

Spaceketeer was a Windows disk-usage viewer. It is no longer distributed: its
Store listing is gone, and its website remains without its web apps or contact
links. It scanned a drive or folder and showed a sunburst chart next to a flat,
Explorer-like table with Name / Contents (“N files, M folders”) / Size columns.
The table lists one level only. The sunburst goes a few rings deep, shows
folders but not individual files, and caps how many segments it draws. It
offered Pause / Resume / Rescan, Copy Path, Open in Explorer and Properties.
NamiSync's scanner and inventory already compute most of that data. The
question is whether NamiSync should present it the same way.

## User Goal

The page answers **“what exists here, and what is taking up space?”** Each
page answers a different question:

| Page | Question |
| --- | --- |
| Plan / execution | What will change on the target? Rows describe operations, mostly from the target's side, so it is a poor view of what simply exists. |
| Inventory | What evidence do we hold for a tracked location? |
| **This page** | What exists in one folder or volume, and how big is it? |
| Compare (proposed) | What exists in A and B, and how do they differ? |

Inside NamiSync the question also comes up without being asked:

- Plan review reports a capacity shortfall on the target, and the user needs to
  know what to clear.
- `.synctrash` and displaced update versions grow on the target. Nothing shows
  how much space they use until a trash retention policy exists
  ([FEATURES → Trash Retention Policy](FEATURES.md#data-protection)).
- Before a first sync, the user wants to see the shape of a source tree.

## Decisions (2026-11-15)

| Question | User direction | Consequence |
| --- | --- | --- |
| Placement | A new page that answers “what exists here.” A compare page (“what exists in A and B and how they differ”) is a separate future page that may share the two-pane layout. | See [Page](#page). Only the layout is shared, so neither feature blocks the other. |
| Size meaning | Logical (end-of-file) size from `os.scandir`. The small difference from allocated size is tolerated; Properties shows the exact on-disk figure. Probe the known divergent cases before implementation, for rigor. | No new enumeration backend; see [Size](#size). |
| Shape and scale | Spaceketeer-like: one flat level of files and folders, and a few-ring sunburst of folders. | The whole tree is still walked, but only directory aggregates are retained; see [Scale](#scale). |
| Volume custody | Wait. Say so visibly, so the user can choose to pause a sync on that volume. | No new dispatcher custody mode; see [Session behavior](#session-behavior). |
| Chart | Sunburst. Each ring shows only the largest few child folders above a size threshold, so it stays readable. | Parent totals come from the aggregate tree, so no separate slice-merging pass is needed; see [Chart](#chart). |
| Copy Path, Open in Explorer, Properties | Wanted on every page regardless of this feature. Click-through is nice to have. Plan prefers the target side, but copies and updates point naturally at the source. Missing items get no item actions; their folder can still open if it exists. | Separate proposal ([M2_PROPOSAL → Shell actions](M2_PROPOSAL.md)). Side policy is under [Shell actions](#shell-actions). |

## What Exists Today

| Spaceketeer capability | NamiSync now | Gap |
| --- | --- | --- |
| Recursive walk of a folder or whole drive | Scanner FULL scan. Volume roots are admissible locations (displayed as “Volume root”). | The sync scanner opens every entry on NTFS to read file identity; see [Size](#size). |
| Per-folder total size | Inventory projection rolls up complete file bytes. Overflow and unknown bytes are explicit, never clamped ([INVENTORY](INVENTORY.md#stage-6-desktop-contracts-protocol-subset-active)). | Requires a ledger-backed inventory. |
| Contents (“N files, M folders”) | Rollup counters already include descendant row and file counts (`inventory_projection._row_counters`). | No column. |
| Largest-first table | Server-owned sibling sort on Size ([PRESENTATION](PRESENTATION.md#search-filters-sorting-and-follow)). | **Folders cannot be ranked by total.** `sibling_order.sorted_siblings` sorts files first, then folders by their own size, not their aggregate bytes. |
| Flat one-level list with drill-down | Bounded tree with expand and collapse. | No flat “focus folder” list or breadcrumb. |
| Chart | None. | New. |
| Rescan | Whole, exact or recursive-folder Refresh. This is already finer than Spaceketeer's. | None. |
| Pause / Resume | Inventory scan is cancel-only (pause unsupported). | Not needed. |
| Copy Path, Open in Explorer, Properties | Copy Path is listed as a future Inventory action. The host already exposes one native call, the folder picker (`interfaces/web/host.py`). | Separate proposal. |

## Why Inventory Is Not the Engine

Pointing the current Inventory at a drive would fail for four reasons:

1. **Population wall.** Inventory admits at most 150,000 rows per population
   ([DEFENSE](DEFENSE.md) capacity policy). The screenshot's `F:` holds about
   422,000 files in about 46,000 folders, more than three times that limit, so
   the scan refuses.
2. **Ledger side effect.** Inventory is durable evidence. A casual space check
   would register a location and write every row. Disk usage belongs outside
   the ledger (feature orthogonality). Untracked ingest sources set the
   precedent: they are scanned in memory, used, and forgotten
   ([FEATURES → Untracked Ingest Sources](FEATURES.md#ingest)).
3. **Ignored artifacts are exactly what eats target space.** The default
   `IgnoreSet` hides `.synctrash`, owned temporary files, `DESKTOP.INI` and
   `THUMBS.DB`. A space scan turns off the trash and temp exclusions (both are
   flags on `IgnoreSet`) and labels those entries as NamiSync-owned.
4. **Unreadable areas are normal at drive scope.** System Volume Information,
   other users' `$RECYCLE.BIN` and `WindowsApps` deny access. The host refuses
   elevated launch, so these areas stay unreadable. They become an explicit
   “unreadable” entry with unknown size, not a failed scan.

The space view therefore gets its own read-only workflow: a new entry point that
uses the scanner module and a pure projection, with no recorder or ledger. The
shared `visible_sequence.py`, sibling ordering and windowed table renderer are
reused. A folder-total sort and Contents column could later be added to
Inventory too, but that is a separate change to the DR-BR-15 sort contract.

## Page

The page has two panes, a frame the compare page may reuse:

- **Left:** the sunburst, centered on the focused folder. A breadcrumb above it
  re-roots the view. Clicking a segment focuses that folder.
- **Right:** a flat table of the focused folder's direct children. Folders are
  listed first by default, or mixed with files when sorted by size. Columns:
  Name, Contents, Size (with a “% of parent” bar), Modified. Double-clicking a
  folder focuses it, as Explorer does.

Hovering a segment highlights its table row, and the reverse. The table is the
accessible source of truth; the chart is a navigator.

## Size

Size is logical (end-of-file) size, the figure Explorer's Properties dialog
shows as “Size”. The Properties action gives the exact “Size on disk” when a
user needs it.

- **No per-file opens.** On Windows, `os.scandir` returns size, modification
  time and attributes from the directory listing itself; `DirEntry.stat()`
  needs no extra call for them. File identity and link count are not in the
  listing. On NTFS the sync scanner therefore calls `lstat` for every entry,
  which opens each one (`modules/scanner.py`, the `entry.stat` /
  `self._backend.lstat` fallback). A space walk needs no file identity, so it
  reads listing data only. Directories still get identity for loop defense:
  about 46,000 opens on `F:` instead of about 468,000. Skipping file opens also
  avoids the per-file cloud-recall question
  ([SCANNER → Cloud availability](SCANNER.md#cloud-availability-and-hydration-boundary)).
  Whether this is a scanner mode or a separate walk is an implementation
  choice. The sync scanner's behavior does not change.
- **Accepted consequences:**
  - Hard links are counted once per path, as in Explorer's “Size”.
  - Online-only cloud files show their full logical size. Their row already
    carries the cloud indicator.
- **Probe before implementation.** For rigor, measure logical size against
  allocated size, and check that directory-listing sizes match `lstat`, on
  these cases:
  - a file being written (NTFS updates directory-entry sizes lazily);
  - NTFS- and WOF-compressed files;
  - sparse files;
  - block-cloned (ReFS) or deduplicated files;
  - tiny files stored inside the MFT;
  - hard links;
  - online-only cloud placeholders.

  Record results in PERFORMANCE. A surprising divergence reopens this decision.
- **Volume summary.** For a volume root, the page shows used space from
  `GetDiskFreeSpaceExW` next to the scanned total. The two use different units
  (allocated versus logical), so the difference is described as “not accounted
  for” rather than computed as an exact remainder.

## Scale

No Windows API returns a folder's recursive size. Explorer's Properties dialog
walks the tree itself, and reading the MFT directly needs elevation, which a
Store app would not have had. Spaceketeer almost certainly walked too. The walk
is unavoidable; what matters is what gets retained.

- **Retain directories only.** Keep a compact aggregate tree: one entry per
  directory with its parent, name, and subtree totals for files, folders and
  bytes. Also keep each directory's direct-file count and bytes. Memory then
  grows with the number of directories (about 46,000 on `F:`), not the number
  of files. The sunburst needs only this tree.
- **Read files when a folder is focused.** The flat table re-enumerates the
  focused directory's direct entries. Its folder rows come from the aggregate
  tree. If the fresh direct-file total differs from the scanned one, the header
  says “Changed since scan” and offers Rescan for that folder, instead of
  silently mixing two snapshots.
- **Bounds.** Directory count and direct entries per directory each need a
  wall, sized from measurement (directory-heavy shapes such as `node_modules`
  matter). The table still serves 1..256-row windows over a server-sorted
  directory.
- **Measurement first.** PERFORMANCE should record walk time and peak memory on
  a large real volume (the screenshot's `F:` is a good profile), comparing the
  listing-only walk with the sync scanner's per-entry `lstat`.

## Chart

Drawing a sunburst is cheap: hand-written SVG arc paths, with no third-party
chart library. That keeps the packaged-document and closed-asset rules intact.

- **Server layout, top children only.** Lay the chart out on the server from
  the focus folder, about 4 rings deep.
  - In each ring, draw only the largest *N* child folders (about 5) whose share
    passes a threshold (for example 2% of the focus folder).
  - Each parent's total comes from the aggregate tree, so everything not drawn
    is simply parent total minus drawn children. That remainder includes the
    parent's direct files and every small or unranked folder, and it appears as
    a neutral arc, much as Spaceketeer left it unfilled.

  No separate merge pass exists, and the payload size is fixed by
  *N* × depth.
- **Accessibility.** The chart is `aria-hidden` and supplementary. The table,
  breadcrumb and keyboard focus carry the same navigation. Forced colors use
  system colors with outlines.
- **Palette (open).** Spaceketeer gave each top-level branch its own hue. That
  conflicts with NamiSync's reserved semantic hues
  ([FEATURES → Semantic Color Channels](FEATURES.md#desktop-ui)). The proposed
  default is a single accent or neutral lightness ramp by depth, with the
  hovered or focused path emphasized. A categorical palette needs an explicit
  product-author decision.

## Session behavior

- **Waiting for a volume.** A space scan takes ordinary volume custody and
  queues behind any session that holds the volume. While waiting, the page
  names the blocking task (with a link) and says: “Waiting for *task* to finish
  on F:. Pausing it lets this scan run now; it resumes after the scan.” This
  matches existing behavior: pausing releases custody, and a resumed session
  re-enters the back of its volumes' queue
  ([FEATURES → Resume Never Preempts](FEATURES.md#dispatcher)). The dispatcher
  stays domain-blind; the adapter maps the blocking session to its task.
- **Cancel and Rescan, no Pause.** A read-only scan has no continuation worth
  keeping.
- **Settled-only first.** The chart appears when the scan completes, matching
  inventory's no-partial publication. A progressive chart is a later option.

## Shell actions

These are now a separate cross-page proposal ([M2_PROPOSAL → Shell
actions](M2_PROPOSAL.md)), which the space view consumes. The remaining work is
mostly policy. The plumbing is modest.

- **Plumbing.** The folder picker is already a host-side callable injected into
  the web adapter. Each action follows the same pattern: a bridge command
  carries a server-owned node id, the server resolves it to a path, and a host
  callable acts. The browser never supplies path text. Primitives:
  - Copy Path: host clipboard.
  - Open in Explorer: `SHOpenFolderAndSelectItems`.
  - Properties: `SHObjectProperties` on a COM-initialized (STA) host thread.
  - Never `ShellExecute` “open” on a file: that would launch it.

  Each command needs BRIDGE ingress bounds and a DEFENSE note for the new
  external effect.
- **Plan side policy (proposed).** Plan rows can describe two paths. A silent
  default makes copies point at the source and everything else at the target,
  and that is the confusion to avoid. The proposal is to never choose
  implicitly:
  - The row menu shows explicitly labelled actions, “Source: Open in Explorer”
    and “Target: Open in Explorer”.
  - Each label is offered only when that side's path exists now. For example,
    a planned copy has no target file yet, so it gets “Target: Open folder” if
    the parent exists.
  - Move rows label the previous and new paths the same way.
  - Plan has no double-click shell default. One-sided pages (Inventory, this
    page, the compare page's per-side tables) may use double-click, because
    the side is unambiguous.
- **Missing items.** Missing items get no Open or Properties actions; “Open
  containing folder” appears when the parent exists. Copy Path stays available,
  because the text is harmless and useful for finding the file. This is a
  proposed refinement of the user's rule.
- **Mutation boundary.** Explorer and the Properties dialog let the user change
  files outside NamiSync. That is the user's own action, as with any Explorer
  use. NamiSync performs none itself and adds no delete, move or cleanup path.

## Non-Goals

- No delete, move, or cleanup from this view. Mutation inside a managed root
  stays pipeline-only (plan → preflight → execute).
- No ledger writes, recents, history runs or background or scheduled scans.
- No elevation and no MFT or USN reading. The future
  [Change-Journal Scanning](FEATURES.md#scanner) protocol is the lawful route
  to faster rescans.
- No duplicate finder (content dedup belongs to ingest) and no network shares
  (remote roots are refused by admission).

## Related Proposals

- **Compare page** ([M2_PROPOSAL](M2_PROPOSAL.md)). “What exists in A and B,
  and how do they differ”. It still needs its own outcome definition.
- **Checksum adoption** ([M2_PROPOSAL](M2_PROPOSAL.md)). It can be run from the
  compare page or from sync execution. It does not belong on this page, which
  writes no ledger state.

## Open Questions

1. Sunburst palette: depth ramp (proposed) or a categorical palette.
2. Whether the Plan capacity link (“See what's using target space”, opening
   this page on the target with `.synctrash` highlighted) belongs in the first
   slice or later.
3. Ring count, *N* and the threshold. Tune these on real volumes.
4. Wall values, after measurement.

## Suggested Slices (Not Commitments)

1. Size-case probes and the walk measurement (listing-only versus per-entry
   `lstat`), recorded in PERFORMANCE.
2. Read-only space workflow, aggregate tree and page:
   - flat table and breadcrumb;
   - trash and temps visible and labelled;
   - unreadable and not-accounted-for entries;
   - visible wait-for-volume notice.
3. Sunburst navigator.
4. Shell actions on every page (separate proposal; can ship before slices 1–3).
5. Plan capacity link.
