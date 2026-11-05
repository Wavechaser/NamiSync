# Latest session — Create batch admission follow-up, 2026-11-05

The user authorized extending the Setup gesture fix to Create batch. Removed
only the editable Source/Target pending exclusions from its start handler.
Queued pairs continue to own their saved paths/options and admission results;
a check on the editable form cannot silently discard the batch click.

Add pair's existing saved-approval behavior is deliberately unchanged: a pair
captured during a recheck can retain the earlier accepted choice. Batch reuses
that saved choice when present, otherwise admits its saved candidate. It does
not wait for or borrow the editable row's promise. Native workflow admission
and explicit review before execution remain independent.

## Verification

Evidence: `build/setup-admission-20261104/batch-followup-20261105/`.
The focused probe fails before the fix and passes afterward for both Source
and Target blur immediately followed by Create batch. It verifies saved
paths/options, one creation/start on repeated activation, batch completion
while the live check remains pending, and independence from its later refusal.
All 2,208 interface-department tests pass, together with three affected installed
Setup/shell cases. Document link and diff checks pass; independent review found
no blocking code issue. Original failed receipts are retained. Native evidence
is archived; both test-owned temporary roots were removed after identity,
archive and process checks. `pytest-cleanup-result-20261105-085625.json` records
cleanup, including unlinking one fixture junction without traversal. Earlier
packaging fixtures and prior round evidence remain untouched.

## Package and resumption context

Latest portable debug package remains
`build/m1-release-20261104/attempt-05/NamiSync-windows-x64-dev.zip`, SHA-256
`be10b5c90915975194d0e4dd72c64434d0164af86ecd3554a86911e0b1fd4162`.
Its source is `939e57c17f8209c2d9c42e45228ba4acb583e149`: it includes the prior
Setup fix but predates this Create batch follow-up. No package was rebuilt here.
Packaging-owned extraction/native profiles are excluded from test cleanup.
Previous first-click diagnostic and cleanup evidence remain under
`build/setup-admission-20261104/`, with product fix `e2f482ae` and diagnostic
closeout `939e57c1`; their result is historical, not a new native single-click
journey for this follow-up. No further native diagnostic or release is implied.

M1_PLAN owns remaining dependency locks, hosted CI, notices/distribution,
resource acceptance and final candidate gates. No push or publication.
