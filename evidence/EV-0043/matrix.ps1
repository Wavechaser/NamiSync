$ErrorActionPreference = 'Stop'
$workspace = $PSScriptRoot
$cases = @(
    @{name='m01-baseline'; maximized=$true},
    @{name='m02-default-first'; default_first=$true},
    @{name='m03-return-zero'; zero_return=$true},
    @{name='m04-top-one'; inset=1; zero_return=$true},
    @{name='m05-top-zero-default-return'; inset=0},
    @{name='m06-top-margin'; margins=@(0,0,64,0); zero_return=$true},
    @{name='m07-stock'; stock=$true; default_first=$true; default_only=$true},
    @{name='m08-candidate'; inset=0; zero_return=$true; pad=$true; correct_carve=$true; native_hit=$true; maximized=$true}
)
$rows = @()
foreach ($case in $cases) {
    $resultPath = Join-Path $workspace "out/$($case.name).json"
    if (Test-Path -LiteralPath $resultPath) { throw "Run already exists: $resultPath" }
    $temporary = Join-Path $workspace 'command-next.json'
    $case | ConvertTo-Json -Compress | Set-Content -LiteralPath $temporary -Encoding utf8
    Move-Item -LiteralPath $temporary -Destination (Join-Path $workspace 'command.json') -Force
    $deadline = [DateTime]::UtcNow.AddSeconds(15)
    while (-not (Test-Path -LiteralPath $resultPath)) {
        if ([DateTime]::UtcNow -gt $deadline) { throw "No result for $($case.name)" }
        Start-Sleep -Milliseconds 200
    }
    Start-Sleep -Milliseconds 200
    $record = Get-Content -LiteralPath $resultPath -Raw | ConvertFrom-Json
    $row = [ordered]@{
        name=$case.name
        config=$case
        geometry=$record.geometry
        dwmHandled=$record.dwm_handled_grid.Count
        hitCodes=@($record.dwm_handled_grid | ForEach-Object { $_[2] } | Sort-Object -Unique)
        buttonPoints=$record.button_points
        titlebarRects=$record.titlebar_rects
    }
    $rows += $row
    Write-Output "$($case.name): DWM handled $($row.dwmHandled) of 600 grid points"
}
$rows | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath (Join-Path $workspace 'out/matrix.json') -Encoding utf8
