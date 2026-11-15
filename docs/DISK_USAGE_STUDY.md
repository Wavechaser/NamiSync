# Disk Usage View — Future Feature Study

Status: **study only**, indexed from [M2_PROPOSAL](M2_PROPOSAL.md). Nothing here
is accepted scope, activates implementation, or changes an M1 limit. Open
decisions at the end belong to the user. Inspected revision: `ebf72fbe`
(2026-11-15).

## Prompt

Spaceketeer was a Windows disk-usage viewer. It is no longer distributed: its
Store listing is gone, and its website remains without its web apps or contact
links. It scanned
a drive or folder and showed a sunburst chart next to a Name / Contents
(“N files, M folders”) / Size table. Clicking drilled into a folder, and it
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

## What Exists Today

| Spaceketeer capability | NamiSync now | Gap |
| --- | --- | --- |
| Recursive walk of a folder or whole drive | Scanner FULL scan. Volume roots are admissible locations (displayed as “Volume root”). | None for the walk itself. See the constraints below. |
| Per-folder total size | Inventory projection rolls up complete file bytes. Overflow and unknown bytes are explicit, never clamped ([INVENTORY](INVENTORY.md#stage-6-desktop-contracts-protocol-subset-active)). | Shown in the Size cell only. |
| Contents (“N files, M folders”) | Rollup counters already include descendant row and file counts (`inventory_projection._row_counters`). | No column. |
| Largest-first table | Server-owned sibling sort on Size ([PRESENTATION](PRESENTATION.md#search-filters-sorting-and-follow)). | **Folders cannot be ranked by total.** `sibling_order.sorted_siblings` sorts files first, then folders by their own size, not their aggregate bytes. For disk usage this is the most important gap. |
| Drill-down / breadcrumb | Expand and collapse in a bounded tree. Follow and Go resolve visible ancestors. | No “focus this folder” re-rooting. |
| Chart | None. | New. |
| Rescan | Whole, exact or recursive-folder Refresh. This is already finer than Spaceketeer's. | None. |
| Pause / Resume | Inventory scan is cancel-only (pause unsupported). | Low value. See the recommendation. |
| Copy Path | Listed as a future action ([FEATURES → Inventory Actions](FEATURES.md#desktop-ui)). | Not built. |
| Open in Explorer, Properties | None. | New external shell actions. |
| Chart grows while scanning | Inventory publishes only complete settled views. | New. Possibly unnecessary. |

## Why “Point Inventory at a Drive” Is the Wrong First Answer

1. **Population wall.** Inventory admits at most 150,000 rows per population
   ([DEFENSE](DEFENSE.md) capacity policy). The screenshot's `F:` holds about
   422,000 files in about 46,000 folders, more than three times that limit, so
   the scan refuses with `REFUSED+UNRUN`. Raising the wall is a DEFENSE
   capacity decision, and it needs memory and time evidence under §7.
2. **Ledger side effect.** Inventory is durable evidence. A casual space check
   would register a location, write every row, then mark rows missing and
   reappeared on later scans. Disk-usage curiosity is not integrity evidence.
   It belongs outside the ledger (feature orthogonality). Untracked ingest
   sources set the precedent: they are scanned in memory, used, and forgotten
   ([FEATURES → Untracked Ingest Sources](FEATURES.md#ingest)).
3. **Ignored artifacts are exactly what eats target space.** The default
   `IgnoreSet` hides `.synctrash`, owned temporary files, `DESKTOP.INI` and
   `THUMBS.DB`. A space view must turn off the trash and temp exclusions (both
   are flags on `IgnoreSet`) and label those entries as NamiSync-owned rather
   than user data.
4. **Logical size is not disk usage.** The scanner records logical size only.
   That overstates or misattributes usage in these cases:
   - files with several hard links, counted once per path;
   - sparse, compressed or block-cloned files;
   - online-only cloud placeholders, whose logical bytes are not local
     ([SCANNER → Cloud availability](SCANNER.md#cloud-availability-and-hydration-boundary)).

   DEFENSE already treats apparent size above volume capacity as reachable.
   Spaceketeer most likely showed logical size.
5. **Unreadable areas are normal at drive scope.** System Volume Information,
   other users' `$RECYCLE.BIN` and `WindowsApps` deny access. The desktop host
   refuses elevated launch, so these areas stay unreadable. Today they become
   warnings that make the scan incomplete. A space view needs them as an
   explicit “unreadable” bucket with unknown size, not as a failure.
6. **Bounded transport.** The bridge serves `1..256`-row windows and never ships
   a complete tree to the browser. A chart needs its own bounded,
   server-computed layout payload under [BRIDGE](BRIDGE.md)'s ingress and
   egress contracts.
7. **Color channels are taken.** Hue is reserved for plan intent, lifecycle and
   integrity ([FEATURES → Semantic Color Channels](FEATURES.md#desktop-ui)).
   Spaceketeer used a categorical palette, one hue per top-level branch.
   NamiSync would either use an accent or neutral lightness ramp, or make an
   explicit product-author palette decision.

## Design Options

### Where it lives

- **A. Inventory overlay only.** Add the table improvements to the existing
  Inventory view. This is cheap and also helps inventory users. It does not
  help with whole drives, unmanaged folders or trash, because all of the
  constraints above still apply.
- **B. Ephemeral “Space” task (recommended core).** Setup takes one folder or
  volume root through the existing candidate admission and runs a read-only scan
  with no ledger writes. It produces an in-memory projection that the task
  owns and that is discarded on Close. Layering stays lawful: a new workflow
  composes the scanner with a pure projection, and the shared
  `visible_sequence.py`, sibling ordering and tree renderer are reused.
- **C. Plan capacity link (motivating integration).** When review shows
  capacity guidance, “See what's using target space” opens B on the target root
  with `.synctrash` highlighted. It is information only, with no cleanup action
  ([M2_PROPOSAL → Session cleanup](M2_PROPOSAL.md) stays separate).

### What it shows

Tiers are ordered by value per cost:

1. **Table first (most value).**
   - A *Total size* sort that ranks folders and files together by aggregate
     bytes.
   - An inline “% of parent” bar in the Size cell.
   - A Contents column (files / folders).
   - A “focus folder” action that re-roots the view.

   This reuses the server sort and windows and keeps full accessibility. It
   answers the user goal without any chart.
2. **Chart as navigator, not authority.** The chart is a supplementary pane
   synchronized with the tree. Hover shows name and size. Click equals Go to
   that row. The tree remains the accessible source of truth. The server
   computes the layout from the focus root with:
   - a depth cap of about 4 rings;
   - segments below a minimum angle merged into “N smaller items”;
   - a bounded segment count.

   **Sunburst or treemap?** A sunburst is what the user knows and shows depth
   well, but outer rings overstate area and small labels are unreadable. A
   treemap is area-honest and better for “a few huge files”, but shows
   hierarchy depth poorly. Recommendation: sunburst limited to a few rings from
   a focus root, because drill-down is the main interaction. Reconsider if
   people use it mainly to find large single files.
3. **Size truth.**
   - Count hard-linked identities once and disclose it. The scanner already
     records link count and identity.
   - Optionally report allocated size from directory-handle enumeration
     (`FILE_ID_BOTH_DIR_INFO` carries `AllocationSize` without opening each
     file). This replaces the `os.scandir` backend, so it is a scanner change
     with its own hydration and containment evidence.
   - Show “unaccounted” as volume used space (`GetDiskFreeSpaceEx`) minus known
     bytes when the root is a volume root.

### Scale

Retaining every file record is unmeasured at 400k+ entries. Before choosing,
PERFORMANCE should measure memory and time for both of these approaches:

- **(a)** full per-file retention under a raised, space-scan-only wall;
- **(b)** directory-level aggregates plus the largest K files per directory and
  an “N other files, X bytes” remainder. Memory then grows with the number of
  directories, which still needs its own wall (`node_modules`-shaped trees).

Approach (b) keeps the chart exact at folder level and trades exhaustive leaf
listing for a bound. Reading a folder's direct files again on expand would mix
observation times, so it is not recommended without an explicit staleness label.

### Session behavior

- Cancel and Rescan, no Pause. A read-only scan has no continuation worth
  keeping, and inventory already declares pause unsupported for scans.
- Progressive display (the chart growing during the scan) is optional. Ship
  settled-only first, matching inventory's no-partial publication.
- Volume custody is open (decision 4). A read-only scan queued behind a
  two-hour sync on the same volume is poor UX. Running alongside it adds I/O
  contention and observes a moving tree.

## Non-Goals

- **No delete, move, or cleanup from this view.** Mutation inside a managed root
  stays pipeline-only (plan → preflight → execute). Open in Explorer hands the
  user to Explorer; NamiSync itself never mutates.
- No ledger writes, recents, history runs or background or scheduled scans.
- No elevation and no MFT or USN reading. Tools like WizTree are fast because
  they read the MFT with elevation, and the host refuses elevation. The future
  [Change-Journal Scanning](FEATURES.md#scanner) protocol is the lawful route
  to faster rescans.
- No duplicate finder (content dedup belongs to ingest) and no network shares
  (remote roots are refused by admission).
- No `ShellExecute` “open” on files. Open in Explorer, if accepted, only selects
  a revalidated path resolved from a server-owned node id, never browser text.

## Open Decisions

1. Placement: B + C (recommended), A only, or all three.
2. Size meaning: logical only, allocated only, or both with labels.
3. Population ceiling and retention approach (a) or (b) for ephemeral scans,
   after measurement.
4. Volume custody for read-only scans: queue, or a new shared-read custody mode
   in the domain-blind dispatcher.
5. Chart: sunburst (recommended), treemap or table-only. Also the palette
   decision under the Semantic Color Channels contract.
6. Whether Open in Explorer and Properties become new external shell actions,
   beyond the already-planned Copy Path.

## Suggested Slices (Not Commitments)

1. Table tier on the existing Inventory view: Total size sort, % bar, Contents
   column, focus folder. This changes the DR-BR-15 sort contract, so
   PRESENTATION and BRIDGE are updated first.
2. Ephemeral Space task (B): logical size, trash and temps visible and labelled,
   an unreadable bucket, the unaccounted remainder, and a measured wall.
3. Chart navigator.
4. Size truth (hard-link dedup, allocated size), the Plan capacity link (C),
   and the Copy Path / Open in Explorer actions.
