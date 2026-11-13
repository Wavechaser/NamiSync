# Post-round-5 hold check: worktrees clean, tester set counts, frozen2 proof ZIPs present.
$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
$build = Split-Path $here
$out = [ordered]@{}
foreach ($wt in 'm1-r5-20261111\checkout', 'm1-release-repair-20261110\acceptance-checkout', 'm1-release-repair-20261110\idle-followup-checkout') {
    $s = git -C (Join-Path $build $wt) status --porcelain
    $out[$wt] = if ($s) { "dirty: $(@($s).Count)" } else { 'clean' }
}
foreach ($d in 'm1-r5-20261111\delivery', 'm1-r5-20261111\delivery-package04-draft', 'gui-tuning') {
    $out[$d] = @(Get-ChildItem -LiteralPath (Join-Path $build $d) -Recurse -File -Force).Count
}
$out['build_cleanup_files'] = @(Get-ChildItem -LiteralPath $build -Filter 'build_cleanup_*' -File).Count
$proofs = Import-Csv (Join-Path $here 'round5-manifest.csv') | Where-Object rule -eq 'frozen2' | Select-Object -ExpandProperty proof -Unique
$out['frozen2_proof_zips'] = "$(@($proofs | Where-Object { Test-Path -LiteralPath (Join-Path $build $_) }).Count)/$(@($proofs).Count)"
$out | ConvertTo-Json
