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

The goal is not a pie chart. Users ask **“what is using space here, and where
do I go to act on it?”** Inside NamiSync the question also comes up without
being asked:

- Plan review reports a capacity shortfall on the target, and the user needs to
  know what to clear.
- `.synctrash` and displaced update versions grow on the target. Nothing shows
  how much space they use until a trash retention policy exists
  ([FEATURES → Trash Retention Policy](FEATURES.md#data-protection)).
- Before a first sync, the user wants to see the shape of a source tree.

A disk-usage view that answers these questions supports the product's
existing purpose. As a standalone utility it would be scope drift.

## Decisions (2026-11-15)

| Question | User direction | Consequence |
| --- | --- | --- |
| Placement | A new page. It may share a proposed two-pane “compare” page: the sunburst takes one table's space and a file table sits beside it. | See [Page](#page). Only the layout is shared, so the space view does not wait for compare semantics to be designed. |
| Size meaning | Prioritize space on disk. | On-disk size drives the sort and the chart; logical size is secondary. This needs a new enumeration backend; see [Size](#size). |
| Shape and scale | Spaceketeer-like: one flat level of files and folders, and a few-ring sunburst of folders with a segment cap. | The whole tree is still walked, but only directory aggregates are retained, so the 150,000-row inventory wall stops mattering; see [Scale](#scale). |
| Volume custody | Wait. Say so visibly, so the user can choose to pause a sync on that volume. | No new dispatcher custody mode; see [Session behavior](#session-behavior). |
| Chart | Sunburst; drawing it is cheap. | Agreed for rendering. The remaining cost is layout bounds, accessibility and palette; see [Chart](#chart). |
| Copy Path, Open in Explorer, Properties | Wanted on every page regardless of this feature; click-through integration is nice to have. | Moved to a separate proposal ([M2_PROPOSAL → Shell actions](M2_PROPOSAL.md)). Cost notes are under [Shell actions](#shell-actions). |

## What Exists Today

| Spaceketeer capability | NamiSync now | Gap |
| --- | --- | --- |
| Recursive walk of a folder or whole drive | Scanner FULL scan. Volume roots are admissible locations (displayed as “Volume root”). | Records only logical size. |
| Per-folder total size | Inventory projection rolls up complete file bytes. Overflow and unknown bytes are explicit, never clamped ([INVENTORY](INVENTORY.md#stage-6-desktop-contracts-protocol-subset-active)). | Logical bytes only. Requires a ledger-backed inventory. |
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

The page has two panes with the same frame as the proposed compare page:

- **Left:** the sunburst, centered on the focused folder. A breadcrumb above it
  re-roots the view. Clicking a segment focuses that folder.
- **Right:** a flat table of the focused folder's direct children (folders
  first by default, or mixed when sorted by size). Columns: Name, Contents,
  On disk (with a “% of parent” bar), Size, Modified. Double-clicking a folder
  focuses it, as Explorer does.

Hovering a segment highlights its table row, and the reverse. The table is the
accessible source of truth; the chart is a navigator.

The compare page's own purpose (two folders side by side? two scans of one
folder over time?) is undefined. The space view should share only its layout,
so neither feature blocks the other.

## Size

On-disk size is the primary measure. The current scanner uses `os.scandir`,
which exposes only logical size.

- **Backend.** Enumerate each directory through its handle with
  `GetFileInformationByHandleEx(FileIdBothDirectoryInfo)` or the equivalent
  `NtQueryDirectoryFile` class. Each entry then carries `AllocationSize`,
  `EndOfFile`, attributes and file ID without opening the file. That avoids
  per-file opens and the cloud-recall risk that comes with them
  ([SCANNER → Cloud availability](SCANNER.md#cloud-availability-and-hydration-boundary)).
  It is a new native backend with its own containment, long-path and
  no-follow evidence. Sync scans keep `os.scandir` until that backend is
  separately measured and accepted for them.
- **Known inaccuracies, to be disclosed rather than hidden:**
  - NTFS updates directory-entry sizes lazily, so a file being written can
    show stale sizes.
  - Files compressed with NTFS or WOF can report allocation that differs
    from their true physical usage. An optional second pass could use
    `GetCompressedFileSizeW`, but it opens each file by path.
  - Block-cloned (ReFS) and deduplicated files share extents, so per-file
    allocation overcounts.
  - Tiny files stored inside the MFT report zero allocation.
- **Hard links** are counted once per file ID and disclosed as “N hard-linked
  files counted once”.
- **Cloud placeholders** show their real local allocation, which is often zero.
  This is the honest answer for disk usage.
- **Reconciliation.** For a volume root, the page shows used space from
  `GetDiskFreeSpaceExW` next to the known on-disk total. The difference is shown
  as “not accounted for”: unreadable folders, metadata, shadow copies and
  similar.

## Scale

No Windows API returns a folder's recursive size. Explorer's Properties dialog
walks the tree itself, and reading the MFT directly needs elevation, which a
Store app would not have had. Spaceketeer almost certainly walked too. The walk
is unavoidable; what matters is what gets retained.

- **Retain directories only.** Keep a compact aggregate tree: one entry per
  directory with its parent, name, and the subtree totals for files, folders,
  on-disk bytes and logical bytes. Also keep each directory's direct-file count
  and bytes. Memory then grows with the number of directories (about 46,000 on
  `F:`), not the number of files. The sunburst needs only this tree.
- **Read files when a folder is focused.** The flat table re-enumerates the
  focused directory's direct entries using the same backend. Its folder rows
  come from the aggregate tree. If the fresh direct-file total differs from the
  scanned one, the header says “Changed since scan” and offers Rescan for that
  folder, instead of silently mixing two snapshots.
- **Bounds.** Directory count and direct entries per directory each need a
  wall, sized from measurement (directory-heavy shapes such as `node_modules`
  matter). The table still serves 1..256-row windows over a server-sorted
  directory.
- **Measurement first.** PERFORMANCE should record walk time and peak memory
  on a large real volume (the screenshot's `F:` is a good profile) for the new
  backend against `os.scandir`, before any wall value is chosen.

## Chart

Drawing a sunburst is cheap: hand-written SVG arc paths, with no third-party
chart library. That keeps the packaged-document and closed-asset rules intact.
The remaining work is elsewhere:

- **Server layout.** Compute the layout on the server from the focus folder.
  - Use folders only, about 4 rings deep.
  - Merge segments below a minimum angle into “N smaller folders”.
  - Cap the total segment count (a few hundred).
  - Leave a parent's direct-file bytes as visible unfilled arc, as Spaceketeer
    did.

  The payload is bounded like any other bridge response.
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
actions](M2_PROPOSAL.md)). The space view consumes them. Code has not been
built or measured, but inspection suggests moderate cost:

- **Pattern exists.** The folder picker is a host-side callable injected into
  the web adapter and bound to the window. Shell actions would follow the same
  pattern: a bridge command carries a server-owned node id, the server resolves
  it to an absolute path, and an injected host callable performs the action.
  The browser never supplies path text.
- **Per-page work.** Each page needs node-to-path resolution:
  - Plan rows have a source and a target side, and prior-path rows, so the
    action needs a side choice.
  - Missing Inventory rows open the parent folder instead.
  - Each command also needs BRIDGE ingress bounds and DEFENSE notes for the
    new external effect.
- **Primitives.**
  - Copy Path uses the host clipboard (`SetClipboardData`), so the browser
    never needs the full path.
  - Open in Explorer uses `SHOpenFolderAndSelectItems`. That avoids command-line
    quoting and Explorer's weak handling of `\\?\` paths.
  - Properties uses `SHObjectProperties` on the host window. It needs a
    COM-initialized (STA) thread.
  - Never use `ShellExecute` “open” on a file: that would launch it.
- **Mutation boundary.** Explorer and the Properties dialog let the user change
  files outside NamiSync. That is the user's own action, as with any Explorer
  use. NamiSync performs none itself and adds no delete, move or cleanup path.
- **Click-through** (double-click or context menu on any row) is mostly
  presentation once the commands exist. Plan rows need the side choice.

## Non-Goals

- No delete, move, or cleanup from this view. Mutation inside a managed root
  stays pipeline-only (plan → preflight → execute).
- No ledger writes, recents, history runs or background or scheduled scans.
- No elevation and no MFT or USN reading. The future
  [Change-Journal Scanning](FEATURES.md#scanner) protocol is the lawful route
  to faster rescans.
- No duplicate finder (content dedup belongs to ingest) and no network shares
  (remote roots are refused by admission).

## Open Questions

1. The compare page's purpose, if it should become its own proposal.
2. Sunburst palette: depth ramp (proposed) or a categorical palette.
3. Whether the Plan capacity link (“See what's using target space”, opening
   this page on the target with `.synctrash` highlighted) belongs in the first
   slice or later.
4. Wall values, after measurement.

## Suggested Slices (Not Commitments)

1. Native directory-handle enumeration with on-disk size, plus PERFORMANCE
   measurement on a large real volume.
2. Read-only space workflow, aggregate tree and page:
   - flat table and breadcrumb;
   - trash and temps visible and labelled;
   - unreadable and not-accounted-for entries;
   - visible wait-for-volume notice.
3. Sunburst navigator.
4. Shell actions on every page (separate proposal; can ship before slices 1–3).
5. Plan capacity link.
