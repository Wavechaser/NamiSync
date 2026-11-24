"""Controlled geometry/message-routing experiments on the EV-0042 prototype."""
import ctypes
import importlib.util
import json
import shutil
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
shutil.copyfile(ROOT / "evidence/EV-0042/framing-proto.py", HERE / "baseline.py")
spec = importlib.util.spec_from_file_location("baseline", HERE / "baseline.py")
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
p.HERE = HERE
p.OUT = HERE / "out"
p.OUT.mkdir(exist_ok=True)
current = {"name": "baseline"}
instance = None


class Framing(p.Framing):
    def __init__(self, flags):
        super().__init__(flags)
        global instance
        instance = self

    def _proc(self, hwnd, msg, wp, lp, uid, ref):
        if msg == p.WM_NCCALCSIZE and wp:
            params = ctypes.cast(lp, ctypes.POINTER(p.NCCALCSIZE_PARAMS)).contents
            original = params.rgrc[0].top
            result = p.comctl32.DefSubclassProc(hwnd, msg, wp, lp)
            if current.get("stock"):
                return result
            inset = current.get("inset", self.frame_y()) if self.is_max() else 0
            params.rgrc[0].top = original + inset
            return 0 if current.get("zero_return") else result
        if msg == p.WM_NCHITTEST and current.get("default_first"):
            result = p.comctl32.DefSubclassProc(hwnd, msg, wp, lp)
            if current.get("default_only"):
                return result
        if msg == p.WM_NCHITTEST and current.get("native_hit") and self.is_max():
            lr = p.LRESULT()
            if p.dwmapi.DwmDefWindowProc(hwnd, msg, wp, lp, ctypes.byref(lr)):
                self.hit_trace.append((p.signed(lp), p.signed(lp >> 16), True,
                                       p.HT.get(lr.value), p.HT.get(lr.value)))
                del self.hit_trace[:-400]
                return lr.value
        result = super()._proc(hwnd, msg, wp, lp, uid, ref)
        if msg in (p.WM_SIZE, 0x02E0) and self.wv_hwnd:
            layout()
        return result


p.Framing = Framing
original_carve = p.carve_apply


def carve(fr, result=None):
    if not (fr.is_max() and current.get("correct_carve")):
        return original_carve(fr, result)
    cr = p.wintypes.RECT()
    p.user32.GetClientRect(p.wintypes.HWND(fr.wv_hwnd), ctypes.byref(cr))
    org = p.wintypes.POINT()
    p.user32.ClientToScreen(p.wintypes.HWND(fr.wv_hwnd), ctypes.byref(org))
    region = p.gdi32.CreateRectRgn(0, 0, cr.right, cr.bottom)
    title = titlebar()
    for i in (2, 3, 5):
        r = title.rgrect[i]
        hole = p.gdi32.CreateRectRgn(r.left - org.x, r.top - org.y,
                                   r.right - org.x, r.bottom - org.y)
        p.gdi32.CombineRgn(region, region, hole, 4)
        p.gdi32.DeleteObject(hole)
    p.user32.SetWindowRgn(p.wintypes.HWND(fr.wv_hwnd), region, True)


p.carve_apply = carve


class TITLEBARINFOEX(ctypes.Structure):
    _fields_ = [("cbSize", p.wintypes.DWORD), ("rcTitleBar", p.wintypes.RECT),
                ("rgstate", p.wintypes.DWORD * 6), ("rgrect", p.wintypes.RECT * 6)]


def titlebar():
    title = TITLEBARINFOEX()
    title.cbSize = ctypes.sizeof(title)
    p.user32.SendMessageW(instance.hwnd, 0x033F, 0, ctypes.addressof(title))
    return title


def layout():
    import webview
    from System.Windows.Forms import Padding
    fr = instance
    form = webview.windows[0].native
    inset = fr.frame_y() if fr.is_max() and current.get("pad") else 0
    if form.Padding.Top != inset:
        form.Padding = Padding(0, inset, 0, 0)
    p.carve_apply(fr)


def ui(fn):
    import webview
    from System import Action
    result = {}

    def invoke():
        try:
            result["value"] = fn()
        except Exception as exc:
            result["error"] = repr(exc)
    webview.windows[0].native.Invoke(Action(invoke))
    if "error" in result:
        raise RuntimeError(result["error"])
    return result.get("value")


def geometry():
    fr = instance
    client = p.wintypes.RECT()
    org = p.wintypes.POINT()
    p.user32.GetClientRect(p.wintypes.HWND(fr.hwnd), ctypes.byref(client))
    p.user32.ClientToScreen(p.wintypes.HWND(fr.hwnd), ctypes.byref(org))
    child_org = p.wintypes.POINT()
    p.user32.ClientToScreen(p.wintypes.HWND(fr.wv_hwnd), ctypes.byref(child_org))
    return {"window": p.win_rect(fr.hwnd), "client_origin": [org.x, org.y],
            "webview_origin": [child_org.x, child_org.y], "webview_rect": p.win_rect(fr.wv_hwnd),
            "client_size": [client.right, client.bottom], "frame": fr.frame_y(),
            "maximized": fr.is_max(), "dpi": p.user32.GetDpiForWindow(fr.hwnd),
            "buttons": p.dwm_get_rect(fr.hwnd, p.DWMWA_CAPTION_BUTTON_BOUNDS)[1],
            "extended": p.dwm_get_rect(fr.hwnd, p.DWMWA_EXTENDED_FRAME_BOUNDS)[1]}


def sample():
    fr = instance
    g = geometry()
    wl, wt, wr, wb = g["window"]
    # Direct API diagnostic on the owning UI thread: no cursor/input injection.
    hits = []
    for y in range(max(0, wt), max(0, wt) + 100, 5):
        for x in range(wr - 300, wr, 10):
            lr = p.LRESULT()
            handled = p.dwmapi.DwmDefWindowProc(fr.hwnd, p.WM_NCHITTEST, 0, p.pack(x, y), ctypes.byref(lr))
            if handled:
                hits.append([x, y, lr.value])
    title = titlebar()
    button_points = []
    for i, expected in ((2, 8), (3, 9), (5, 20)):
        r = title.rgrect[i]
        for x, y in ((r.left, r.top), (r.right-1, r.top), (r.left, r.bottom-1),
                     (r.right-1, r.bottom-1), ((r.left+r.right)//2, (r.top+r.bottom)//2)):
            actual = p.user32.SendMessageW(fr.hwnd, p.WM_NCHITTEST, 0, p.pack(x, y))
            receiver = p.user32.WindowFromPoint(p.wintypes.POINT(x, y))
            button_points.append({"point": [x,y], "expected": expected,
                                  "actual": actual, "receiver_is_form": receiver == fr.hwnd})
    return {"config": dict(current), "geometry": g, "dwm_handled_grid": hits,
            "button_points": button_points,
            "titlebar_rects": [[r.left, r.top, r.right, r.bottom] for r in title.rgrect],
            "titlebar_states": list(title.rgstate)}


def apply(command):
    import webview
    from System.Windows.Forms import FormWindowState
    fr = instance
    current.clear()
    current.update(command)
    form = webview.windows[0].native
    form.Text = "NamiSync maximized probe [" + current["name"] + "]"
    if "maximized" in current:
        form.WindowState = FormWindowState.Maximized if current["maximized"] else FormWindowState.Normal
    margins = current.get("margins", [-1, -1, -1, -1])
    m = p.MARGINS(*margins)
    p.dwmapi.DwmExtendFrameIntoClientArea(p.wintypes.HWND(fr.hwnd), ctypes.byref(m))
    p.user32.SetWindowPos(p.wintypes.HWND(fr.hwnd), None, 0, 0, 0, 0, 0x37)
    layout()
    fr.hit_trace.clear()
    fr.dwm_mouse.clear()


def worker():
    last = None
    while not instance or not instance.wv_hwnd:
        time.sleep(.2)
    time.sleep(2)
    while True:
        try:
            path = HERE / "command.json"
            raw = path.read_text(encoding="utf-8-sig") if path.exists() else '{"name":"baseline"}'
            if raw != last:
                command = json.loads(raw)
                ui(lambda: apply(command))
                time.sleep(.5)
                result = ui(sample)
                (p.OUT / (command["name"] + ".json")).write_text(json.dumps(result, indent=2), encoding="utf-8")
                last = raw
            live = {"config": current, "geometry": ui(geometry), "hits": instance.hit_trace[-80:]}
            (p.OUT / "live.json").write_text(json.dumps(live, indent=2), encoding="utf-8")
        except Exception as exc:
            (p.OUT / "error.txt").write_text(repr(exc), encoding="utf-8")
        time.sleep(.5)


threading.Thread(target=worker, daemon=True).start()
sys.argv = [sys.argv[0], "--mode", "nonclient_carve", "--fix-hover", "--fix-theme", "--interactive"]
p.main()
