$ErrorActionPreference = 'Stop'
$out = $PSScriptRoot
$plan = Get-Content -LiteralPath (Join-Path $out 'external-cleanup-plan.json') -Raw | ConvertFrom-Json
$remaining = @($plan | Where-Object { Test-Path -LiteralPath $_.Path })
if ($remaining.Count) { throw "$($remaining.Count) fixture roots remain." }
$branches = @(git for-each-ref refs/heads/codex/ '--format=%(refname:short)')
if ($LASTEXITCODE -ne 0 -or $branches.Count) { throw 'codex branches remain or inspection failed.' }
$inventory = Import-Csv -LiteralPath (Join-Path $out 'inventory.csv')
$kept = foreach ($path in @('F:\NamiSyncExecutorBenchSource', 'H:\test_dir\source', 'H:\test_dir\target')) {
    $baseline = @($inventory | Where-Object Path -EQ $path)
    if ($baseline.Count -ne 1) { throw "Missing baseline for $path" }
    $pending = [System.Collections.Generic.Stack[System.IO.DirectoryInfo]]::new()
    $pending.Push((Get-Item -LiteralPath $path -Force))
    [long]$files = 0
    [long]$bytes = 0
    while ($pending.Count) {
        foreach ($entry in $pending.Pop().GetFileSystemInfos()) {
            if ($entry.Attributes -band [System.IO.FileAttributes]::ReparsePoint) { throw "Unexpected retained reparse entry: $($entry.FullName)" }
            if ($entry -is [System.IO.DirectoryInfo]) { $pending.Push($entry) }
            else { $files++; $bytes += $entry.Length }
        }
    }
    if ($files -ne [long]$baseline[0].Files -or $bytes -ne [long]$baseline[0].Bytes) { throw "Retained census changed: $path" }
    [pscustomobject]@{ Path=$path; Present=$true; BaselineFileCountAndBytesMatch=$true; Files=$files; Bytes=$bytes }
}
$extraF = @(Get-ChildItem -LiteralPath 'F:\' -Force | Where-Object Name -Like 'NamiSync-resource-*')
$extraH = @(Get-ChildItem -LiteralPath 'H:\test_dir' -Force | Where-Object Name -Like 'NamiSync-resource-*')
if ($extraF.Count -or $extraH.Count) { throw 'External resource roots remain beyond planned set.' }
$receipt = [pscustomobject]@{
    Verified=[DateTimeOffset]::Now.ToString('o'); RemovedRoots=$plan.Count; RemainingCodexBranches=$branches.Count
    RemainingExternalResourceRoots=0; Retained=$kept; Worktrees=@(git worktree list --porcelain)
}
$receipt | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $out 'cleanup-verification.json') -Encoding utf8
$receipt | ConvertTo-Json -Depth 5
