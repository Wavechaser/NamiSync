# Documentation Maintenance

Active subject documents live in `docs/`; superseded plans belong in
`obsolete/` and must not guide current implementation. Root `AGENTS.md` owns
repository execution boundaries. Root `README.md` remains the product/package
readme, documentation index, roadmap and concise milestone/phase changelog;
this file owns editing conventions, not a second product index.

Read the section relevant to the document being edited. Update a subject's
existing owner rather than creating parallel authority or copying its rules
into every consumer document.

## Subject Ownership

- [DEFENSE.md](DEFENSE.md) is normative for supported assumptions, trusted
  boundaries, hard walls, tolerances, quantitative evidence, residual-risk
  dispositions and model-reopen triggers. Other documents link to its policy
  and describe their own mechanisms; they do not restate its tables or accept
  a residual merely by describing it.
- [ARCHITECTURE.md](ARCHITECTURE.md) owns durable decisions, contracts, layering,
  coordination, invariants, type/protocol meaning and milestone direction.
  Exact fields, enums, inheritance, protocols and signatures belong to the
  owning core symbol. Keep the contract-to-source locator current; reproduce
  exact shapes only when needed to explain an architectural decision. Module
  docs explain use/extension policy without redefining shapes. Put dated
  status, acceptance results, measurements and implementation walkthroughs in
  the changelog, delivery plan or owning component document.
- [FEATURES.md](FEATURES.md) owns product behavior and distinguishes active
  from unrealized outcomes, without milestone build recaps.
- [BUGS.md](BUGS.md) owns substantive defects and its entry conventions. Keep
  entries module-first, roughly 6–12 rendered lines, retaining consequence,
  cause, fix and essential residual/test context. Categories name reusable
  causal mechanisms; severity follows the worst supported product consequence,
  not the audit or gate that found it.
- [M1_PLAN.md](M1_PLAN.md) is the sole active M1 delivery register. Archive
  superseded plan ancestry rather than maintaining parallel current authorities.
- [HANDOFF.md](HANDOFF.md) covers only the latest session: changes, verification
  and immediate operational context. Replace it rather than accumulating a
  project reference or transcript; retain necessary resumption/evidence pointers.

## Changelogs

Both root changelogs are newest-first. README has only `##` milestone/release
and `###` phase summaries, never task entries. CHANGELOG repeats those levels
and adds dated `####` tasks with concise delivery bullets. Before named releases,
use milestone headings such as `M1`; afterward use version and codename, such as
`v0.1.0 "Gertrud"`.

Before adding a task, decide whether the session advances an existing one;
extend its date range and summary when it does. Put post-delivery work in the
relevant hardening phase rather than appending it to the original feature task.
Update README's changelog synopsis only when the milestone/phase summary changes.
