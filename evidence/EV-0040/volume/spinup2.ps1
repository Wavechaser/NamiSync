#Requires -Version 7.0
# M2-A2 spin-up probe, latency method. Runs elevated (openSeaChest needs it).
# Uses only openSeaChest_PowerControl --spinDown and --checkPowerMode on verified
# disks. The drive is never polled between spin-down and the timed query: a query
# that touches media blocks for the spin-up (seconds); one served from memory
# returns in microseconds. A positive control (unbuffered 4 KiB read) shows a wake.
param(
    [int] $SettleSeconds = 45,
    [int] $Repetitions = 1
)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$here = $PSScriptRoot
$repo = [IO.Path]::GetFullPath((Join-Path $here "..\..\.."))
$py = Join-Path $repo ".venv\Scripts\python.exe"
$tool = Join-Path $repo "build\openSeaChest-v26.03.2-win-x64\openSeaChest_PowerControl.exe"
$stamp = [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssZ")
$out = Join-Path $here "spinup2-$stamp.jsonl"
$raw = Join-Path $here "spinup2-$stamp.raw.txt"
$drives = @(
    @{ Letter = "M"; Disk = 11; Model = "42AS" },
    @{ Letter = "J"; Disk = 0; Model = "WUH721816ALE6L4" }
)
$queries = @("positive_read", "GetLogicalDrives", "GetDriveTypeW", "GetVolumeInformationW",
    "GetDiskFreeSpaceExW", "CreateFileW0", "device_prop", "seek_penalty",
    "disk_extents", "GetDevicePowerState", "positive_read")

function Invoke-Sea([int] $Disk, [string[]] $Arguments) {
    $text = (& $tool -d "PD$Disk" @Arguments 2>&1 | Out-String)
    Add-Content -LiteralPath $raw -Value ("### PD$Disk " + ($Arguments -join " ") + "`n" + $text)
    return $text
}

function Write-Record($Record) {
    Add-Content -LiteralPath $out -Value ($Record | ConvertTo-Json -Depth 8 -Compress)
}

try {
    foreach ($drive in $drives) {
        $letter = $drive.Letter; $disk = $drive.Disk
        try {
            if ((Get-Partition -DriveLetter $letter).DiskNumber -ne $disk) {
                throw "drive $letter is not on disk $disk"
            }
            if ((Invoke-Sea $disk @("--checkPowerMode")) -notmatch [regex]::Escape($drive.Model)) {
                throw "PD$disk does not report model $($drive.Model)"
            }
            # Does standby hold when nobody polls?
            [void] (Invoke-Sea $disk @("--spinDown"))
            Start-Sleep -Seconds $SettleSeconds
            $mode = ((Invoke-Sea $disk @("--checkPowerMode")) -split "`r?`n" |
                Where-Object { $_ -match "Device is in" } | Select-Object -Last 1)
            Write-Record ([ordered]@{ letter = $letter; standby_check_after_s = $SettleSeconds; mode = "$mode".Trim() })
            Write-Host "$letter standby check: $mode"
            foreach ($rep in 1..$Repetitions) {
                foreach ($query in $queries) {
                    [void] (Invoke-Sea $disk @("--spinDown"))
                    Start-Sleep -Seconds $SettleSeconds
                    $result = & $py (Join-Path $here "spin_query.py") $query $letter | Out-String
                    $record = [ordered]@{ letter = $letter; rep = $rep; query = $query
                        query_result = ($result.Trim() | ConvertFrom-Json) }
                    Write-Record $record
                    Write-Host "$letter $rep $query : $($record.query_result.ms) ms"
                }
            }
        }
        catch {
            Write-Record ([ordered]@{ letter = $letter; failed = $_.Exception.Message })
            Write-Host "FAILED $letter : $($_.Exception.Message)"
        }
    }
    Write-Host "done: $out"
}
finally {
    Write-Host "Window closes in 15 s."
    Start-Sleep -Seconds 15
}
