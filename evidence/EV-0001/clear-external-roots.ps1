param([switch]$Execute)
$ErrorActionPreference = 'Stop'
$out = $PSScriptRoot
$owners = Import-Csv -LiteralPath (Join-Path $out 'external-root-owners.csv')
$targets = @($owners | Where-Object { [int]$_.Matches -gt 0 })
if ($targets.Count -ne 61) { throw 'Expected exactly 61 reviewed fixture roots.' }
$seen = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
$plan = foreach ($target in $targets) {
    $path = [System.IO.Path]::GetFullPath($target.Path).TrimEnd('\')
    $parent = [System.IO.Path]::GetDirectoryName($path)
    $name = [System.IO.Path]::GetFileName($path)
    if ($parent -notin @('F:\', 'H:\test_dir') -or $name -notmatch '^NamiSync-resource-[a-zA-Z0-9-]+$') {
        throw "Outside approved fixture boundary: $path"
    }
    if (-not $seen.Add($path)) { throw "Duplicate target: $path" }
    $registered = $false
    foreach ($registry in $target.Registries.Split(';')) {
        foreach ($line in Get-Content -LiteralPath $registry) {
            if (($line | ConvertFrom-Json).root -eq $path) { $registered = $true }
        }
    }
    if (-not $registered) { throw "Registry no longer corroborates $path" }
    if (-not (Test-Path -LiteralPath $path)) {
        [pscustomobject]@{ Path=$path; Present=$false; Files=0; Bytes=0; Directories=0 }
        continue
    }
    $pending = [System.Collections.Generic.Stack[System.IO.DirectoryInfo]]::new()
    $pending.Push([System.IO.DirectoryInfo]::new($path))
    [long]$files = 0
    [long]$bytes = 0
    [long]$directories = 0
    while ($pending.Count) {
        $directory = $pending.Pop()
        if ($directory.Attributes -band [System.IO.FileAttributes]::ReparsePoint) { throw "Reparse directory: $($directory.FullName)" }
        $directories++
        foreach ($entry in $directory.GetFileSystemInfos()) {
            if ($entry.Attributes -band [System.IO.FileAttributes]::ReparsePoint) { throw "Reparse entry: $($entry.FullName)" }
            if ($entry -is [System.IO.DirectoryInfo]) { $pending.Push($entry) }
            else { $files++; $bytes += $entry.Length }
        }
    }
    [pscustomobject]@{ Path=$path; Present=$true; Files=$files; Bytes=$bytes; Directories=$directories }
}
$plan | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $out 'external-cleanup-plan.json') -Encoding utf8
$plan | Format-Table Path,Files,Bytes -AutoSize
if (-not $Execute) { return }
$journal = Join-Path $out 'external-cleanup-journal.jsonl'
foreach ($item in $plan) {
    if ($item.Present) {
        $current = Get-Item -LiteralPath $item.Path -Force
        if ($current.Attributes -band [System.IO.FileAttributes]::ReparsePoint) { throw "Changed to reparse root: $($item.Path)" }
        Remove-Item -LiteralPath $item.Path -Recurse -Force
    }
    if (Test-Path -LiteralPath $item.Path) { throw "Root remains: $($item.Path)" }
    [pscustomobject]@{ Path=$item.Path; Absent=$true; Time=[DateTimeOffset]::Now.ToString('o'); Files=$item.Files; Bytes=$item.Bytes } |
        ConvertTo-Json -Compress | Add-Content -LiteralPath $journal -Encoding utf8
    Write-Output "Removed $($item.Path)"
}
$retained = @('F:\NamiSyncExecutorBenchSource', 'H:\test_dir\source', 'H:\test_dir\target')
foreach ($path in $retained) { if (-not (Test-Path -LiteralPath $path -PathType Container)) { throw "Retained directory missing: $path" } }
[pscustomobject]@{ Completed=[DateTimeOffset]::Now.ToString('o'); AbsentRoots=$plan.Count; RetainedRoots=$retained; Files=($plan | Measure-Object Files -Sum).Sum; Bytes=($plan | Measure-Object Bytes -Sum).Sum } |
    ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $out 'external-cleanup-result.json') -Encoding utf8
