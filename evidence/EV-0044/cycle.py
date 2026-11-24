"""Cycle a running framing prototype through maximize/restore twice and print restored sizes.

usage: cycle.py <pid>
"""
import ctypes
import sys
import time
from ctypes import wintypes

user32 = ctypes.WinDLL("user32")
pid = int(sys.argv[1])
found = []
CB = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def cb(h, _):
    p = wintypes.DWORD()
    user32.GetWindowThreadProcessId(h, ctypes.byref(p))
    if user32.IsWindowVisible(h):
        n = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(h, n, 256)
        if "framing" in n.value:
            found.append(h)
    return True


user32.EnumWindows(CB(cb), 0)
h = found[0]


def size():
    r = wintypes.RECT()
    user32.GetWindowRect(h, ctypes.byref(r))
    return (r.right - r.left, r.bottom - r.top)


sizes = [size()]
for _ in range(2):
    user32.SendMessageW(h, 0x0112, 0xF030, 0)  # SC_MAXIMIZE
    time.sleep(1.0)
    user32.SendMessageW(h, 0x0112, 0xF120, 0)  # SC_RESTORE
    time.sleep(1.0)
    sizes.append(size())
print(sizes)
