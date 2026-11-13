param([switch]$Details)
$ErrorActionPreference = 'Stop'
$outputRoot = $PSScriptRoot
$repoBuild = Split-Path -Parent $outputRoot
$roots = @(
    [pscustomobject]@{ Scope = 'F-root-NamiSync'; Entries = @(Get-ChildItem -LiteralPath 'F:\' -Force | Where-Object Name -Like 'NamiSync*') }
    [pscustomobject]@{ Scope = 'H-test_dir'; Entries = @(Get-ChildItem -LiteralPath 'H:\test_dir' -Force) }
    [pscustomobject]@{ Scope = 'build'; Entries = @(Get-ChildItem -LiteralPath $repoBuild -Force | Where-Object FullName -NE $outputRoot) }
)
if ($Details) {
    $roots = @('m1-release-repair-20261110', 'm1-r4-20261109', 'm1-r5-20261111') | ForEach-Object {
        [pscustomobject]@{ Scope = $_; Entries = @(Get-ChildItem -LiteralPath (Join-Path $repoBuild $_) -Force) }
    }
}
$prefix = if ($Details) { 'detail-' } else { '' }
$rows = [System.Collections.Generic.List[object]]::new()
$issues = [System.Collections.Generic.List[object]]::new()
foreach ($root in $roots) {
    foreach ($entry in $root.Entries) {
        [long]$bytes = 0
        [long]$files = 0
        [long]$directories = 0
        [long]$reparse = 0
        $issueStart = $issues.Count
        $pending = [System.Collections.Generic.Stack[System.IO.FileSystemInfo]]::new()
        $pending.Push($entry)
        while ($pending.Count -gt 0) {
            $item = $pending.Pop()
            try {
                if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
                    $reparse++
                    $issues.Add([pscustomobject]@{ Path = $item.FullName; Kind = 'reparse-skipped'; Detail = [string]$item.Attributes })
                } elseif (($item.Attributes -band [System.IO.FileAttributes]::Directory) -ne 0) {
                    $directories++
                    foreach ($child in $item.GetFileSystemInfos()) { $pending.Push($child) }
                } else {
                    $files++
                    $bytes += $item.Length
                }
            } catch {
                $issues.Add([pscustomobject]@{ Path = $item.FullName; Kind = 'read-error'; Detail = $_.Exception.Message })
            }
        }
        $rows.Add([pscustomobject]@{
            Scope = $root.Scope; Path = $entry.FullName; Bytes = $bytes
            GiB = [math]::Round($bytes / 1GB, 4); Files = $files
            Directories = $directories; ReparseSkipped = $reparse
            Issues = $issues.Count - $issueStart; LastWriteTime = $entry.LastWriteTime.ToString('o')
        })
    }
}
$rows | Export-Csv -LiteralPath (Join-Path $outputRoot ($prefix + 'inventory.csv')) -NoTypeInformation -Encoding utf8
$issues | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $outputRoot ($prefix + 'issues.json')) -Encoding utf8
$summary = @($rows | Group-Object Scope | ForEach-Object {
    [pscustomobject]@{
        Scope = $_.Name; Entries = $_.Count
        Bytes = ($_.Group | Measure-Object Bytes -Sum).Sum
        Files = ($_.Group | Measure-Object Files -Sum).Sum
        Issues = ($_.Group | Measure-Object Issues -Sum).Sum
    }
})
$summary | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $outputRoot ($prefix + 'survey-summary.json')) -Encoding utf8
$summary | Format-Table -AutoSize
$rows | Sort-Object Bytes -Descending | Select-Object -First 25 Scope,GiB,Files,Issues,Path | Format-Table -AutoSize
