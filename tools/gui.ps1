#Requires -Version 7.0

[CmdletBinding(PositionalBinding = $false)]
param(
    [Parameter(Position = 0)]
    [ValidateSet("gallery")]
    [string] $Target,

    [ValidateSet("light", "dark", "forced", "reduced")]
    [string] $Mode = "dark"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$script:EvidenceSchema = "namisync-headed-evidence-v1"
$script:EvidenceLimit = 1MB
$script:GalleryOwnerMarker = ".nami-gui-owner"
$script:TailLines = 80

function New-NamiGuiPlan {
    param(
        [Parameter(Mandatory)] [string] $RepositoryRoot,
        [Parameter(Mandatory)] [string] $LocalAppDataRoot,
        [ValidateSet("shell", "gallery")] [string] $Kind = "shell",
        [ValidateSet("light", "dark", "forced", "reduced")]
        [string] $Mode = "dark",
        [string] $OutputToken
    )

    $repository = [IO.Path]::GetFullPath($RepositoryRoot)
    $development = Join-Path (
        [IO.Path]::GetFullPath($LocalAppDataRoot)
    ) "NamiSync-Development"
    $python = Join-Path $repository ".venv\Scripts\python.exe"

    if ($Kind -eq "shell") {
        $child = Join-Path $repository (
            "tests\interfaces\web\_headed_host_child.py"
        )
        $data = Join-Path $development "shell"
        $mutex = "Local\NamiSync.Development.Desktop"
        $title = "NamiSync [Development]"
        return [pscustomobject]@{
            Kind = "shell"
            Mode = $null
            Repository = $repository
            Python = $python
            Child = $child
            Data = $data
            Log = Join-Path $data "logs\namisync.log"
            Output = $null
            OutputToken = $null
            Scenario = $null
            Mutex = $mutex
            LauncherMutex = "Local\NamiSync.Development.Launcher.Desktop"
            Title = $title
            Arguments = [string[]] @(
                $child,
                "--data-dir", $data,
                "--mutex", $mutex,
                "--title", $title
            )
        }
    }

    if (
        [string]::IsNullOrWhiteSpace($OutputToken) -or
        $OutputToken -notmatch "^[A-Za-z0-9-]+$"
    ) {
        throw "gallery launch planning requires a safe output token"
    }
    $normalizedMode = $Mode.ToLowerInvariant()
    $modeRoot = Join-Path (
        (Join-Path $development "gallery")
    ) $normalizedMode
    $data = Join-Path $modeRoot "data"
    $output = Join-Path (Join-Path $modeRoot "output") $OutputToken
    $child = Join-Path $repository (
        "tests\interfaces\web\_component_gallery_child.py"
    )
    $scenario = Join-Path $repository "tests\assets\component_gallery\gallery.js"
    $mutex = "Local\NamiSync.Development.Gallery.$normalizedMode"
    $displayMode = (
        [Globalization.CultureInfo]::InvariantCulture.TextInfo.ToTitleCase(
            $normalizedMode
        )
    )
    $title = "NamiSync Component Gallery [$displayMode] [Development]"
    return [pscustomobject]@{
        Kind = "gallery"
        Mode = $normalizedMode
        Repository = $repository
        Python = $python
        Child = $child
        Data = $data
        Log = Join-Path $data "logs\namisync.log"
        Output = $output
        OutputToken = $OutputToken
        Scenario = $scenario
        Mutex = $mutex
        LauncherMutex = (
            "Local\NamiSync.Development.Launcher.Gallery.$normalizedMode"
        )
        Title = $title
        Arguments = [string[]] @(
            $child,
            "--mode", $normalizedMode,
            "--data-dir", $data,
            "--mutex", $mutex,
            "--title", $title,
            "--evidence-dir", $output,
            "--scenario", $scenario
        )
    }
}

function Start-NamiGuiProcess {
    param(
        [Parameter(Mandatory)] [string] $FilePath,
        [Parameter(Mandatory)] [string[]] $Arguments,
        [Parameter(Mandatory)] [string] $WorkingDirectory,
        [switch] $Announce
    )

    $start = [Diagnostics.ProcessStartInfo]::new()
    $start.FileName = $FilePath
    $start.WorkingDirectory = $WorkingDirectory
    $start.UseShellExecute = $false
    foreach ($key in @($start.Environment.Keys)) {
        if ($key.StartsWith("PYTHON", [StringComparison]::OrdinalIgnoreCase)) {
            [void] $start.Environment.Remove($key)
        }
    }
    $start.Environment["PYTHONUTF8"] = "1"
    foreach ($argument in $Arguments) {
        [void] $start.ArgumentList.Add($argument)
    }
    $process = [Diagnostics.Process]::new()
    $process.StartInfo = $start
    try {
        if (-not $process.Start()) {
            throw "the editable GUI child process did not start"
        }
        $processId = $process.Id
        if ($Announce) {
            Write-Host "Child PID: $processId"
        }
        $process.WaitForExit()
        return [pscustomobject]@{
            ProcessId = $processId
            ExitCode = $process.ExitCode
        }
    }
    finally {
        $process.Dispose()
    }
}

function Test-NamiExactPropertyNames {
    param(
        [Parameter(Mandatory)] [pscustomobject] $Value,
        [Parameter(Mandatory)] [string[]] $Names
    )

    $actual = @($Value.PSObject.Properties | ForEach-Object { $_.Name })
    if ($actual.Count -ne $Names.Count) { return $false }
    foreach ($name in $Names) {
        if ($actual -cnotcontains $name) { return $false }
    }
    return $true
}

function Read-NamiGalleryFinal {
    param([Parameter(Mandatory)] [string] $Path)

    $item = Get-Item -LiteralPath $Path -Force
    if (
        $item.PSIsContainer -or
        ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 -or
        $item.Length -gt $script:EvidenceLimit
    ) {
        throw "gallery final diagnostic is not a bounded regular file"
    }
    try {
        $record = ConvertFrom-Json -InputObject (
            [IO.File]::ReadAllText($item.FullName, [Text.Encoding]::UTF8)
        )
    }
    catch {
        throw "gallery final diagnostic is not valid JSON"
    }
    if (
        $record -isnot [pscustomobject] -or
        -not (Test-NamiExactPropertyNames $record @(
            "milestone", "payload", "schema"
        )) -or
        $record.schema -cne $script:EvidenceSchema -or
        $record.milestone -cne "final" -or
        $record.payload -isnot [pscustomobject]
    ) {
        throw "gallery final diagnostic has an invalid envelope"
    }
    $late = $record.payload.PSObject.Properties["post_ready_failure"]
    $payloadNames = if ($null -eq $late) {
        @("exit_code", "host_returned")
    }
    else {
        @("exit_code", "host_returned", "post_ready_failure")
    }
    if (
        -not (Test-NamiExactPropertyNames $record.payload $payloadNames) -or
        $record.payload.host_returned -isnot [bool] -or
        ($record.payload.exit_code -isnot [int] -and
            $record.payload.exit_code -isnot [long])
    ) {
        throw "gallery final diagnostic has an invalid payload"
    }
    if (
        $null -ne $late -and
        ($late.Value -isnot [pscustomobject] -or
            -not (Test-NamiExactPropertyNames $late.Value @(
                "stage", "type"
            )) -or
            $late.Value.stage -isnot [string] -or
            $late.Value.type -isnot [string])
    ) {
        throw "gallery final diagnostic has an invalid post-ready failure"
    }
    return [pscustomobject]@{
        ExitCode = $record.payload.exit_code
        HostReturned = $record.payload.host_returned
        PostReadyFailure = if ($null -eq $late) { $null } else { $late.Value }
    }
}

function Get-NamiGalleryStatus {
    param(
        [Parameter(Mandatory)] [string] $OutputRoot,
        [Parameter(Mandatory)] [int] $ExitCode
    )

    $problems = [Collections.Generic.List[string]]::new()
    if ($ExitCode -ne 0) {
        [void] $problems.Add("gallery child exited with code $ExitCode")
    }
    $ready = Test-Path -LiteralPath (
        Join-Path $OutputRoot "ready.json"
    ) -PathType Leaf
    $failure = Test-Path -LiteralPath (
        Join-Path $OutputRoot "failure.json"
    ) -PathType Leaf
    $finalPath = Join-Path $OutputRoot "final.json"
    $final = Test-Path -LiteralPath $finalPath -PathType Leaf
    if ($failure) {
        [void] $problems.Add("gallery published failure diagnostics")
    }
    elseif (-not $ready) {
        [void] $problems.Add("gallery did not publish ready")
    }
    if (-not $final) {
        [void] $problems.Add("gallery did not publish final")
    }
    else {
        try {
            $completion = Read-NamiGalleryFinal $finalPath
            if (-not $completion.HostReturned) {
                [void] $problems.Add("gallery host did not return normally")
            }
            if ($completion.ExitCode -ne $ExitCode) {
                [void] $problems.Add("gallery final exit code does not match")
            }
            if ($null -ne $completion.PostReadyFailure) {
                [void] $problems.Add(
                    "gallery failed after ready: " +
                    "$($completion.PostReadyFailure.stage)/" +
                    "$($completion.PostReadyFailure.type)"
                )
            }
        }
        catch {
            [void] $problems.Add($_.Exception.Message)
        }
    }
    return [pscustomobject]@{
        Abnormal = $problems.Count -ne 0
        Summary = if ($problems.Count) {
            $problems -join "; "
        }
        else {
            "gallery child closed after publishing ready/final diagnostics"
        }
    }
}

function New-NamiGalleryOutput {
    param(
        [Parameter(Mandatory)] [string] $OutputRoot,
        [Parameter(Mandatory)] [string] $OwnerToken
    )

    if (Test-Path -LiteralPath $OutputRoot) {
        throw "generated gallery output already exists: $OutputRoot"
    }
    [void] [IO.Directory]::CreateDirectory($OutputRoot)
    $marker = Join-Path $OutputRoot $script:GalleryOwnerMarker
    $bytes = [Text.UTF8Encoding]::new($false).GetBytes($OwnerToken)
    $stream = [IO.File]::Open(
        $marker,
        [IO.FileMode]::CreateNew,
        [IO.FileAccess]::Write,
        [IO.FileShare]::None
    )
    try {
        $stream.Write($bytes, 0, $bytes.Length)
        $stream.Flush($true)
    }
    finally {
        $stream.Dispose()
    }
}

function Assert-NamiGalleryOutputOwnership {
    param(
        [Parameter(Mandatory)] [string] $OutputRoot,
        [Parameter(Mandatory)] [string] $OwnerToken
    )

    $root = Get-Item -LiteralPath $OutputRoot -Force
    if (
        -not $root.PSIsContainer -or
        ($root.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0
    ) {
        throw "gallery diagnostic root is no longer the created directory"
    }
    $markerPath = Join-Path $OutputRoot $script:GalleryOwnerMarker
    $marker = Get-Item -LiteralPath $markerPath -Force
    if (
        $marker.PSIsContainer -or
        ($marker.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 -or
        $marker.Length -gt 128 -or
        [IO.File]::ReadAllText($markerPath, [Text.Encoding]::UTF8) -cne $OwnerToken
    ) {
        throw "gallery diagnostic ownership marker no longer matches"
    }
}

function Remove-NamiGalleryOutput {
    param(
        [Parameter(Mandatory)] [string] $OutputRoot,
        [Parameter(Mandatory)] [string] $OwnerToken
    )

    Assert-NamiGalleryOutputOwnership $OutputRoot $OwnerToken
    $expected = @(
        $script:GalleryOwnerMarker,
        "final.json",
        "ready.json"
    )
    $entries = @(Get-ChildItem -LiteralPath $OutputRoot -Force)
    $actual = @($entries | ForEach-Object { $_.Name })
    if (
        $actual.Count -ne $expected.Count -or
        @($actual | Where-Object { $expected -cnotcontains $_ }).Count -ne 0
    ) {
        throw "unexpected gallery diagnostics prevent cleanup"
    }
    foreach ($entry in $entries) {
        if (
            $entry.PSIsContainer -or
            ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0
        ) {
            throw "non-file gallery diagnostics prevent cleanup"
        }
    }
    $reviewed = @{}
    foreach ($entry in $entries) {
        $reviewed[$entry.Name] = [pscustomobject]@{
            Creation = $entry.CreationTimeUtc.Ticks
            Length = $entry.Length
            Modified = $entry.LastWriteTimeUtc.Ticks
        }
    }
    $markerPath = Join-Path $OutputRoot $script:GalleryOwnerMarker
    Write-Host "Generated gallery cleanup plan:"
    Write-Host "  file: $(Join-Path $OutputRoot 'ready.json')"
    Write-Host "  file: $(Join-Path $OutputRoot 'final.json')"
    Write-Host "  ownership marker: $markerPath"
    Write-Host "  empty directory: $OutputRoot"
    $removed = [Collections.Generic.List[string]]::new()
    try {
        foreach ($name in @("ready.json", "final.json")) {
            $path = Join-Path $OutputRoot $name
            Assert-NamiGalleryOutputOwnership $OutputRoot $OwnerToken
            $current = Get-Item -LiteralPath $path -Force
            $prior = $reviewed[$name]
            if (
                $current.PSIsContainer -or
                ($current.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 -or
                $current.CreationTimeUtc.Ticks -ne $prior.Creation -or
                $current.Length -ne $prior.Length -or
                $current.LastWriteTimeUtc.Ticks -ne $prior.Modified
            ) {
                throw "gallery diagnostic changed after cleanup inspection: $path"
            }
            [IO.File]::Delete($path)
            if (Test-Path -LiteralPath $path) {
                throw "gallery diagnostic remained after delete: $path"
            }
            [void] $removed.Add($path)
            Write-Host "Removed generated gallery diagnostic: $path"
        }
        Assert-NamiGalleryOutputOwnership $OutputRoot $OwnerToken
        $remaining = @(Get-ChildItem -LiteralPath $OutputRoot -Force)
        if (
            $remaining.Count -ne 1 -or
            $remaining[0].Name -cne $script:GalleryOwnerMarker
        ) {
            throw "new gallery diagnostics prevent directory cleanup"
        }
        [IO.File]::Delete($markerPath)
        [void] $removed.Add($markerPath)
        Write-Host "Removed gallery ownership marker: $markerPath"
        [IO.Directory]::Delete($OutputRoot, $false)
        [void] $removed.Add($OutputRoot)
        Write-Host "Removed empty gallery diagnostic root: $OutputRoot"
    }
    catch {
        Write-Warning "Gallery cleanup incomplete."
        if ($removed.Count) {
            Write-Warning "Successfully removed: $($removed -join ', ')"
        }
        else {
            Write-Warning "Successfully removed: none"
        }
        Write-Warning (
            "Remaining root: $(Test-Path -LiteralPath $OutputRoot); " +
            "remaining marker: $(Test-Path -LiteralPath $markerPath)"
        )
        throw
    }
    Write-Host "Generated gallery diagnostics removed."
}

function Get-NamiLogState {
    param([Parameter(Mandatory)] [string] $Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return [pscustomobject]@{ Exists = $false; Length = 0L; Stamp = 0L }
    }
    $item = Get-Item -LiteralPath $Path -Force
    return [pscustomobject]@{
        Exists = $true
        Length = $item.Length
        Stamp = $item.LastWriteTimeUtc.Ticks
    }
}

function Show-NamiLogTail {
    param(
        [Parameter(Mandatory)] [string] $Path,
        [Parameter(Mandatory)] [pscustomobject] $Before
    )

    try {
        if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
            Write-Warning "No GUI log was created at $Path"
            return
        }
        $item = Get-Item -LiteralPath $Path -Force
        if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            Write-Warning "Refusing to read a reparse-point GUI log: $Path"
            return
        }
        if (
            $Before.Exists -and $Before.Length -eq $item.Length -and
            $Before.Stamp -eq $item.LastWriteTimeUtc.Ticks
        ) {
            Write-Warning (
                "This launch did not update the persistent log; old tail:"
            )
        }
        else {
            Write-Host "GUI log tail:"
        }
        foreach ($line in @(Get-Content -LiteralPath $Path -Tail $script:TailLines)) {
            Write-Host $line
        }
    }
    catch {
        Write-Warning "Could not read GUI log tail at ${Path}: $($_.Exception.Message)"
    }
}

function Test-NamiMutexExists {
    param([Parameter(Mandatory)] [string] $Name)

    $handle = $null
    try {
        $handle = [Threading.Mutex]::OpenExisting($Name)
        return $true
    }
    catch [Threading.WaitHandleCannotBeOpenedException] {
        return $false
    }
    finally {
        if ($null -ne $handle) {
            $handle.Dispose()
        }
    }
}

function Enter-NamiLauncherMutex {
    param([Parameter(Mandatory)] [string] $Name)

    $mutex = [Threading.Mutex]::new($false, $Name)
    $owned = $false
    try {
        try {
            $owned = $mutex.WaitOne(0)
        }
        catch [Threading.AbandonedMutexException] {
            $owned = $true
        }
        if (-not $owned) {
            throw "another launcher already owns this development GUI profile"
        }
        return $mutex
    }
    catch {
        if ($owned) { $mutex.ReleaseMutex() }
        $mutex.Dispose()
        throw
    }
}

function Exit-NamiLauncherMutex {
    param([Parameter(Mandatory)] [Threading.Mutex] $Mutex)

    $Mutex.ReleaseMutex()
    $Mutex.Dispose()
}

function Resolve-NamiRelaunchChoice {
    param([AllowNull()] [object] $Value)

    if ($null -eq $Value) { return "quit" }
    if ($Value -isnot [string]) { return "invalid" }
    if ($Value -eq "") { return "relaunch" }
    if ($Value.Trim().Equals("q", [StringComparison]::OrdinalIgnoreCase)) {
        return "quit"
    }
    return "invalid"
}

function Invoke-NamiGui {
    param(
        [AllowNull()] [string] $SelectedTarget,
        [string] $SelectedMode,
        [bool] $ModeWasExplicit,
        [Parameter(Mandatory)] [string] $RepositoryRoot,
        [Parameter(Mandatory)] [string] $LocalAppDataRoot
    )

    if ($ModeWasExplicit -and $SelectedTarget -ne "gallery") {
        throw "-Mode is valid only after the gallery command"
    }
    $kind = if ($SelectedTarget -eq "gallery") { "gallery" } else { "shell" }
    $normalizedMode = $SelectedMode.ToLowerInvariant()
    $newPlan = {
        $token = if ($kind -eq "gallery") {
            $stamp = [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssfffZ")
            "$stamp-$([Guid]::NewGuid().ToString('N'))"
        }
        else {
            $null
        }
        $parameters = @{
            RepositoryRoot = $RepositoryRoot
            LocalAppDataRoot = $LocalAppDataRoot
            Kind = $kind
            Mode = $normalizedMode
            OutputToken = $token
        }
        New-NamiGuiPlan @parameters
    }
    $plan = & $newPlan
    if (-not (Test-Path -LiteralPath $plan.Python -PathType Leaf)) {
        throw (
            "project venv Python is missing at $($plan.Python); create the " +
            "venv and install .[dev] as editable"
        )
    }
    foreach ($required in @($plan.Child, $plan.Scenario)) {
        if (
            $null -ne $required -and
            -not (Test-Path -LiteralPath $required -PathType Leaf)
        ) {
            throw "required editable GUI path is missing: $required"
        }
    }

    $probe = (
        "import pathlib, sys; import namisync; " +
        "root=pathlib.Path(sys.argv[1]).resolve(); " +
        "source=pathlib.Path(namisync.__file__).resolve(); " +
        "raise SystemExit(0 if source.is_relative_to(root) else 3)"
    )
    $probeRun = @{
        FilePath = $plan.Python
        Arguments = @("-I", "-c", $probe, $plan.Repository)
        WorkingDirectory = [IO.Path]::GetTempPath()
    }
    if ((Start-NamiGuiProcess @probeRun).ExitCode -ne 0) {
        throw (
            "the project venv is not editable; run " +
            ".\.venv\Scripts\python.exe -m pip install -e `".[dev]`""
        )
    }

    $launcherMutex = Enter-NamiLauncherMutex $plan.LauncherMutex
    try {
        while ($true) {
            if (Test-NamiMutexExists $plan.Mutex) {
                throw (
                    "the $kind development window is already running; " +
                    "close it before using this foreground launcher"
                )
            }
            if ($kind -eq "gallery") {
                New-NamiGalleryOutput $plan.Output $plan.OutputToken
            }

            Write-Host ""
            Write-Host "Editable preview; not clean-wheel acceptance evidence"
            Write-Host "Title: $($plan.Title)"
            if ($kind -eq "gallery") { Write-Host "Gallery mode: $($plan.Mode)" }
            Write-Host "Source: $($plan.Repository)"
            Write-Host "Python: $($plan.Python)"
            Write-Host "Data: $($plan.Data)"
            Write-Host "Log: $($plan.Log)"
            if ($kind -eq "gallery") {
                Write-Host "Scenario: $($plan.Scenario)"
                Write-Host "Diagnostic output: $($plan.Output)"
            }

            $logBefore = Get-NamiLogState $plan.Log
            $launchError = $null
            try {
                $run = Start-NamiGuiProcess `
                    $plan.Python $plan.Arguments $plan.Repository -Announce
                $childExit = $run.ExitCode
            }
            catch {
                $launchError = $_.Exception.Message
                $childExit = 1
            }
            if ($kind -eq "gallery") {
                $status = Get-NamiGalleryStatus `
                    -OutputRoot $plan.Output -ExitCode $childExit
            }
            else {
                $status = [pscustomobject]@{
                    Abnormal = $childExit -ne 0
                    Summary = "development shell exited with code $childExit"
                }
            }
            if ($null -ne $launchError) {
                $status = [pscustomobject]@{
                    Abnormal = $true
                    Summary = "child process failed to start: $launchError"
                }
            }

            Write-Host "Exit: $childExit"
            Write-Host "Status: $($status.Summary)"
            $logicalExit = if ($status.Abnormal -and $childExit -eq 0) {
                1
            }
            else {
                $childExit
            }
            if ($status.Abnormal) {
                Write-Warning "Development GUI launch was abnormal."
                if ($kind -eq "gallery") {
                    Write-Warning "Gallery diagnostics retained at $($plan.Output)"
                }
                Show-NamiLogTail $plan.Log $logBefore
            }
            elseif ($kind -eq "gallery") {
                try {
                    Remove-NamiGalleryOutput $plan.Output $plan.OutputToken
                }
                catch {
                    Write-Warning (
                        "Gallery cleanup did not complete at $($plan.Output); " +
                        "see the completed/remaining receipt: " +
                        $_.Exception.Message
                    )
                    $logicalExit = 1
                }
            }

            do {
                try {
                    $answer = Read-Host "Press Enter to relaunch or Q to quit"
                }
                catch [System.Management.Automation.PipelineStoppedException] {
                    $answer = $null
                }
                catch [System.Management.Automation.PSInvalidOperationException] {
                    $answer = $null
                }
                $choice = Resolve-NamiRelaunchChoice $answer
                if ($choice -eq "invalid") {
                    Write-Host "Enter relaunches; Q quits."
                }
            } while ($choice -eq "invalid")
            if ($choice -eq "quit") {
                return $logicalExit
            }
            $plan = & $newPlan
        }
    }
    finally {
        Exit-NamiLauncherMutex $launcherMutex
    }
}

if ($MyInvocation.InvocationName -ne ".") {
    try {
        $localAppData = [Environment]::GetFolderPath(
            [Environment+SpecialFolder]::LocalApplicationData
        )
        if ([string]::IsNullOrWhiteSpace($localAppData)) {
            throw "Windows LocalAppData is unavailable"
        }
        $parameters = @{
            SelectedTarget = $Target
            SelectedMode = $Mode
            ModeWasExplicit = $PSBoundParameters.ContainsKey("Mode")
            RepositoryRoot = [IO.Path]::GetFullPath(
                (Join-Path $PSScriptRoot "..")
            )
            LocalAppDataRoot = $localAppData
        }
        exit (Invoke-NamiGui @parameters)
    }
    catch {
        [Console]::Error.WriteLine("gui.ps1: $($_.Exception.Message)")
        exit 2
    }
}
