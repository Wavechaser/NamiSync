"""Summarize drop-log.jsonl: one line per drop. Usage: python read_log.py [logfile]"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "drop-log.jsonl")
sys.stdout.reconfigure(encoding="utf-8")
for line in open(path, encoding="utf-8"):
    r = json.loads(line)
    ev = r["event"]
    if ev == "drop":
        files = [i for i in r["items"] if i.get("path")]
        print(f"DROP #{r['seq']} field={r['field']} mode={r['page'].get('mode')} host_count={r['host_count']} "
              f"native_files={len(files)} elevated={r['elevated']}")
        for i in files:
            print(f"    {'DIR ' if i.get('os_isdir') else 'FILE' if i.get('os_isfile') else '??? '} "
                  f"{i['path']}  (len {len(i['path'])}, drive {i.get('drive')})")
        extra = len(r["items"]) - len(files)
        if extra:
            print(f"    + {extra} object(s) not a CoreWebView2File (null in pythonnet)")
        print(f"    page saw: files={r['page'].get('files')} handle kinds={r['page'].get('handleKinds')}")
    elif ev in ("refused", "host-error", "navigation-starting", "attached", "url-after", "selftest-error"):
        print(ev.upper(), {k: v for k, v in r.items() if k not in ("event", "t")})
