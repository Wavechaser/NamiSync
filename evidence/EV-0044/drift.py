"""Restore-size drift probe: a bare WinForms Form (no WebView2, no pywebview).

usage: drift.py <variant> [syscmd|state]
variants: plain    stock frame
          nccalc   restored top inset 0, maximized top inset frame_y (EV-0042 baseline)
          nccalc0  top inset 0 in both states (EV-0043 candidate)
Drives two maximize/restore cycles and writes out-<variant>-<driver>.json with every
size-changing WM_WINDOWPOSCHANGING and the managed stack that caused it.
"""
import ctypes
import json
import sys
from ctypes import wintypes
from pathlib import Path

import clr  # pythonnet

clr.AddReference("System.Windows.Forms")
clr.AddReference("System.Drawing")
import System  # noqa: E402
from System.Drawing import Size  # noqa: E402
from System.Threading import ApartmentState, Thread, ThreadStart  # noqa: E402
from System.Windows.Forms import Application, Form, FormStartPosition, FormWindowState, Timer  # noqa: E402

HERE = Path(__file__).resolve().parent
variant = sys.argv[1]
driver = sys.argv[2] if len(sys.argv) > 2 else "syscmd"
FIX = "fix" in sys.argv[3:]
HOOK = "hook" in sys.argv[3:]

user32 = ctypes.WinDLL("user32", use_last_error=True)
comctl32 = ctypes.WinDLL("comctl32")
user32.SetProcessDpiAwarenessContext.argtypes = (ctypes.c_ssize_t,)
user32.SetProcessDpiAwarenessContext(-4)  # per-monitor v2, as pywebview's host is

LRESULT, WPARAM, LPARAM = ctypes.c_ssize_t, ctypes.c_size_t, ctypes.c_ssize_t
SUBCLASSPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, WPARAM, LPARAM,
                                  ctypes.c_size_t, ctypes.c_size_t)
comctl32.SetWindowSubclass.argtypes = (wintypes.HWND, SUBCLASSPROC, ctypes.c_size_t, ctypes.c_size_t)
comctl32.DefSubclassProc.argtypes = (wintypes.HWND, wintypes.UINT, WPARAM, LPARAM)
comctl32.DefSubclassProc.restype = LRESULT
user32.SendMessageW.argtypes = (wintypes.HWND, wintypes.UINT, WPARAM, LPARAM)
user32.SendMessageW.restype = LRESULT
user32.GetWindowLongPtrW.argtypes = (wintypes.HWND, ctypes.c_int)
user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.GetDpiForWindow.argtypes = (wintypes.HWND,)


class NCCALCSIZE_PARAMS(ctypes.Structure):
    _fields_ = [("rgrc", wintypes.RECT * 3), ("lppos", ctypes.c_void_p)]


class WINDOWPOS(ctypes.Structure):
    _fields_ = [("hwnd", wintypes.HWND), ("after", wintypes.HWND), ("x", ctypes.c_int),
                ("y", ctypes.c_int), ("cx", ctypes.c_int), ("cy", ctypes.c_int), ("flags", wintypes.UINT)]


class WINDOWPLACEMENT(ctypes.Structure):
    _fields_ = [("length", wintypes.UINT), ("flags", wintypes.UINT), ("showCmd", wintypes.UINT),
                ("ptMin", wintypes.POINT), ("ptMax", wintypes.POINT), ("rcNormal", wintypes.RECT)]


WM_NCCALCSIZE, WM_WINDOWPOSCHANGING = 0x0083, 0x0046
SWP_NOSIZE = 0x0001
log = []
state = {"hwnd": 0}


def is_max(hwnd):
    return bool(user32.GetWindowLongPtrW(hwnd, -16) & 0x01000000)


def frame_y(hwnd):
    dpi = user32.GetDpiForWindow(hwnd)
    return user32.GetSystemMetricsForDpi(33, dpi) + user32.GetSystemMetricsForDpi(92, dpi)


def rect(hwnd):
    r = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return [r.left, r.top, r.right, r.bottom]


def client(hwnd):
    r = wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(r))
    return [r.right, r.bottom]


def placement(hwnd):
    wp = WINDOWPLACEMENT()
    wp.length = ctypes.sizeof(wp)
    user32.GetWindowPlacement(hwnd, ctypes.byref(wp))
    n = wp.rcNormal
    return [n.left, n.top, n.right, n.bottom]


def managed_stack():
    lines = System.Diagnostics.StackTrace(False).ToString().splitlines()
    return [ln.strip() for ln in lines if "System.Windows.Forms" in ln][:16]


def proc(hwnd, msg, wp, lp, uid, ref):
    try:
        if msg == WM_NCCALCSIZE and wp and variant != "plain":
            p = ctypes.cast(lp, ctypes.POINTER(NCCALCSIZE_PARAMS)).contents
            top = p.rgrc[0].top
            res = comctl32.DefSubclassProc(hwnd, msg, wp, lp)
            inset = frame_y(hwnd) if (variant == "nccalc" and is_max(hwnd)) else 0
            p.rgrc[0].top = top + inset
            return res
        if msg == 0x0005 and wp == 2 and HOOK:  # WM_SIZE, SIZE_MAXIMIZED
            res = comctl32.DefSubclassProc(hwnd, msg, wp, lp)
            from System.Reflection import BindingFlags
            fld = clr.GetClrType(Form).GetField("restoredWindowBoundsSpecified",
                                                BindingFlags.NonPublic | BindingFlags.Instance)
            log.append({"event": "hook", "before": str(fld.GetValue(state["form"]))})
            fld.SetValue(state["form"], getattr(System.Windows.Forms.BoundsSpecified, "None"))
            return res
        if msg == WM_WINDOWPOSCHANGING:
            w = ctypes.cast(lp, ctypes.POINTER(WINDOWPOS)).contents
            if not (w.flags & SWP_NOSIZE):
                log.append({"event": "WINDOWPOSCHANGING", "cx": w.cx, "cy": w.cy, "flags": hex(w.flags),
                            "maximized": is_max(hwnd), "stack": managed_stack()})
    except Exception as e:  # never raise through the window procedure
        log.append({"event": "exc", "error": repr(e)})
    return comctl32.DefSubclassProc(hwnd, msg, wp, lp)


cb = SUBCLASSPROC(proc)


def form_private():
    from System.Reflection import BindingFlags
    flags = BindingFlags.NonPublic | BindingFlags.Instance
    form = state["form"]
    t = clr.GetClrType(Form)
    out = {}
    for name in ("restoredWindowBounds", "restoredWindowBoundsSpecified", "clientWidth", "clientHeight"):
        fld = t.GetField(name, flags) or clr.GetClrType(System.Windows.Forms.Control).GetField(name, flags)
        out[name] = str(fld.GetValue(form)) if fld is not None else None
    fse = t.GetField("formStateEx", flags)
    if fse is not None:
        vec = fse.GetValue(form)
        for name in ("FormStateExWindowBoundsWidthIsClientSize", "FormStateExWindowBoundsHeightIsClientSize"):
            sec = t.GetField(name, BindingFlags.NonPublic | BindingFlags.Static)
            out[name] = vec[sec.GetValue(None)] if sec is not None else None
    return out


def snap(label):
    h = state["hwnd"]
    log.append({"event": "snapshot", "label": label, "window": rect(h), "client": client(h),
                "normal": placement(h), "maximized": is_max(h), "form_client": [state["form"].ClientSize.Width,
                state["form"].ClientSize.Height], "winforms": form_private()})


def run():
    form = Form()
    form.Text = f"drift {variant} {driver}"
    form.StartPosition = FormStartPosition.Manual
    form.Location = System.Drawing.Point(300, 200)
    form.Size = Size(1100, 720)
    state["form"] = form
    steps = ["max", "restore", "max", "restore", "close"]
    timer = Timer()
    timer.Interval = 700

    def on_shown(_s, _e):
        h = int(form.Handle.ToInt64())
        state["hwnd"] = h
        comctl32.SetWindowSubclass(h, cb, 1, 0)
        user32.SetWindowPos(h, None, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0004 | 0x0020)  # FRAMECHANGED
        snap("start")
        timer.Start()

    def tick(_s, _e):
        step = steps.pop(0)
        h = state["hwnd"]
        if step == "close":
            timer.Stop()
            snap("end")
            form.Close()
            return
        log.append({"event": "step", "step": step})
        if driver == "syscmd":
            user32.SendMessageW(h, 0x0112, 0xF030 if step == "max" else 0xF120, 0)
        else:
            form.WindowState = FormWindowState.Maximized if step == "max" else FormWindowState.Normal
        if step == "max" and FIX:
            # Drop WinForms' client-size restore record so Windows' own normal placement stands.
            from System.Reflection import BindingFlags
            fld = clr.GetClrType(Form).GetField("restoredWindowBoundsSpecified",
                                                BindingFlags.NonPublic | BindingFlags.Instance)
            fld.SetValue(form, getattr(System.Windows.Forms.BoundsSpecified, "None"))
        snap("after " + step)

    form.Shown += on_shown
    timer.Tick += tick
    Application.Run(form)


t = Thread(ThreadStart(run))
t.SetApartmentState(ApartmentState.STA)
t.Start()
t.Join()
restored = [e["window"] for e in log if e.get("event") == "snapshot" and not e["maximized"]]
sizes = [[r[2] - r[0], r[3] - r[1]] for r in restored]
(HERE / f"out-{variant}-{driver}{'-fix' if FIX else ''}{'-hook' if HOOK else ''}.json").write_text(json.dumps({"restored_sizes": sizes, "log": log}, indent=1),
                                                    encoding="utf-8")
print(variant, driver, sizes)
