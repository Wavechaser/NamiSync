Notes for "Verify follow scheduling (2026-11-07)": text files chosen from `build/verify-follow-20261107/`, verbatim, each under an H1 naming its source path. Non-Markdown files are fenced. JSON is in `data.json`.

# `build/verify-follow-20261107/review/follow-retirement.txt`

````text
app.js SHA256 e0c020d3f78e7c206b262364c6b6f5ecf690d0419aa64e8494f417a7da5d8af7
prior candidate control cached Go adoptions before another reply [36,296]
prior candidate control Gap adoptions before recovered C settles [296]
corrected candidate cached Go adoptions before another reply [36]
corrected candidate Gap adoptions before recovered C settles []
````

# `build/verify-follow-20261107/review/window-receipt-cause.txt`

````text
default: full page passes, then complete offset 10 with 14 exact items replaces it and fails only overlayCountMatches; retained items = 24
default: missing item fails page coverage, and 24 attached items including out-of-page rows pass old fixture-count check but fail exact page coverage
larger: full page passes, then complete offset 7 with 17 exact items replaces it and fails only overlayCountMatches; retained items = 24
larger: missing item fails page coverage, and 24 attached items including out-of-page rows pass old fixture-count check but fail exact page coverage
````

# `build/verify-follow-20261107/review/window-receipt-durable.txt`

````text
default history.db sha256 6b69b0ee228df5f8abfdcc2e963b2bcf27c6b99545c55e10f5450f1ecfb549dc
default history.db-wal sha256 a7df76cf2f0a9eedc871b65478985e72d4eea8d6c250a14a266ecd30f5368d60
default ledger.db sha256 76e549caf5a5c1dab6a81d7855f9a2c555b3bc721a8eeb589bd925f29d96ddb4
default ledger.db-wal sha256 c3d11ada0862e76dbae28350581facb8073bd197345df4642f788672fdd5224c
default execution=505375e45609471493ef5889f2f19607 ordinary_verify=7579cbe6298c42f5bd73c14bb0e600f9 verified_history_items=24 verified_target_ledger_rows=24 last_verified_path=file-23.txt window_offset=10 window_items=14
larger history.db sha256 6b69b0ee228df5f8abfdcc2e963b2bcf27c6b99545c55e10f5450f1ecfb549dc
larger history.db-wal sha256 83220f3aa7bdad41fd4e9c2eda68bf48671fb139a919318b6b9b7352a795b172
larger ledger.db sha256 76e549caf5a5c1dab6a81d7855f9a2c555b3bc721a8eeb589bd925f29d96ddb4
larger ledger.db-wal sha256 be7832a21b4c24eb11038322836fe51d75a2accab0134ce2f246ae59a8d774e7
larger execution=381298ec99204fe1abab9eba702c0e00 ordinary_verify=f6be3e2f36ff4f2c97d1bfb075e9e086 verified_history_items=24 verified_target_ledger_rows=24 last_verified_path=file-23.txt window_offset=7 window_items=17
````
