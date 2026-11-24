"""M2-A2 window-framing spike prototype. Same stack as the product:
pywebview create_window + gui=edgechromium, DWM Mica via DwmSetWindowAttribute.

Usage:
  proto.py --mode NAME [--measure] [--interactive]
Modes (flags combine): see MODES below. --measure runs the hit-test grid,
writes out/<mode>.json and screenshots, then closes. --interactive leaves the
window open for the manual checklist (close it with Alt+F4 or the close button).
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import sys
import threading
import time
from ctypes import wintypes
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)

# mode -> flags
MODES = {
    "baseline": dict(),                                    # stock pywebview + Mica only
    "nccalc": dict(nccalc=True),                           # extend content over caption, no hit-test handling
    "nchit": dict(nccalc=True, nchit=True),                # + top-level WM_NCHITTEST
    "nchit_carve": dict(nccalc=True, nchit=True, carve=True),  # + SetWindowRgn hole in WebView2 host
    "nonclient": dict(nccalc=True, nonclient=True),        # WebView2 IsNonClientRegionSupportEnabled
    "nonclient_nchit": dict(nccalc=True, nchit=True, nonclient=True),
    "nonclient_carve": dict(nccalc=True, nchit=True, nonclient=True, carve=True),
}

user32 = ctypes.WinDLL("user32", use_last_error=True)
dwmapi = ctypes.WinDLL("dwmapi")
comctl32 = ctypes.WinDLL("comctl32")
gdi32 = ctypes.WinDLL("gdi32")
kernel32 = ctypes.WinDLL("kernel32")

LRESULT = ctypes.c_ssize_t
WPARAM = ctypes.c_size_t
LPARAM = ctypes.c_ssize_t
SUBCLASSPROC = ctypes.WINFUNCTYPE(
    LRESULT, wintypes.HWND, wintypes.UINT, WPARAM, LPARAM, ctypes.c_size_t, ctypes.c_size_t
)
comctl32.SetWindowSubclass.argtypes = (wintypes.HWND, SUBCLASSPROC, ctypes.c_size_t, ctypes.c_size_t)
comctl32.SetWindowSubclass.restype = wintypes.BOOL
comctl32.RemoveWindowSubclass.argtypes = (wintypes.HWND, SUBCLASSPROC, ctypes.c_size_t)
comctl32.DefSubclassProc.argtypes = (wintypes.HWND, wintypes.UINT, WPARAM, LPARAM)
comctl32.DefSubclassProc.restype = LRESULT
dwmapi.DwmDefWindowProc.argtypes = (wintypes.HWND, wintypes.UINT, WPARAM, LPARAM, ctypes.POINTER(LRESULT))
dwmapi.DwmDefWindowProc.restype = wintypes.BOOL
user32.SendMessageW.argtypes = (wintypes.HWND, wintypes.UINT, WPARAM, LPARAM)
user32.SendMessageW.restype = LRESULT
user32.GetWindowLongPtrW.argtypes = (wintypes.HWND, ctypes.c_int)
user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.WindowFromPoint.argtypes = (wintypes.POINT,)
user32.WindowFromPoint.restype = wintypes.HWND
user32.ChildWindowFromPointEx.argtypes = (wintypes.HWND, wintypes.POINT, wintypes.UINT)
user32.ChildWindowFromPointEx.restype = wintypes.HWND
user32.GetDpiForWindow.argtypes = (wintypes.HWND,)
user32.GetDpiForWindow.restype = wintypes.UINT
user32.GetSystemMetricsForDpi.argtypes = (ctypes.c_int, wintypes.UINT)
user32.GetSystemMetricsForDpi.restype = ctypes.c_int
user32.SetWindowRgn.argtypes = (wintypes.HWND, wintypes.HANDLE, wintypes.BOOL)
user32.GetClassNameW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
user32.GetParent.argtypes = (wintypes.HWND,)
user32.GetParent.restype = wintypes.HWND
user32.GetAncestor.argtypes = (wintypes.HWND, wintypes.UINT)
user32.GetAncestor.restype = wintypes.HWND
user32.EnumChildWindows.argtypes = (wintypes.HWND, ctypes.c_void_p, LPARAM)
gdi32.CreateRectRgn.argtypes = (ctypes.c_int,) * 4
gdi32.CreateRectRgn.restype = wintypes.HANDLE
gdi32.CombineRgn.argtypes = (wintypes.HANDLE, wintypes.HANDLE, wintypes.HANDLE, ctypes.c_int)
gdi32.DeleteObject.argtypes = (wintypes.HANDLE,)

WM_NCCALCSIZE, WM_NCHITTEST, WM_SIZE = 0x0083, 0x0084, 0x0005
HT = {0: "HTNOWHERE", 1: "HTCLIENT", 2: "HTCAPTION", 3: "HTSYSMENU", 4: "HTGROWBOX", 5: "HTMENU",
      6: "HTHSCROLL", 7: "HTVSCROLL", 8: "HTMINBUTTON", 9: "HTMAXBUTTON", 10: "HTLEFT", 11: "HTRIGHT",
      12: "HTTOP", 13: "HTTOPLEFT", 14: "HTTOPRIGHT", 15: "HTBOTTOM", 16: "HTBOTTOMLEFT",
      17: "HTBOTTOMRIGHT", 18: "HTBORDER", 20: "HTCLOSE", 21: "HTHELP", -1: "HTTRANSPARENT",
      -2: "HTERROR"}
HTCLIENT, HTCAPTION, HTMAXBUTTON, HTMINBUTTON, HTCLOSE = 1, 2, 9, 8, 20
HTLEFT, HTRIGHT, HTTOP, HTTOPLEFT, HTTOPRIGHT = 10, 11, 12, 13, 14
HTBOTTOM, HTBOTTOMLEFT, HTBOTTOMRIGHT = 15, 16, 17
GWL_STYLE = -16
WS = {"WS_CAPTION": 0x00C00000, "WS_THICKFRAME": 0x00040000, "WS_SYSMENU": 0x00080000,
      "WS_MAXIMIZEBOX": 0x00010000, "WS_MINIMIZEBOX": 0x00020000, "WS_MAXIMIZE": 0x01000000}
DWMWA_USE_IMMERSIVE_DARK_MODE, DWMWA_SYSTEMBACKDROP_TYPE = 20, 38
DWMWA_EXTENDED_FRAME_BOUNDS, DWMWA_CAPTION_BUTTON_BOUNDS = 9, 5
DWMSBT_MAINWINDOW = 2
# WM_NCMOUSEMOVE, WM_NCLBUTTONDOWN, WM_NCLBUTTONUP, WM_NCMOUSEHOVER, WM_NCMOUSELEAVE
NC_MOUSE_NAMES = {0x0084: "NCHITTEST", 0x00A0: "NCMOUSEMOVE", 0x00A1: "NCLBUTTONDOWN", 0x00A2: "NCLBUTTONUP",
                  0x02A0: "NCMOUSEHOVER", 0x02A2: "NCMOUSELEAVE"}
NC_MOUSE = frozenset(NC_MOUSE_NAMES)


class NCCALCSIZE_PARAMS(ctypes.Structure):
    _fields_ = [("rgrc", wintypes.RECT * 3), ("lppos", ctypes.c_void_p)]


class MARGINS(ctypes.Structure):
    _fields_ = [("l", ctypes.c_int), ("r", ctypes.c_int), ("t", ctypes.c_int), ("b", ctypes.c_int)]


def dwm_set(hwnd, attr, value):
    v = ctypes.c_int(value)
    return dwmapi.DwmSetWindowAttribute(wintypes.HWND(hwnd), attr, ctypes.byref(v), 4)


def dwm_get_int(hwnd, attr):
    v = ctypes.c_int(-99)
    hr = dwmapi.DwmGetWindowAttribute(wintypes.HWND(hwnd), attr, ctypes.byref(v), 4)
    return hr, v.value


def dwm_get_rect(hwnd, attr):
    r = wintypes.RECT()
    hr = dwmapi.DwmGetWindowAttribute(wintypes.HWND(hwnd), attr, ctypes.byref(r), 16)
    return hr, (r.left, r.top, r.right, r.bottom)


def cls_name(h):
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(h, buf, 256)
    return buf.value


def pid_of(h):
    p = wintypes.DWORD()
    user32.GetWindowThreadProcessId(h, ctypes.byref(p))
    return p.value


def win_rect(h):
    r = wintypes.RECT()
    user32.GetWindowRect(wintypes.HWND(h), ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom


def pack(x, y):
    return ((y & 0xFFFF) << 16) | (x & 0xFFFF)


def signed(v):
    v &= 0xFFFF
    return v - 0x10000 if v & 0x8000 else v


class Framing:
    """State shared with the subclass procedure."""

    def __init__(self, flags):
        self.flags = flags
        self.hwnd = 0
        self.caption_h_dip = 32
        self.resize_top_dip = 6
        self.log = []          # real WM_NCHITTEST seen by the top-level
        self.logging = False
        self.wv_hwnd = 0
        self.carve_count = 0
        self.nodrag_rects = []  # screen-relative-to-window rects (physical px) that stay HTCLIENT
        self.dwm_mouse = {}    # (msg, DwmDefWindowProc handled) -> count, for fix_hover
        self.dwm_hit = {}      # DwmDefWindowProc's own WM_NCHITTEST answers -> count
        self.hit_trace = []    # (x, y, maximized, dwm answer, our answer), last 400
        self.proc = SUBCLASSPROC(self._proc)

    def scale(self):
        return user32.GetDpiForWindow(self.hwnd) / 96.0

    def is_max(self):
        return bool(user32.GetWindowLongPtrW(self.hwnd, GWL_STYLE) & WS["WS_MAXIMIZE"])

    def frame_y(self):
        dpi = user32.GetDpiForWindow(self.hwnd)
        return user32.GetSystemMetricsForDpi(33, dpi) + user32.GetSystemMetricsForDpi(92, dpi)  # SIZEFRAME + PADDEDBORDER

    def max_btn_rect(self):
        """Window-relative rect of the maximize button (middle third of DWM caption-button bounds)."""
        hr, (l, t, r, b) = dwm_get_rect(self.hwnd, DWMWA_CAPTION_BUTTON_BOUNDS)
        if hr != 0:
            return None
        w = 46 * self.scale()  # Win11 caption button width; verified by the sweep in the report
        return (int(r - 2 * w), t, int(r - w), b)

    def _proc(self, hwnd, msg, wparam, lparam, uid, ref):
        f = self.flags
        try:
            # A2 follow-up: let DWM animate its caption buttons on non-client mouse messages
            if f.get("fix_hover") and msg in NC_MOUSE:
                lres = LRESULT(0)
                handled = dwmapi.DwmDefWindowProc(hwnd, msg, wparam, lparam, ctypes.byref(lres))
                self.dwm_mouse[(msg, bool(handled))] = self.dwm_mouse.get((msg, bool(handled)), 0) + 1
                if handled:
                    return lres.value
            if msg == WM_NCCALCSIZE and f.get("nccalc") and wparam:
                p = ctypes.cast(lparam, ctypes.POINTER(NCCALCSIZE_PARAMS)).contents
                orig_top = p.rgrc[0].top
                res = comctl32.DefSubclassProc(hwnd, msg, wparam, lparam)
                if self.is_max():
                    p.rgrc[0].top = orig_top + self.frame_y()
                else:
                    p.rgrc[0].top = orig_top
                return res
            if msg in (WM_SIZE, 0x02E0) and f.get("carve") and self.wv_hwnd:  # WM_SIZE, WM_DPICHANGED
                res = comctl32.DefSubclassProc(hwnd, msg, wparam, lparam)
                carve_apply(self)
                return res
            if msg == WM_NCHITTEST:
                if f.get("fix_hover"):
                    lres = LRESULT(0)
                    handled = dwmapi.DwmDefWindowProc(hwnd, msg, wparam, lparam, ctypes.byref(lres))
                    key = (msg, bool(handled))
                    self.dwm_mouse[key] = self.dwm_mouse.get(key, 0) + 1
                    if handled:
                        self.dwm_hit[lres.value] = self.dwm_hit.get(lres.value, 0) + 1
                res = self._nchittest(hwnd, msg, wparam, lparam)
                if f.get("fix_hover"):
                    self.hit_trace.append((signed(lparam), signed(lparam >> 16), self.is_max(),
                                           HT.get(lres.value, lres.value) if handled else "-", HT.get(res, res)))
                    del self.hit_trace[:-400]
                if self.logging:
                    self.log.append((signed(lparam), signed(lparam >> 16), res, HT.get(res, str(res))))
                return res
        except Exception as e:  # never raise through the WndProc
            self.log.append(("exc", repr(e)))
        return comctl32.DefSubclassProc(hwnd, msg, wparam, lparam)

    def _nchittest(self, hwnd, msg, wparam, lparam):
        if not self.flags.get("nchit"):
            return comctl32.DefSubclassProc(hwnd, msg, wparam, lparam)
        lres = LRESULT(0)
        x, y = signed(lparam), signed(lparam >> 16)
        top_y = win_rect(hwnd)[1]
        in_top_band = (not self.is_max()) and y < top_y + int(self.resize_top_dip * self.scale())
        if not in_top_band:
            hrb, (bl, bt, br, bb) = dwm_get_rect(hwnd, DWMWA_CAPTION_BUTTON_BOUNDS)
            wl_, wt_, _, _ = win_rect(hwnd)
            bw = 46 * self.scale()
            if hrb == 0 and (wt_ + bt) <= y < (wt_ + bb):
                for k, code in ((0, HTCLOSE), (1, HTMAXBUTTON), (2, HTMINBUTTON)):
                    x1 = wl_ + br - k * bw
                    if x1 - bw <= x < x1:
                        return code
        res = comctl32.DefSubclassProc(hwnd, msg, wparam, lparam)
        if res != HTCLIENT:
            return res
        x, y = signed(lparam), signed(lparam >> 16)
        l, t, r, b = win_rect(hwnd)
        s = self.scale()
        mb = self.max_btn_rect()
        # Snap Layouts: maximize button must hit-test as HTMAXBUTTON
        if mb and (l + mb[0]) <= x < (l + mb[2]) and (t + mb[1]) <= y < (t + mb[3]):
            return HTMAXBUTTON
        top_band = int(self.resize_top_dip * s) if not self.is_max() else 0
        corner = int(16 * s)
        if y < t + top_band:
            if x < l + corner:
                return HTTOPLEFT
            if x >= r - corner:
                return HTTOPRIGHT
            return HTTOP
        if y < t + int(self.caption_h_dip * s):
            for (a, bb, c, d) in self.nodrag_rects:
                if l + a <= x < l + c and t + bb <= y < t + d:
                    return HTCLIENT
            return HTCAPTION
        return HTCLIENT


def carve_apply(fr, result=None):
    """Hole in the WebView2 host control (SetWindowRgn) so the top-level sees the mouse over the
    top resize band and the caption buttons. Must be re-run on WM_SIZE / WM_DPICHANGED."""
    top, h = fr.hwnd, fr.wv_hwnd
    cr = wintypes.RECT()
    user32.GetClientRect(wintypes.HWND(h), ctypes.byref(cr))
    cw, ch = cr.right, cr.bottom
    s = fr.scale()
    rgn = gdi32.CreateRectRgn(0, 0, cw, ch)
    if not fr.is_max():
        hole = gdi32.CreateRectRgn(0, 0, cw, int(fr.resize_top_dip * s))
        gdi32.CombineRgn(rgn, rgn, hole, 4)  # RGN_DIFF
        gdi32.DeleteObject(hole)
    hr, (l, t, r, b) = dwm_get_rect(top, DWMWA_CAPTION_BUTTON_BOUNDS)
    if hr == 0:
        wr = win_rect(top)
        org = wintypes.POINT(0, 0)
        user32.ClientToScreen(wintypes.HWND(h), ctypes.byref(org))
        ox, oy = org.x - wr[0], org.y - wr[1]
        hole = gdi32.CreateRectRgn(l - ox, t - oy, r - ox, b - oy)
        gdi32.CombineRgn(rgn, rgn, hole, 4)
        gdi32.DeleteObject(hole)
        if result is not None:
            result["carve_buttons_rect_ctrl"] = (l - ox, t - oy, r - ox, b - oy)
    user32.SetWindowRgn(wintypes.HWND(h), rgn, True)  # system owns rgn now
    fr.carve_count += 1
    if result is not None:
        result["carved"] = True


def child_windows(top):
    out = []
    CB = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, LPARAM)

    def cb(h, _):
        out.append(h)
        return True

    keep = CB(cb)
    user32.EnumChildWindows(wintypes.HWND(top), ctypes.cast(keep, ctypes.c_void_p), 0)
    return out


def chain(h):
    c = []
    while h:
        c.append(f"{h:#x}:{cls_name(h)}:pid{pid_of(h)}")
        h = user32.GetParent(wintypes.HWND(h)) or 0
    return c


def hit_probe(top, x, y):
    pt = wintypes.POINT(x, y)
    lp = pack(x, y)
    top_res = user32.SendMessageW(wintypes.HWND(top), WM_NCHITTEST, 0, lp)
    wfp = user32.WindowFromPoint(pt) or 0
    cw = user32.ChildWindowFromPointEx(wintypes.HWND(top), wintypes.POINT(x, y), 0) or 0
    # ChildWindowFromPointEx wants client coords
    cp = wintypes.POINT(x, y)
    user32.ScreenToClient(wintypes.HWND(top), ctypes.byref(cp))
    cw = user32.ChildWindowFromPointEx(wintypes.HWND(top), cp, 0) or 0
    child_res = None
    if wfp and wfp != top:
        child_res = user32.SendMessageW(wintypes.HWND(wfp), WM_NCHITTEST, 0, lp)
    chain_res = []
    h = wfp
    while h and h != top:
        r_ = user32.SendMessageW(wintypes.HWND(h), WM_NCHITTEST, 0, lp)
        chain_res.append(f"{cls_name(h)[:26]}={HT.get(r_, r_)}")
        h = user32.GetParent(wintypes.HWND(h)) or 0
    return {
        "x": x, "y": y, "chain": chain_res,
        "top_NCHITTEST": HT.get(top_res, top_res),
        "WindowFromPoint": f"{wfp:#x} {cls_name(wfp) if wfp else ''} pid{pid_of(wfp) if wfp else 0}"
                           + (" (top)" if wfp == top else "")
                           + (" ROOT=ours" if wfp and (user32.GetAncestor(wintypes.HWND(wfp), 2) or 0) == top else " ROOT=OTHER"),
        "ChildWindowFromPointEx": f"{cw:#x} {cls_name(cw) if cw else ''}" if cw else "none",
        "WFP_NCHITTEST": HT.get(child_res, child_res) if child_res is not None else "-",
    }


def sweep(top):
    wl, wt, wr, wb = win_rect(top)
    hr, (l, t, r, b) = dwm_get_rect(top, DWMWA_CAPTION_BUTTON_BOUNDS)
    y = wt + (t + b) // 2
    runs, prev, start = [], None, None
    for x in range(wl + l - 40, wl + r + 8):
        res = user32.SendMessageW(wintypes.HWND(top), WM_NCHITTEST, 0, pack(x, y))
        if res != prev:
            if prev is not None:
                runs.append((start - wl, x - 1 - wl, HT.get(prev, prev)))
            prev, start = res, x
    runs.append((start - wl, wl + r + 7 - wl, HT.get(prev, prev)))
    return runs


def grid(top):
    wl, wt, wr, wb = win_rect(top)
    hr, (vl, vt, vr, vb) = dwm_get_rect(top, DWMWA_EXTENDED_FRAME_BOUNDS)
    cap = dwm_get_rect(top, DWMWA_CAPTION_BUTTON_BOUNDS)
    s = user32.GetDpiForWindow(top) / 96.0
    midx, midy = (vl + vr) // 2, (vt + vb) // 2
    pts = {}
    for name, off in (("out3", -3), ("in1", 1), ("in4", 4), ("in10", 10)):
        pts[f"left_{name}"] = (vl + off, midy)
        pts[f"right_{name}"] = (vr - off - 1 + (0 if off >= 0 else 0), midy) if off >= 0 else (vr - off - 1, midy)
        pts[f"bottom_{name}"] = (midx, vb - off - 1) if off >= 0 else (midx, vb - off - 1)
        pts[f"top_{name}"] = (midx, vt + off)
    for name, off in (("in1", 1), ("in4", 4)):
        pts[f"topleft_{name}"] = (vl + off, vt + off)
        pts[f"topright_{name}"] = (vr - off - 1, vt + off)
        pts[f"bottomleft_{name}"] = (vl + off, vb - off - 1)
        pts[f"bottomright_{name}"] = (vr - off - 1, vb - off - 1)
    pts["topleft_corner_in12"] = (vl + 12, vt + 3)
    pts["topright_corner_in12"] = (vr - 13, vt + 3)
    capy = vt + int(16 * s)
    pts["caption_drag_left"] = (vl + int(40 * s), capy)
    pts["caption_drag_center"] = (midx, capy)
    pts["caption_below_resize_y10"] = (midx, vt + 10)
    if cap[0] == 0:
        l, t, r, b = cap[1]
        w = (r - l) / 3.0
        cy = wt + (t + b) // 2
        bw = 46 * s
        for i, nm in enumerate(("min_btn", "max_btn", "close_btn")):
            pts[nm] = (int(wl + r - bw * (3 - i - 0.5)), cy)
        pts["left_of_buttons_x-4"] = (int(wl + r - 3 * bw - 4), cy)
        pts["max_btn_top_edge_y1"] = (int(wl + r - bw * 1.5), vt + 1)
        pts["close_btn_topright_y1"] = (vr - 6, vt + 1)
    pts["client_body_center"] = (midx, midy)
    pts["client_body_below_caption"] = (midx, vt + int(48 * s))
    return {k: hit_probe(top, *v) for k, v in pts.items()}


def mouse(x, y, flags=0):
    class MI(ctypes.Structure):
        _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long), ("mouseData", wintypes.DWORD),
                    ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("extra", ctypes.c_size_t)]

    class INP(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("mi", MI)]

    vx, vy = user32.GetSystemMetrics(76), user32.GetSystemMetrics(77)
    vw, vh = user32.GetSystemMetrics(78), user32.GetSystemMetrics(79)
    nx = int((x - vx) * 65535 / (vw - 1))
    ny = int((y - vy) * 65535 / (vh - 1))
    inp = INP(0, MI(nx, ny, 0, 0x0001 | 0x8000 | 0x4000 | flags, 0, 0))
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


LDOWN, LUP, RDOWN, RUP = 0x2, 0x4, 0x8, 0x10


def click(x, y, n=1, right=False, gap=0.08):
    mouse(x, y)
    time.sleep(0.15)
    for _ in range(n):
        mouse(x, y, RDOWN if right else LDOWN)
        time.sleep(0.04)
        mouse(x, y, RUP if right else LUP)
        time.sleep(gap)


def drag(x0, y0, x1, y1, steps=12):
    mouse(x0, y0)
    time.sleep(0.2)
    mouse(x0, y0, LDOWN)
    time.sleep(0.15)
    for i in range(1, steps + 1):
        mouse(x0 + (x1 - x0) * i // steps, y0 + (y1 - y0) * i // steps)
        time.sleep(0.03)
    time.sleep(0.15)
    mouse(x1, y1, LUP)
    time.sleep(0.4)


class GUITHREADINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("flags", wintypes.DWORD), ("hwndActive", wintypes.HWND),
                ("hwndFocus", wintypes.HWND), ("hwndCapture", wintypes.HWND),
                ("hwndMenuOwner", wintypes.HWND), ("hwndMoveSize", wintypes.HWND),
                ("hwndCaret", wintypes.HWND), ("rcCaret", wintypes.RECT)]


def gui_flags(hwnd):
    tid = user32.GetWindowThreadProcessId(wintypes.HWND(hwnd), None)
    gi = GUITHREADINFO()
    gi.cbSize = ctypes.sizeof(gi)
    user32.GetGUIThreadInfo(tid, ctypes.byref(gi))
    return gi.flags


def is_zoomed(hwnd):
    return bool(user32.IsZoomed(wintypes.HWND(hwnd)))


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT),
                ("dwFlags", wintypes.DWORD)]


def monitor_info(hwnd):
    user32.MonitorFromWindow.restype = wintypes.HANDLE
    user32.MonitorFromWindow.argtypes = (wintypes.HWND, wintypes.DWORD)
    m = user32.MonitorFromWindow(wintypes.HWND(hwnd), 2)
    mi = MONITORINFO()
    mi.cbSize = ctypes.sizeof(mi)
    user32.GetMonitorInfoW.argtypes = (wintypes.HANDLE, ctypes.c_void_p)
    user32.GetMonitorInfoW(m, ctypes.byref(mi))
    return ((mi.rcMonitor.left, mi.rcMonitor.top, mi.rcMonitor.right, mi.rcMonitor.bottom),
            (mi.rcWork.left, mi.rcWork.top, mi.rcWork.right, mi.rcWork.bottom))


def client_screen_rect(hwnd):
    cr = wintypes.RECT()
    user32.GetClientRect(wintypes.HWND(hwnd), ctypes.byref(cr))
    o = wintypes.POINT(0, 0)
    user32.ClientToScreen(wintypes.HWND(hwnd), ctypes.byref(o))
    return (o.x, o.y, o.x + cr.right, o.y + cr.bottom)


def btn_centers(top):
    wl, wt, wr, wb = win_rect(top)
    hr, (l, t, r, b) = dwm_get_rect(top, DWMWA_CAPTION_BUTTON_BOUNDS)
    bw = 46 * user32.GetDpiForWindow(top) / 96.0
    cy = wt + (t + b) // 2
    return {"min": (int(wl + r - 2.5 * bw), cy), "max": (int(wl + r - 1.5 * bw), cy),
            "close": (int(wl + r - 0.5 * bw), cy)}


def esc():
    user32.keybd_event(0x1B, 0, 0, 0)
    user32.keybd_event(0x1B, 0, 2, 0)


def run_actions(top, out_dir, mode, T=lambda m: None):
    """Drive real mouse/keyboard input at the prototype window and record the outcome."""
    A = {}
    user32.SetWindowPos(wintypes.HWND(top), wintypes.HWND(-1), 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)
    s = user32.GetDpiForWindow(top) / 96.0
    vl, vt, vr, vb = dwm_get_rect(top, DWMWA_EXTENDED_FRAME_BOUNDS)[1]
    cx = (vl + vr) // 2
    A["monitor_rect_work"] = monitor_info(top)
    A["monitors_in_system"] = user32.GetSystemMetrics(80)
    click(cx, (vt + vb) // 2)  # focus
    r0 = win_rect(top)
    T("act drag")
    capy = vt + int(16 * s)
    drag(cx, capy, cx + 90, capy + 70)
    r1 = win_rect(top)
    A["caption_drag"] = {"before": r0, "after": r1, "moved_xy": (r1[0] - r0[0], r1[1] - r0[1]),
                         "size_changed": (r1[2] - r1[0]) != (r0[2] - r0[0])}
    T("act dblclick")
    vl, vt, vr, vb = dwm_get_rect(top, DWMWA_EXTENDED_FRAME_BOUNDS)[1]
    cx = (vl + vr) // 2
    capy = vt + int(16 * s)
    click(cx, capy, n=2, gap=0.06)
    time.sleep(0.8)
    A["dblclick_caption_1"] = {"zoomed": is_zoomed(top), "rect": win_rect(top)}
    if is_zoomed(top):
        A["maximized_geometry"] = {
            "window_rect": win_rect(top), "client_screen_rect": client_screen_rect(top),
            "monitor_rect_work": monitor_info(top),
            "caption_button_bounds": dwm_get_rect(top, DWMWA_CAPTION_BUTTON_BOUNDS),
            "styles": {k: bool(user32.GetWindowLongPtrW(top, GWL_STYLE) & v) for k, v in WS.items()}}
        A["maximized_sweep"] = sweep(top)
        A["maximized_grid_sample"] = {k: v for k, v in grid(top).items() if k in (
            "caption_drag_center", "min_btn", "max_btn", "close_btn", "client_body_center", "top_in1", "top_in4")}
        try:
            A["maximized_screenshot_ok"] = print_window(out_dir / f"{mode}_maximized.png", top)
        except Exception as e:
            A["maximized_screenshot_ok"] = repr(e)
        vl2, vt2, vr2, vb2 = dwm_get_rect(top, DWMWA_EXTENDED_FRAME_BOUNDS)[1]
        click((vl2 + vr2) // 2, vt2 + int(16 * s), n=2, gap=0.06)
        time.sleep(0.8)
        A["dblclick_caption_2"] = {"zoomed": is_zoomed(top), "rect": win_rect(top)}
    T("act maxbtn")
    pts = btn_centers(top)
    click(*pts["max"])
    time.sleep(0.8)
    A["maxbtn_click_1"] = {"zoomed": is_zoomed(top)}
    if is_zoomed(top):
        click(*btn_centers(top)["max"])
        time.sleep(0.8)
        A["maxbtn_click_2"] = {"zoomed": is_zoomed(top)}
    T("act minbtn")
    click(*btn_centers(top)["min"])
    time.sleep(1.0)
    A["minbtn_click"] = {"iconic": bool(user32.IsIconic(wintypes.HWND(top)))}
    user32.ShowWindow(wintypes.HWND(top), 9)  # SW_RESTORE
    time.sleep(0.8)
    user32.SetWindowPos(wintypes.HWND(top), wintypes.HWND(-1), 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)
    T("act resize")
    cases = (
        ("top_edge", lambda l, t, r, b: ((l + r) // 2, t + 2, 0, -40)),
        ("left_edge", lambda l, t, r, b: (l + 1, (t + b) // 2, -40, 0)),
        ("right_edge", lambda l, t, r, b: (r - 2, (t + b) // 2, 40, 0)),
        ("bottom_edge", lambda l, t, r, b: ((l + r) // 2, b - 2, 0, 40)),
        ("topleft_corner", lambda l, t, r, b: (l + 2, t + 2, -30, -30)),
        ("topright_corner", lambda l, t, r, b: (r - 3, t + 2, 30, -30)),
        ("bottomright_corner", lambda l, t, r, b: (r + 2, b + 2, 30, 30)),
        ("bottomleft_corner", lambda l, t, r, b: (l - 3, b + 2, -30, 30)),
    )
    for name, fn in cases:
        ext = dwm_get_rect(top, DWMWA_EXTENDED_FRAME_BOUNDS)[1]
        before = win_rect(top)
        x, y, dx, dy = fn(*ext)
        drag(x, y, x + dx, y + dy)
        after = win_rect(top)
        A.setdefault("resize", {})[name] = {"start": (x, y), "delta_ltrb": tuple(a - b for a, b in zip(after, before))}
    T("act altspace")
    wr_ = win_rect(top)
    click(cx, (wr_[1] + wr_[3]) // 2)
    time.sleep(0.2)
    user32.keybd_event(0x12, 0, 0, 0)
    user32.keybd_event(0x20, 0, 0, 0)
    user32.keybd_event(0x20, 0, 2, 0)
    user32.keybd_event(0x12, 0, 2, 0)
    time.sleep(0.6)
    fl = gui_flags(top)
    A["alt_space"] = {"gui_flags": hex(fl), "system_menu_mode": bool(fl & 0x8), "in_menu_mode": bool(fl & 0x4)}
    try:
        wl, wt, _, _ = win_rect(top)
        screen_capture(out_dir / f"{mode}_altspace.png", (wl, wt, wl + 700, wt + 520))
    except Exception:
        pass
    esc()
    time.sleep(0.4)
    T("act rclick")
    vl, vt, vr, vb = dwm_get_rect(top, DWMWA_EXTENDED_FRAME_BOUNDS)[1]
    click((vl + vr) // 2, vt + int(16 * s), right=True)
    time.sleep(0.7)
    fl = gui_flags(top)
    A["right_click_caption"] = {"gui_flags": hex(fl), "system_menu_mode": bool(fl & 0x8), "popup_menu_mode": bool(fl & 0x10)}
    esc()
    time.sleep(0.3)
    return A


def screen_capture(path, rect):
    import System
    from System.Drawing import Bitmap, Graphics, Point, Size
    from System.Drawing.Imaging import ImageFormat
    l, t, r, b = rect
    bmp = Bitmap(r - l, b - t)
    g = Graphics.FromImage(bmp)
    g.CopyFromScreen(l, t, 0, 0, Size(r - l, b - t))
    g.Dispose()
    bmp.Save(str(path), ImageFormat.Png)
    bmp.Dispose()


user32.PrintWindow.argtypes = (wintypes.HWND, ctypes.c_void_p, wintypes.UINT)


def print_window(path, hwnd):
    from System.Drawing import Bitmap, Graphics, Rectangle
    from System.Drawing.Imaging import ImageFormat
    l, t, r, b = win_rect(hwnd)
    bmp = Bitmap(r - l, b - t)
    g = Graphics.FromImage(bmp)
    hdc = g.GetHdc()
    ok = user32.PrintWindow(wintypes.HWND(hwnd), ctypes.c_void_p(int(hdc.ToInt64())), 2)  # PW_RENDERFULLCONTENT
    g.ReleaseHdc(hdc)
    g.Dispose()
    bmp.Save(str(path), ImageFormat.Png)
    bmp.Dispose()
    return bool(ok)


def root_is(hwnd, x, y):
    w = user32.WindowFromPoint(wintypes.POINT(x, y)) or 0
    return bool(w) and (user32.GetAncestor(wintypes.HWND(w), 2) or 0) == hwnd


def move_real_cursor(x, y):
    """SendInput absolute move (virtual desktop coords normalised)."""
    class MI(ctypes.Structure):
        _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long), ("mouseData", wintypes.DWORD),
                    ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("extra", ctypes.c_size_t)]

    class INP(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("mi", MI)]

    vx, vy = user32.GetSystemMetrics(76), user32.GetSystemMetrics(77)
    vw, vh = user32.GetSystemMetrics(78), user32.GetSystemMetrics(79)
    nx = int((x - vx) * 65535 / (vw - 1))
    ny = int((y - vy) * 65535 / (vh - 1))
    inp = INP(0, MI(nx, ny, 0, 0x0001 | 0x8000 | 0x4000, 0, 0))  # MOVE|ABSOLUTE|VIRTUALDESK
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


PAGE = """<!doctype html><meta charset=utf-8><title>framing</title>
<style>
:root{color-scheme:light dark}
html,body{margin:0;height:100%;background:transparent;font:14px 'Segoe UI Variable Text','Segoe UI',sans-serif;color:CanvasText}
body.dark{color:#fff}body.light{color:#111}
#bar{height:32px;display:flex;align-items:center;gap:8px;padding:0 12px;box-sizing:border-box;
 outline:1px dashed rgba(128,128,128,.6);outline-offset:-1px;app-region:drag;-webkit-app-region:drag;user-select:none}
#bar .title{font-weight:600}
#bar button{app-region:no-drag;-webkit-app-region:no-drag;height:24px}
#zone{margin-left:auto;width:138px;height:32px;box-sizing:border-box;border-left:1px dashed rgba(128,128,128,.6);
 display:flex;align-items:center;justify-content:center;font-size:11px;opacity:.7}
#body{padding:16px}
</style>
<body class=light>
<div id=bar><span class=title>NamiSync framing spike</span><button id=nd>no-drag button</button>
<span style="font-size:11px;opacity:.7">drag region (app-region:drag)</span><div id=zone>caption buttons zone</div></div>
<div id=body><p id=mode></p><p>Page background is transparent; Mica should show through.</p>
<p>Double-click the bar to maximize; hover the maximize button for Snap Layouts.</p></div>
<script>
function setTheme(t){document.body.className=t}
function rects(){const o=[];document.querySelectorAll('#nd').forEach(e=>{const r=e.getBoundingClientRect();o.push([r.left,r.top,r.right,r.bottom,devicePixelRatio])});return JSON.stringify(o)}
</script>"""


def T(msg):
    with open(OUT / "trace.txt", "a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%H:%M:%S')} {msg}\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="nonclient_carve", choices=sorted(MODES))
    ap.add_argument("--measure", action="store_true")
    ap.add_argument("--interactive", action="store_true")
    ap.add_argument("--actions", action="store_true", help="drive real mouse/keyboard input at the window")
    ap.add_argument("--dark", action="store_true", help="start with dark DWM mode")
    ap.add_argument("--fix-theme", action="store_true",
                    help="reapply dark mode and Mica after pywebview's own theme-change handler")
    ap.add_argument("--fix-hover", action="store_true",
                    help="pass non-client mouse messages to DwmDefWindowProc first")
    ap.add_argument("--nc-buttons", default="move",
                    help="with --fix-hover: 'move' (move/hover/leave only) or 'all' (also button down/up)")
    args = ap.parse_args()
    flags = dict(MODES[args.mode])
    if args.fix_hover:
        flags["fix_hover"] = True
        if args.nc_buttons != "all":
            global NC_MOUSE
            NC_MOUSE = frozenset({0x00A0, 0x02A0, 0x02A2})
    import faulthandler
    faulthandler.dump_traceback_later(30, file=open(OUT / f"hang_{args.mode}.txt", "w"), exit=False)
    T(f"main start {args.mode}")
    fr = Framing(flags)

    import webview
    page = HERE / "page.html"
    page.write_text(PAGE, encoding="utf-8")
    window = webview.create_window(
        f"NamiSync framing spike [{args.mode}]", str(page), js_api=None,
        background_color="#202020", transparent=False, width=1100, height=720, min_size=(640, 420),
        x=260, y=140,
    )
    result = {"mode": args.mode, "flags": flags}
    done = threading.Event()

    def ui(fn):
        """Run fn on the form's UI thread and return its result."""
        from System import Action
        box = {}

        def run():
            try:
                box["v"] = fn()
            except Exception as e:
                box["e"] = repr(e)
        window.native.Invoke(Action(run))
        if "e" in box:
            raise RuntimeError(box["e"])
        return box.get("v")

    def apply_frame():
        from System.Drawing import Color
        form = window.native
        hwnd = int(form.Handle.ToInt64())
        fr.hwnd = hwnd
        result["hwnd"] = hex(hwnd)
        # Mica exactly like appearance.py: dark attr, backdrop, margins -1, black BackColor, transparent controller
        result["dwm_dark_set_hr"] = dwm_set(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, 1 if args.dark else 0)
        result["dwm_backdrop_set_hr"] = dwm_set(hwnd, DWMWA_SYSTEMBACKDROP_TYPE, DWMSBT_MAINWINDOW)
        m = MARGINS(-1, -1, -1, -1)
        result["extend_frame_hr"] = dwmapi.DwmExtendFrameIntoClientArea(wintypes.HWND(hwnd), ctypes.byref(m))
        form.BackColor = Color.Black
        form.browser.webview.DefaultBackgroundColor = Color.Transparent
        if flags.get("nccalc") or flags.get("nchit"):
            ok = comctl32.SetWindowSubclass(wintypes.HWND(hwnd), fr.proc, 1, 0)
            result["subclass_installed"] = bool(ok)
        if flags.get("nonclient"):
            core = form.browser.webview.CoreWebView2
            s = core.Settings
            result["IsNonClientRegionSupportEnabled_before"] = bool(s.IsNonClientRegionSupportEnabled)
            s.IsNonClientRegionSupportEnabled = True
            result["IsNonClientRegionSupportEnabled_after"] = bool(s.IsNonClientRegionSupportEnabled)
        if args.fix_theme:
            # pywebview's UserPreferenceChanged handler (subscribed earlier, in the form constructor)
            # sets DWMWA_SYSTEMBACKDROP_TYPE to DWMSBT_NONE in light mode; reapply after it runs.
            from Microsoft.Win32 import SystemEvents
            from System import Action

            def reapply():
                import winreg
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                    r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
                    light = winreg.QueryValueEx(k, "AppsUseLightTheme")[0]
                dark = 0 if light else 1
                hr1 = dwm_set(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, dark)
                hr2 = dwm_set(hwnd, DWMWA_SYSTEMBACKDROP_TYPE, DWMSBT_MAINWINDOW)
                T(f"theme reapply dark={dark} hr={hr1},{hr2} backdrop_readback={dwm_get_int(hwnd, DWMWA_SYSTEMBACKDROP_TYPE)}")

            def on_pref(_s, _e):
                form.BeginInvoke(Action(reapply))
            SystemEvents.UserPreferenceChanged += on_pref
            result["fix_theme_handler"] = on_pref  # keep a reference
        # force NCCALCSIZE
        SWP = 0x0001 | 0x0002 | 0x0004 | 0x0020  # NOSIZE NOMOVE NOZORDER FRAMECHANGED
        user32.SetWindowPos(wintypes.HWND(hwnd), None, 0, 0, 0, 0, SWP)

    def carve():
        fr.wv_hwnd = int(window.native.browser.webview.Handle.ToInt64())
        carve_apply(fr, result)

    def nodrag_from_page():
        raw = window.evaluate_js("rects()")
        rs = json.loads(raw)
        out = []
        for l, t, r, b, dpr in rs:
            out.append((int(l * dpr), int(t * dpr), int(r * dpr), int(b * dpr)))
        # element rects are client coords; caption-height top-level is at client origin when nccalc.
        fr.nodrag_rects = out
        result["nodrag_rects_px"] = out

    def run_measure():
        top = fr.hwnd
        T('rm start')
        time.sleep(0.5)
        result["pywebview"] = webview.__version__ if hasattr(webview, "__version__") else "?"
        result["dpi"] = user32.GetDpiForWindow(top)
        result["window_rect"] = win_rect(top)
        result["extended_frame_bounds"] = dwm_get_rect(top, DWMWA_EXTENDED_FRAME_BOUNDS)[1]
        result["caption_button_bounds_window_rel"] = dwm_get_rect(top, DWMWA_CAPTION_BUTTON_BOUNDS)
        st = user32.GetWindowLongPtrW(top, GWL_STYLE)
        result["styles"] = {k: bool(st & v) for k, v in WS.items()}
        result["dwm_dark_readback"] = dwm_get_int(top, DWMWA_USE_IMMERSIVE_DARK_MODE)
        result["dwm_backdrop_readback"] = dwm_get_int(top, DWMWA_SYSTEMBACKDROP_TYPE)
        result["children"] = [f"{h:#x} {cls_name(h)} pid{pid_of(h)} parent={chain(h)[1] if len(chain(h))>1 else ''}"
                              for h in child_windows(top)]
        client = wintypes.RECT()
        user32.GetClientRect(wintypes.HWND(top), ctypes.byref(client))
        org = wintypes.POINT(0, 0)
        user32.ClientToScreen(wintypes.HWND(top), ctypes.byref(org))
        wr = win_rect(top)
        result["client_origin_minus_window_origin"] = (org.x - wr[0], org.y - wr[1])
        result["client_size"] = (client.right, client.bottom)
        user32.SetForegroundWindow(wintypes.HWND(top))
        time.sleep(0.4)
        user32.SetWindowPos(wintypes.HWND(top), wintypes.HWND(-1), 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)  # TOPMOST for the run
        time.sleep(0.3)
        T('sweep')
        result["sweep_caption_y"] = sweep(top)
        T('grid')
        result["grid_normal"] = grid(top)
        T('real')
        # real cursor path: log what the top-level really receives
        fr.log.clear()
        fr.logging = True
        saved = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(saved))
        real = {}
        vl, vt, vr, vb = dwm_get_rect(top, DWMWA_EXTENDED_FRAME_BOUNDS)[1]
        s = user32.GetDpiForWindow(top) / 96.0
        cap = dwm_get_rect(top, DWMWA_CAPTION_BUTTON_BOUNDS)[1]
        wl, wt = win_rect(top)[:2]
        w3 = 46 * s
        targets = {
            "caption_drag_center": ((vl + vr) // 2, vt + int(16 * s)),
            "max_btn": (int(wl + cap[2] - w3 * 1.5), wt + (cap[1] + cap[3]) // 2),
            "top_edge_y1": ((vl + vr) // 2, vt + 1),
            "top_edge_y3": ((vl + vr) // 2, vt + 3),
            "left_edge_in1": (vl + 1, (vt + vb) // 2),
            "left_edge_out3": (vl - 3, (vt + vb) // 2),
            "bottom_right_corner_in2": (vr - 3, vb - 3),
            "client_body": ((vl + vr) // 2, (vt + vb) // 2),
        }
        shots = {}
        for name, (x, y) in targets.items():
            fr.log.clear()
            for _ in range(3):
                user32.SetWindowPos(wintypes.HWND(top), wintypes.HWND(-1), 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)
                move_real_cursor(x - 8, y)
                time.sleep(0.15)
                move_real_cursor(x, y)
                time.sleep(0.5)
                if root_is(top, x, y):
                    break
            seen = [e for e in fr.log if e[0] != "exc"]
            real[name] = {"at": (x, y), "top_level_received": seen[-3:], "count": len(seen),
                          "WindowFromPoint": f"{cls_name(user32.WindowFromPoint(wintypes.POINT(x, y)))}",
                          "root_is_ours": root_is(top, x, y)}
            if name == "max_btn":
                time.sleep(1.4)  # allow Snap Layouts flyout delay
                if root_is(top, x, y):
                    p = OUT / f"{args.mode}_hover_max.png"
                    screen_capture(p, (vl - 20, vt - 20, vr + 20, vt + 420))
                    real[name]["screenshot"] = p.name
        fr.logging = False
        user32.SetCursorPos(saved.x, saved.y)
        result["real_cursor"] = real
        # screenshots light / dark (no cursor on the window)
        user32.SetCursorPos(vl - 200 if vl > 200 else vr + 50, vb + 5)
        for theme, d in (("light", 0), ("dark", 1)):
            ui(lambda d=d: dwm_set(fr.hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, d))
            window.evaluate_js(f"setTheme('{theme}')")
            time.sleep(0.6)
            p = OUT / f"{args.mode}_{theme}.png"
            result.setdefault("printwindow_ok", []).append(print_window(p, top))
            result.setdefault("screenshots", []).append(p.name)
        user32.SetCursorPos(saved.x, saved.y)
        if args.actions:
            try:
                result["actions"] = run_actions(top, OUT, args.mode, T)
            except Exception:
                import traceback
                result["actions_error"] = traceback.format_exc()
            user32.SetCursorPos(saved.x, saved.y)

    def on_shown():
        try:
            T('apply_frame')
            ui(apply_frame)
            # wait for CoreWebView2 + first load
            T('wait loaded')
            loaded.wait(15)
            if flags.get("nonclient") and not result.get("IsNonClientRegionSupportEnabled_after"):
                ui(lambda: setattr(window.native.browser.webview.CoreWebView2.Settings,
                                   "IsNonClientRegionSupportEnabled", True))
                result["IsNonClientRegionSupportEnabled_late"] = True
            if flags.get("nonclient"):
                # the setting may only apply to the next navigation: reload the page once
                loaded.clear()
                window.load_url(page.as_uri())
                result["reloaded_loaded_event"] = loaded.wait(15)
                time.sleep(0.8)
            time.sleep(0.6)
            window.evaluate_js(f"document.getElementById('mode').textContent = {json.dumps('mode: ' + args.mode)}")
            if flags.get("nchit"):
                nodrag_from_page()
            if flags.get("carve"):
                ui(carve)
            if args.fix_hover:
                def dump_counts():
                    while True:
                        time.sleep(3)
                        (OUT / "dwm_mouse_counts.json").write_text(json.dumps(
                            {**{f"{NC_MOUSE_NAMES[m]} handled={h}": n for (m, h), n in sorted(fr.dwm_mouse.items())},
                             **{f"dwm hit {HT.get(c, c)}": n for c, n in sorted(fr.dwm_hit.items())},
                             "frame_y": fr.frame_y(), "window_rect": win_rect(fr.hwnd),
                             "caption_button_bounds": dwm_get_rect(fr.hwnd, DWMWA_CAPTION_BUTTON_BOUNDS),
                             "trace": [list(t) for t in fr.hit_trace]},
                            indent=1), encoding="utf-8")
                threading.Thread(target=dump_counts, daemon=True).start()
            T('measure')
            if args.measure:
                run_measure()
        except Exception as e:
            import traceback
            result["error"] = traceback.format_exc()
        finally:
            if args.measure:
                (OUT / f"{args.mode}.json").write_text(json.dumps(result, indent=1, default=str), encoding="utf-8")
                try:
                    window.destroy()
                except Exception:
                    pass

    loaded = threading.Event()
    window.events.loaded += lambda: loaded.set()

    def after_start():
        # `shown` can fire before CoreWebView2 init; apply_frame retries for nonclient in on_shown
        on_shown()

    def kick():
        # `shown` fires once the form exists on the UI thread; never touch Control.Handle before that
        T("kick start")
        T(f"shown wait -> {window.events.shown.wait(30)}")
        # CoreWebView2 must exist before Settings can be touched
        for _ in range(150):
            try:
                if ui(lambda: window.native.browser.webview.CoreWebView2 is not None):
                    T("CoreWebView2 ready")
                    break
            except Exception:
                pass
            time.sleep(0.1)
        after_start()

    store = HERE / f"wv2data-{os.getpid()}"
    store.mkdir(exist_ok=True)
    webview.start(kick, gui="edgechromium", debug=False, storage_path=str(store), private_mode=True)


if __name__ == "__main__":
    main()
