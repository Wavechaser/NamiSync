# Documentation Conventions

Read this before creating or editing a document in `docs/`, README or CHANGELOG.

## Layout

- Active subject documents live in `docs/`. Agent working procedures live in
  `docs/procedures/`. Superseded material belongs in `docs/obsolete/`; it is
  historical reference and must not guide current implementation.
- Root `AGENTS.md` owns always-on repository execution boundaries and routes to
  these procedures. Root `README.md` remains the product/package readme,
  documentation index, roadmap and concise milestone/phase changelog. This
  document owns editing conventions, not a second product index.

Read the section relevant to the document being edited. Update a subject's
existing owner rather than creating parallel authority or copying its rules
into every consumer document.

## Subject ownership

- [ARCHITECTURE.md](../ARCHITECTURE.md) owns durable decisions, contracts, layering,
  coordination, invariants, type/protocol meaning and milestone direction.
  Exact fields, enums, inheritance, protocols and signatures belong to the
  owning core symbol. Keep the contract-to-source locator current; reproduce
  exact shapes only when needed to explain an architectural decision. Module
  docs explain use/extension policy without redefining shapes. Put dated
  status, acceptance results, measurements and implementation walkthroughs in
  the changelog, delivery plan or owning component document.
- [DEFENSE.md](../DEFENSE.md) is normative for supported assumptions, trusted
  boundaries, hard walls, tolerances, quantitative evidence, residual-risk
  dispositions and model-reopen triggers. Other documents link to its policy
  and describe their own mechanisms; they do not restate its tables or accept
  a residual merely by describing it.
- [FEATURES.md](../FEATURES.md) owns product behavior and distinguishes active
  from unrealized outcomes, without milestone build recaps. It links any
  limitation to its defense disposition.
- Component and module documents own implemented component policy,
  operation-specific mechanisms, algorithms, local tests, current state, limits
  and extension policy that do not redefine a cross-cutting defense or bridge
  contract. [BRIDGE.md](../BRIDGE.md) owns protocol and transport: exact desktop
  envelopes, commands, wire behavior, limits and acceptance gates beneath
  DEFENSE §4's trusted-base decision. [PRESENTATION.md](../PRESENTATION.md) owns
  views and focused scale criteria; [INTERFACES.md](../INTERFACES.md) owns
  host/lifecycle and release criteria.
- [BUGS.md](../BUGS.md) owns concrete defect incidents, fixes and severity, and
  its entry conventions. Keep entries module-first, roughly 6–12 rendered lines,
  retaining consequence, cause, fix and only the residual/test detail needed to
  identify the technical boundary. Categories end in a reusable mechanism noun;
  severity follows the worst supported product consequence, not the audit or
  gate that found it.
- [M2_PLAN.md](../M2_PLAN.md) is the sole active delivery plan and register.
  A completed milestone's register moves to `obsolete/` (M1's is
  [M1_REGISTER](../obsolete/M1_REGISTER.md)). Archive superseded plan ancestry
  rather than maintaining parallel current authorities.
- [PERFORMANCE.md](../PERFORMANCE.md) owns measurement methods, fixture/profile
  and scaling descriptions, aggregation, provenance and results. Component
  documents own their behavior and acceptance decisions; DEFENSE owns evidence
  authority and consequence. Reporting an observation neither classifies
  consequence nor changes an acceptance gate.
- [CHANGELOG.md](../../CHANGELOG.md) owns dated task outcomes, including dated
  adoption or revision of DEFENSE policy.
- [HANDOFF.md](../HANDOFF.md) covers only the latest session: changes, verification
  and immediate operational context. Replace it rather than accumulating a
  project reference or transcript; retain necessary resumption/evidence pointers.

## Changelogs

Both root changelogs are newest-first. [CHANGELOG.md](../../CHANGELOG.md)'s
header owns heading levels, task entries, date ranges and milestone/version
naming. README has only `##` milestone/release and `###` phase summaries, never
task entries.
