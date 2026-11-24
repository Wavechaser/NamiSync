"""NamiSync M2-A2 drag-and-drop path spike. Read-only toward the product.

Usage (from repo root):
  .venv\\Scripts\\python.exe build\\m2-a2\\drop\\spike.py              # interactive
  .venv\\Scripts\\python.exe build\\m2-a2\\drop\\spike.py --selftest   # CDP-synthesized drops, auto-exit
  ... --no-prevent    # page does not preventDefault (does WebView2 navigate to a dropped file?)
Log: build\\m2-a2\\drop\\drop-log.jsonl (one JSON object per line, truncated each run)
"""
import ctypes
import json
import os
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "drop-log.jsonl")
UDF = os.path.join(HERE, "webview2-userdata")
FIX = os.path.join(HERE, "fixtures")
MAX_HOST_ITEMS = 4          # host-side bound: more is refused, not truncated
MAX_MESSAGE_CHARS = 8192    # host-side bound on the JSON message text
SELFTEST = "--selftest" in sys.argv
PREVENT = "--no-prevent" not in sys.argv

import webview  # noqa: E402
import clr  # noqa: E402,F401
from System import Func, Object  # noqa: E402

_lock = threading.Lock()


def log(**kw):
    kw["t"] = round(time.time(), 3)
    with _lock, open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(kw, ensure_ascii=False) + "\n")


def elevated():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return None


def on_message(sender, args):
    try:
        text = str(args.WebMessageAsJson)
        if len(text) > MAX_MESSAGE_CHARS:
            log(event="refused", reason="message-too-long", chars=len(text))
            return
        msg = json.loads(text)
        if isinstance(msg, str):
            msg = json.loads(msg)
        objs = args.AdditionalObjects
        count = 0 if objs is None else int(objs.Count)
        if count > MAX_HOST_ITEMS:
            log(event="refused", reason="too-many-items", count=count, field=msg.get("field"))
            return
        items = []
        for o in (list(objs) if objs is not None else []):
            if o is None:
                items.append({"type": "None"})
                continue
            rec = {"type": str(type(o)), "clr": str(o.GetType().FullName) if hasattr(o, "GetType") else None}
            for attr in ("Path", "IsDirectory", "Name", "Kind"):
                try:
                    v = getattr(o, attr)
                    rec[attr.lower()] = bool(v) if attr == "IsDirectory" else str(v)
                except Exception:
                    pass
            p = rec.get("path")
            if p:
                rec["os_isdir"] = os.path.isdir(p)
                rec["os_isfile"] = os.path.isfile(p)
                rec["drive"] = os.path.splitdrive(p)[0]
            items.append(rec)
        log(event="drop", field=msg.get("field"), seq=msg.get("seq"), host_count=count,
            page=msg, items=items, elevated=elevated())
    except Exception as e:
        log(event="host-error", error=repr(e))


def nav_log(sender, args):
    log(event="navigation-starting", uri=str(args.Uri))


def run(window):
    if SELFTEST:
        threading.Thread(target=selftest, args=(window,), daemon=True).start()


def cdp(window, method, params):
    form = window.native
    t = form.Invoke(Func[Object](lambda: form.browser.webview.CoreWebView2.CallDevToolsProtocolMethodAsync(
        method, json.dumps(params))))
    if not t.Wait(8000):
        raise TimeoutError('CDP call did not complete in 8s: ' + method)
    return t.Result


def synth_drop(window, el, paths, label):
    x, y = window.evaluate_js(
        "(()=>{const r=document.getElementById('%s').getBoundingClientRect();"
        "return [r.x+r.width/2,r.y+r.height/2]})()" % el)
    data = {"items": [], "files": paths, "dragOperationsMask": 1}
    try:
        for typ in ("dragEnter", "dragOver", "drop"):
            cdp(window, "Input.dispatchDragEvent", {"type": typ, "x": x, "y": y, "data": data})
        log(event="selftest-sent", label=label, target=el, paths=paths)
    except Exception as e:
        log(event="selftest-error", label=label, error=repr(e))
    time.sleep(1.5)


def selftest(window):
    window.events.loaded.wait(60)
    time.sleep(2)

    def d(*p):
        return os.path.join(FIX, *p)

    log(event="selftest-start", elevated=elevated())
    if not PREVENT:
        synth_drop(window, "source", [d("folder_a")], "no-preventDefault: one folder")
        time.sleep(3)
        log(event="url-after", url=str(window.get_current_url()))
        window.destroy()
        return
    for mode in ("handles", "files", "both"):
        window.evaluate_js("window.__mode='%s'" % mode)
        synth_drop(window, "source", [d("folder_a")], "[%s] one folder" % mode)
        synth_drop(window, "destination", [d("file_1.txt")], "[%s] one file" % mode)
        synth_drop(window, "source", [d("folder_a"), d("folder_b")], "[%s] two folders" % mode)
    window.evaluate_js("window.__mode='both'")
    synth_drop(window, "destination", [d("folder_ü_日本語")], "unicode folder")
    long_dir = d("longpath")
    if os.path.isdir(long_dir):
        deep = long_dir
        while True:
            subs = os.listdir(deep)
            if not subs:
                break
            deep = os.path.join(deep, subs[0])
        synth_drop(window, "source", [deep], "long path (%d chars)" % len(deep))
    synth_drop(window, "source", [d("f%d" % i) for i in range(6)], "six items (host bound 4)")
    log(event="selftest-done")
    time.sleep(0.5)
    window.destroy()


def attach(window):
    core = window.native.browser.webview.CoreWebView2
    core.WebMessageReceived += on_message
    core.NavigationStarting += nav_log
    log(event="attached", runtime=str(core.Environment.BrowserVersionString),
        allow_external_drop=str(getattr(window.native.browser.webview, "AllowExternalDrop", "n/a")),
        elevated=elevated())


if __name__ == "__main__":
    os.makedirs(UDF, exist_ok=True)
    open(LOG, "w").close()
    webview.settings["ALLOW_FILE_URLS"] = False
    url = os.path.join(HERE, "page.html")
    if not PREVENT:
        src = open(url, encoding="utf-8").read().replace("params.get('prevent') !== '0'", "false")
        url = os.path.join(HERE, "page_noprevent.html")
        open(url, "w", encoding="utf-8").write(src)
    window = webview.create_window("drop spike", url, width=800, height=600)
    def _attach():
        log(event="before_load-fired")
        try:
            attach(window)
        except Exception as e:
            log(event="attach-error", error=repr(e))
    window.events.before_load += _attach
    window.events.loaded += lambda: log(event="loaded")
    window.events.shown += lambda: log(event="shown")
    webview.start(run, window, gui="edgechromium", private_mode=False, storage_path=UDF, http_server=True)
    log(event="exited")
