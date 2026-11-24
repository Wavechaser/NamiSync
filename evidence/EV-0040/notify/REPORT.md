# M2-A2 spike: completion notification

Written by the orchestrator from the builder's final report; the builder's own
write of this file was refused.

## Method

- Windows PowerShell 5.1 for toast probes (only it projects WinRT types directly);
  taskbar calls through Win32/COM via Add-Type.
- Writes: this folder, and the user-approved key
  `HKCU\Software\Classes\AppUserModelId\NamiSync.Spike`, removed in `finally`
  and verified absent from a separate process.
- `History.Clear` was run on the spike AUMIDs and on Windows PowerShell's own
  AUMID (control), removing the Action Center entries the probes created.
- An attempt to copy `wpndatabase.db` for reading was refused and not done.

## Environment (read-only)

- `SHQueryUserNotificationState` = 5 (accepts notifications).
- `ToastEnabled` and `NOC_GLOBAL_SETTING_*` absent (Windows default: on).
- Do Not Disturb / Focus state unreadable: unknown.
- Primary screen 2194x1234, 48 px bottom taskbar, two monitors.

## Q1 Unregistered toast

| Case | Setting | Show() | History(aumid) count |
|---|---|---|---|
| `NamiSync.Spike.Unregistered`, no process AUMID | blank on first run | ok | 1 |
| same, `SetCurrentProcessExplicitAppUserModelID` hr=0 | 0 Enabled | ok | 2 |
| same, third run | 0 Enabled | ok | 3 |
| PowerShell's registered AUMID (control) | 0 | ok | 1 |

- History persists across processes for the unregistered AUMID.
- `History.GetHistory()` without an AUMID throws 0x80070490 for an unpackaged caller.
- Setting the process AUMID changed no API result.
- No toast was visible in any `CopyFromScreen` capture, including the control,
  and the taskbar itself is missing from captures that cover it: the capture
  method cannot see shell-layer windows here. Visual outcome unconfirmed.

## Q2 Registry-only registration (`register-probe.ps1`, run once, approved)

- Key absent before; DisplayName only, no IconUri.
- Setting 0 before and after; Show() ok; history count 1; captures show no
  toast (same capture limitation). Key removed; confirmed absent.

## Q3 Taskbar flash and progress (unregistered WinForms window, minimized)

- ITaskbarList3: HrInit, SetProgressState (NORMAL, PAUSED, ERROR, NOPROGRESS)
  and SetProgressValue(40/100) all hr=0.
- FlashWindowEx(TRAY|TIMERNOFG) returned False (previous caption state, not an
  error); FlashWindowEx(STOP) True.

## Conclusions (builder's)

1. Unregistered: API calls succeed and Windows records history; banner not
   visually confirmed. Documentation says unregistered desktop apps get no
   proper banner, name or icon (not observed here).
2. Supported minimum: Start menu shortcut with `System.AppUserModel.ID`
   (+ `ToastActivatorCLSID` for activation after exit); Windows App SDK
   automates this. Registry-only AUMID key is the lighter workaround (no
   shortcut, no elevation); accepted without error, banner unconfirmed.
3. Flash and progress work at call level without registration.

## Watched retest (orchestrator, 2026-11-24 16:57–16:58, Do Not Disturb off)

The user watched three toasts: A unregistered AUMID (16:57:48), B Windows
PowerShell's registered AUMID (16:57:58), C registry-only `NamiSync.Spike` key
(~16:58:09, key removed afterwards, verified absent). Banners seen: B and C;
none for A. Setting was Enabled and history recorded all three.

## Follow-up (superseded by the retest above for banner visibility)

- Visual confirmation with a shell-visible capture (computer-use screenshot or
  a person watching), with Focus/DND state checked.
- Whether a registry key is acceptable is a user decision against INTERFACES'
  no-registry stance.

## Rerun (from this folder)

```powershell
powershell.exe -NoProfile -File probe-toast-multi.ps1 -SetProc 1 -Tag t1
powershell.exe -NoProfile -File env-state.ps1
powershell.exe -NoProfile -File probe-taskbar.ps1
powershell.exe -NoProfile -File register-probe.ps1
```
