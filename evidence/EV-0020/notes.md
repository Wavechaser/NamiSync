Notes for "Handle-relative compatibility investigation (2026-10-21)": text files chosen from `build/handle-relative-investigation-20261021/`, verbatim, each under an H1 naming its source path. Non-Markdown files are fenced. JSON is in `data.json`.

# `build/handle-relative-investigation-20261021/cloud/REPORT.md`

# OneDrive metadata visibility — 2026-10-21

**Finding:** strict OBJ_DONT_REPARSE metadata opens do not, by themselves, reject
these real OneDrive cloud entries. Thread-local PHCM_EXPOSE_PLACEHOLDERS reveals
the actual reparse/placeholder attributes in the opened entry and makes current
root admission reject this fixture. A kernel-open-success claim must not be
treated as proof of an ordinary entry. A leaf query does not prove that every
intermediate component was ordinary; thread exposure plus one subject open is
not established as a replacement for the existing descendant checks.

Authorized read root: `H:\OneDrive\NamiSync_OneDrive`. Existing supplied entries
were enumerated and metadata queried; nothing was created, written, renamed,
deleted, read as content, pinned/unpinned, or explicitly recalled. No filesystem
attributes, ACLs, privileges or provider settings were changed. No process
compatibility setter was called; Windows resolved its initial process default
during the first metadata query as documented below. Scripts/receipts alone
were written under this ignored directory.

Native calls requested FILE_READ_ATTRIBUTES only (0x80), sharing7, FILE_OPEN,
OBJ_CASE_INSENSITIVE | OBJ_DONT_REPARSE (0x1040), FILE_OPEN_NO_RECALL (0x400000),
without FILE_OPEN_REPARSE_POINT. Queried same-handle basic, standard and tag info;
never content. Directory enumeration is bounded to128 entries/directory,
16 directories and depth3; five real entries were observed. Reparse directories
were not recursively enumerated. Known exact nested filenames from default-mode
enumeration were separately metadata-probed under exposure.

## Raw observations

[run-02-host.json](run-02-host.json), exit0, elapsed0.230s under90s containment:
default-mode online files show attrs0x400020 (recall-on-data-access, no exposed
reparse), zero allocation and their logical size. Downloaded files show0x20
and positive allocation. Root/subfolder show0x10. All strict absolute-root and
relative-subject opens succeed, including online and downloaded nested files.
Before/after directory metadata, sizes and timestamps match exactly. Allocation
was only queried after a strict metadata open succeeded. No content was read.

[mode-01-host.json](mode-01-host.json), exit0, elapsed0.273s under90s containment,
uses RtlSetThreadPlaceholderCompatibilityMode(2) and restores its returned prior
mode0 in finally; query confirms restoration. Real same-handle and enumeration
metadata under PHCM_EXPOSE:

| Entry | Exposed attributes | Reparse tag | Allocation bytes |
| --- | --- | --- | ---: |
| Supplied root | 0x410 | 0x9000601a | 4096 |
| root download.TIF | 0x420 | 0x9000601a | 61632512 |
| root online.dng | 0x401620 | 0x9000401a | 0 |
| subfolder | 0x410 | 0x9000601a | 0 |
| subfolder download.jpg | 0x420 | 0x9000601a | 6508544 |
| subfolder online.TIF | 0x401620 | 0x9000401a | 0 |

All strict raw opens still succeed under exposure. The ancestor
`H:\OneDrive` has attrs0x431 and tag0x9000701a and also strict-opens successfully.
These findings differ from the real junction corpus returning C000050B; no
claim is made that OBJ_DONT_REPARSE refuses every cloud tag.

**Actual current root admission was tested**, separately from raw-open feasibility:
admit_root(RootAuthority(supplied_root)) succeeds in default mode, rejects with
RootAuthorityError `path contains a reparse component` under exposure, and
succeeds again after restoration. Therefore this is production-reachable hidden
metadata, not merely a low-level diagnostic bypass. Exposure reveals both
downloaded and online cloud entries as reparse, and the supplied configured root
is itself reparse. Under the existing ordinary-root/reparse rejection policy this
root is refused; these receipts do not authorize accepting hydrated cloud roots
or bypassing ancestor admission. The existing default-mode visibility gap is a
separate pre-existing observation; these read-only probes demonstrate no harmful
effect or hydration. The parent selected the authorized PO4 path rather than
introducing an additional intermediate-component algorithm for this candidate.

After restoration, default-mode before/after metadata matches exactly, including
online flags, sizes and timestamps. Successful online metadata handles retained
zero allocation. This is evidence against observed hydration, not a network
trace, provider-wide guarantee, or permission for content access.

## Thread mode and provenance

The official [RtlSetThreadPlaceholderCompatibilityMode documentation](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntifs/nf-ntifs-rtlsetthreadplaceholdercompatibilitymode)
defines signed CHAR input/return, EXPOSE=2, previous mode return and negative
errors. It describes per-thread override of application default, with reparse,
sparse and offline characteristics exposed by enumeration/information queries.
The probe binds c_byte and preserves/restores the returned old thread mode.
The companion [thread query API](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntifs/nf-ntifs-rtlquerythreadplaceholdercompatibilitymode)
verifies current mode. No process setter is called.

[mode-order-01-host.json](mode-order-01-host.json), exit0, elapsed0.176s, isolates
the observed process query value change: startup thread0/process0; first root
metadata enumeration resolves process1 **before any thread setter**; setting
thread2 leaves process1; restoring thread0 also leaves process1. This supports
lazy application compatibility selection, not a process-policy mutation by the
thread setter. All mode changes occurred only in short-lived probe children.

Python3.13.14 AMD64, Windows11 build26200. Admission observed H: NTFS serial
4CA163D1, label WD Blue SN550. Each driver JSON retains exact command,90-second
timeout, stdout/stderr, exit and elapsed time. Script hashes are embedded in raw
receipts; source-identities.json records source and script identities captured
after the investigation. Concurrent parent/builder changes mean this latter
snapshot is not a before/after freeze of every earlier product observation.
The initial run-01 wildcard-preparation failure is retained with its exact
probe_cloud_v1.py source; no content access occurred in that failed run.

Exact successful commands from repository root:

```powershell
./.venv/Scripts/python.exe build/handle-relative-investigation-20261020/probe/run_bounded.py build/handle-relative-investigation-20261021/cloud/probe_cloud.py build/handle-relative-investigation-20261021/cloud/run-02-host.json build/handle-relative-investigation-20261021/cloud/run-02-host
./.venv/Scripts/python.exe build/handle-relative-investigation-20261020/probe/run_bounded.py build/handle-relative-investigation-20261021/cloud/placeholder_mode.py build/handle-relative-investigation-20261021/cloud/mode-01-host.json build/handle-relative-investigation-20261021/cloud/mode-01-host
./.venv/Scripts/python.exe build/handle-relative-investigation-20261020/probe/run_bounded.py build/handle-relative-investigation-20261021/cloud/mode_order.py build/handle-relative-investigation-20261021/cloud/mode-order-01-host.json build/handle-relative-investigation-20261021/cloud/mode-order-01-host
```

All were host-executed for exact user-authorized external read access. No product,
tests or tracked documentation was edited by this investigation lane.

# `build/handle-relative-investigation-20261021/design/report.md`

# Remaining design probes — 2026-10-21

Native local NTFS, same Python/project host as prior study. Production untouched.

ACL fixture: run_acl.ps1 creates unique directory, saves original leaf descriptor,
adds current-SID ReadAttributes denial, probes both observers, and restores in
finally. baseline.json and denied.json show identical complete FileStat in both
routes; original-acl.txt and restored-acl.txt match. This does not establish access
failure parity because neither open was actually denied. Parent enumeration rights
may make this insufficient to induce a denied metadata open. No claim of exhaustive
ACL compatibility follows.

move_probe.py opens task-owned root with full sharing and metadata access, performs
fresh root admission, then renames it and creates replacement at original spelling.
Relative observation returns original object size 8; pathname observation replacement
size 16, distinct file IDs. Original root restored in finally. This isolates handle
object stability after admission; does not exercise production corroboration helper
(which is not implemented). Root move is therefore real, and one-subject permissive
mode must define observation-time object semantics explicitly. No mutation occurred
outside unique task-owned fixture and no sync execution ran.

Suggested lifecycle and status/representation choices are in parent-agent messages;
M1_PLAN owns implementation authorization. Cloud/provider and non-NTFS acceptance
are independent probes; these two receipts do not claim them.

# `build/handle-relative-investigation-20261021/exfat/REPORT.md`

# exFAT compatibility observation — 2026-10-21

**Decision:** the same strict handle-relative subject open works on the authorized
K: exFAT card. Use same-handle FileBasicInfo + FileStandardInfo for common
metadata, with identity omitted for exFAT. FileStatInformation (68) is not a
universal query: present exFAT files/directories returned C000000D
(STATUS_INVALID_PARAMETER), whereas both basic/standard queries succeeded.
This favors one basic/standard metadata algorithm across the supported local
filesystems over a stat68-first optimization requiring query fallback.

Host: Python 3.13.14 AMD64, Windows 11 build26200, HEAD
e6734bbd070eae85113822bb5e2d98a9f21f25bf. Native volume facts: EXFAT,
serial BA1F1F45, label New Volume, component length255. Capability profile:
10ms timestamp granularity, stable identity=false, max_path32767,
ADS=false, hardlinks=false. No identity query was made in the exFAT path.

Raw [run-01-host.json](run-01-host.json) compares current FileStat with native
metadata for ordinary file, directory, absent leaf/parent, nondirectory parent,
370-character existing file and 373-character missing file. For present ordinary
entries all FileStat fields match exactly, including timestamps, attributes,
nlink and identity=None. Both confirmed invocation hold and metadata-only
share7 root acquisition work. The separate read-only
[fresh-01-host.json](fresh-01-host.json) reacquires, fully admits and closes its
metadata root for every subject, confirming the second acquisition mode itself.

Native subject flags: access FILE_READ_ATTRIBUTES (0x80), share7, FILE_OPEN,
OBJ_CASE_INSENSITIVE | OBJ_DONT_REPARSE (0x1040), FILE_OPEN_NO_RECALL (0x400000),
without FILE_OPEN_REPARSE_POINT. No content reads, privilege/ACL changes,
symlink/junction creation or volume setting changes occurred.

Existing semantic caveats remain: absent parent and nondirectory parent both
return raw C000003A; the prototype does not reproduce current error distinction.
It returns FileStat/absence rather than complete StatObservation, so resolved
representability and diagnostic mapping are not established. The test proves
native query compatibility, not complete replacement readiness or root-admission
policy correctness. Neither exFAT nor this fixture proves cloud-placeholder
behavior. Product/test/documentation files were not edited.

Finite warm diagnostic only: three rotated rounds of20 calls/route/subject,
five warmups, reused invocation, no OS cache flush. Raw samples are retained in
run-01-host.json; medians in microseconds:

| Subject | Current | Basic+standard |
| --- | ---: | ---: |
| Shallow existing | 185.055 | 22.915 |
| Shallow missing | 189.600 | 22.535 |
| Deep existing | 645.920 | 35.825 |
| Deep missing | 667.905 | 34.300 |

These omit one-time root setup and complete presentation/error semantics and
are not end-to-end speedup claims or acceptance budgets. Driver receipts record
90-second containment, exit0 and elapsed1.160s /0.172s. Product dependency hashes
were unchanged before/after the main run; script and imported prototype hashes
are retained in the raw evidence. The wrapper script remains unchanged from
2026-10-20.

Exact command from repository root:

```powershell
./.venv/Scripts/python.exe build/handle-relative-investigation-20261020/probe/run_bounded.py build/handle-relative-investigation-20261021/exfat/probe_exfat.py build/handle-relative-investigation-20261021/exfat/run-01-host.json build/handle-relative-investigation-20261021/exfat/run-01-host
```

The follow-up uses the same wrapper with fresh_access.py, fresh-01-host.json and
fresh-01-host respectively. Both ran with host execution for authorized external
fixture access. Initial sandbox Get-Volume failed CIM access; native volume
observation supplied filesystem facts instead, without a system-setting change.

The sole external write root was create-new
`K:\NamiSync-probe-5d4b3b539c3d4e5a8f1fa95568a26e6d`, with AGENTS.md created as
its first file. All generated writes derive from that new UUID root. Direct
source inspection confirms there are no writes/deletes elsewhere on K:;
[fixture-manifest.json](fixture-manifest.json) records the retained three files
and eleven directories below the fixture root. The fresh follow-up made no K:
writes. No assertion is made about unrelated activity by other processes.
No cleanup has run. Keep the exact fixture and raw receipts for review.

# `build/handle-relative-investigation-20261021/final-profile/DESIGN.md`

# Final integrated PO4 observation — prepared, not executed

Execution waits for the parent to identify committed checkpoint b and confirm
tests are idle. measure_final.py is syntax-checked only. It requires explicit
--revision and --tests-idle, checks exact HEAD and clean tracked/untracked
product/test inputs, and never modifies the old fixture/helper/evidence files.

Reuse the unchanged child driver
build/planning-optimization-next-20261019/po4/profile_plan.py and its frozen helper
build/planning-optimization-20261019/helper.py. The child runs real source planning
through service/registry, fresh per-sample databases, completed drain, terminal
release, first256-row window and service shutdown. No sync plan executes.

Population/order: noop90(source8000,target7200) and noop10(source8000,target800),
same fixture paths from fixtures.json. Alternate mixes for one excluded warmup,
three light samples and one separately counted sample per mix: ten serial child
processes total. Each child has the existing helper's240-second Windows Job and
process-tree containment plus the unchanged child's180-second terminal deadline.
Run one child at a time; no concurrent tests, other measurement or source edits.
Parent should poll outer command output with bounded waits during execution.

Outside timing, verify exact expected path sets,32-byte deterministic content,
fixed mtime, file counts and per-side digest before and after; require agreement
with historical04-profile-summary.json digests. Freeze all product files except
pycache, helper, containment Python files, fixture config, historical child and
summary, and the new driver before/after. Capture helper host profile and revision.
Fresh child application databases are under the owned output sample directories,
outside the source/target fixture trees. All logs/receipts remain on failure.

Child assertions verify complete source/target scans, exact population and
COPY/NOOP counts, ready completed plan,256 window rows with matching view revision,
terminal session release and clean ShutdownView complete/custody_released.
Outer validation checks those results plus the exact shutdown representation.
Counts are inclusive instrumentation, not additive wall-time decomposition.
Record root admission/held attributes, chain checks, temp discovery, subject root
and candidate resolutions, and subject final stats using the unchanged child.
Expected deleted resolution sites should yield no observed count; retain raw
counts and validate their applicability against integrated source before claiming
an exact boundary reduction. Do not infer elapsed improvement from counts.

Compare the three light request-to-first-window and observer spans to the
historical integrated PO3/PO5 study (same corpus/helper, different date/source).
This is an integrated warm observation, not a controlled isolated PO4 speedup.
Retain warmup and counted observations but exclude both from light aggregation.
No cold-cache, remote, installed-release, deep-tree or browser claims follow.

Expected command after integration signal, native PowerShell from repository:

```powershell
./.venv/Scripts/python.exe build/handle-relative-investigation-20261021/final-profile/measure_final.py --revision <committed-checkpoint-b> --tests-idle
```

Use host execution to match the earlier successful native containment profile;
sandbox may deny Job/native fixture operations. No execution has occurred during
preparation. Dependencies are pre-existing source helper, child driver, fixture
config, two historical8000-file fixture roots, containment helper files, project
venv/dependencies and Windows native host. No new dependencies or product edits.

# `build/handle-relative-investigation-20261021/final-profile/REPORT.md`

# Integrated PO4 final observation — 2026-10-21

Complete against committed checkpoint b17822b1a4f5b660405384e163224b16c447d8e8e.
Run directory: run_c5df5b36a3254270b98b92acbd468846/. No failed samples or reruns.
The source/helper/containment/driver hashes remained equal before/after. Both
complete fixture censuses matched each other and the historical corpus digests:
exact paths,32-byte deterministic content, fixed size/mtime, source8000 files,
target7200 or800 files. No fixture files changed; no plan executed.

One excluded warmup, three fresh-process light samples, and one separately
counted sample per mix ran serially, alternating mixes. All ten yielded complete
scans, expected COPY/NOOP counts (800/7200 or7200/800),8000 operations, ready
preflight with0 refusals, matching first256-row window revisions, terminal
completion/release and complete service shutdown with custody released. Execution
state remained revision0 with no execution session/result; readiness-checks.json
checks this independently from the frozen child's core assertions.

| Three light samples, seconds | Prior90% NOOP | Final90% NOOP | Prior10% NOOP | Final10% NOOP |
| --- | ---: | ---: | ---: | ---: |
| Request to first window range | 2.976–3.052 | 2.626–2.660 | 6.813–6.995 | 3.844–3.917 |
| Request to first window median | 2.995 | 2.633 | 6.891 | 3.847 |
| Current-world observer range | 0.724–0.747 | 0.360–0.364 | 4.925–5.069 | 1.913–1.979 |

The prior study uses the same fixture and unchanged frozen child/helper on this
host with warm cache, but a different date/source. This is a historical integrated
observation, not a controlled isolated causal estimate of PO4 improvement.
Raw light values and input hashes for the comparison are in analysis.json.
Warmup and counted elapsed values are retained but excluded from these ranges.

| Counted boundary calls, prior → final | 90% NOOP | 10% NOOP |
| --- | ---: | ---: |
| Root admission/held attributes | 1684 → 1684 | 14484 → 14484 |
| Descendant chain admission | 1760 → 1760 | 14560 → 14560 |
| Subject root resolution | 1680 → 0 observed | 14480 → 0 observed |
| Subject candidate resolution | 1680 → 0 observed | 14480 → 0 observed |
| Final subject leaf stat | 880 → 1680 | 7280 → 14480 |
| Reclaimable-temp discovery | 1 → 1 | 1 → 1 |

Counts cover the same wrapper boundaries as the historical study, not all native
syscalls. Chain call counts remain the same while excluding the leaf from its
internal walk. Formerly missing subjects now reach the single final authoritative
leaf stat, explaining the increased final-stat count. Confirmed held fixture
roots exercise the resolution-free path; this does not assert fallback resolution
is universally absent. Counted inclusive durations overlap and must not be summed
or subtracted from light wall times.

Host profile: Windows11 build26200, Intel i7-13700K/24 logical processors,
Python3.13.14 AMD64, SQLite3.50.4, NTFS WD Black SN850X1, warm filesystem cache.
Source execution, uncontrolled background/power and three light samples limit
generalization. No cold-cache, remote, deep-tree, installed-release, browser or
new acceptance-budget claims. Tests were idle; each child used the existing
240-second Windows Job/process-tree containment and180-second terminal deadline.
Parent closeout documentation changes are outside the frozen measurement inputs.

Command (host execution, native PowerShell from repository root):

```powershell
./.venv/Scripts/python.exe build/handle-relative-investigation-20261021/final-profile/measure_final.py --revision 17822b1 --tests-idle
```

Exit0. summary.json retains the exact ten child commands; every sample retains
child.log, receipt.json, counts.json and fresh application databases. Product,
fixture, helper and containment identities live in inputs-before/after.json and
fixtures-before/after.json; profile.json records revision/host. analysis.json
records comparison input receipt hashes and raw light/count data. No tracked
product, tests or documentation was edited by this lane. No cleanup occurred.
