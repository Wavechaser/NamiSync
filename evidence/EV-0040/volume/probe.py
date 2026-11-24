"""M2-A2 volume overview probe. Read-only: zero-access handles and path APIs only.

Usage: python probe.py [--reps N] [--out file.json]
"""
import argparse, ctypes, json, os, shutil, statistics, string, struct, sys, threading, time
from ctypes import wintypes as W

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
adv = ctypes.WinDLL("advapi32", use_last_error=True)
INVALID = ctypes.c_void_p(-1).value
k32.CreateFileW.restype = ctypes.c_void_p
k32.CreateFileW.argtypes = [W.LPCWSTR, W.DWORD, W.DWORD, ctypes.c_void_p, W.DWORD, W.DWORD, ctypes.c_void_p]
k32.CloseHandle.argtypes = [ctypes.c_void_p]
k32.DeviceIoControl.argtypes = [ctypes.c_void_p, W.DWORD, ctypes.c_void_p, W.DWORD,
                                ctypes.c_void_p, W.DWORD, ctypes.POINTER(W.DWORD), ctypes.c_void_p]
k32.GetDevicePowerState.argtypes = [ctypes.c_void_p, ctypes.POINTER(W.BOOL)]
k32.GetCurrentProcess.restype = ctypes.c_void_p
adv.OpenProcessToken.argtypes = [ctypes.c_void_p, W.DWORD, ctypes.POINTER(ctypes.c_void_p)]
adv.GetTokenInformation.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, W.DWORD, ctypes.POINTER(W.DWORD)]

SHARE = 3  # READ|WRITE
OPEN_EXISTING = 3
IOCTL_STORAGE_QUERY_PROPERTY = 0x002D1400
IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS = 0x00560000
BUS = {0: "Unknown", 1: "SCSI", 2: "ATAPI", 3: "ATA", 4: "1394", 5: "SSA", 6: "Fibre", 7: "USB", 8: "RAID",
       9: "iSCSI", 10: "SAS", 11: "SATA", 12: "SD", 13: "MMC", 14: "Virtual", 15: "FileBackedVirtual",
       16: "Spaces", 17: "NVMe", 18: "SCM", 19: "UFS"}
DTYPE = {0: "UNKNOWN", 1: "NO_ROOT_DIR", 2: "REMOVABLE", 3: "FIXED", 4: "REMOTE", 5: "CDROM", 6: "RAMDISK"}


def ok(v=None, **kw):
    return {"ok": True, "value": v, **kw}


def err(code=None):
    return {"ok": False, "error": code if code is not None else ctypes.get_last_error()}


def timed(fn):
    t = time.perf_counter()
    r = fn()
    return r, (time.perf_counter() - t) * 1000


def token_info():
    h = ctypes.c_void_p()
    adv.OpenProcessToken(k32.GetCurrentProcess(), 0x8, ctypes.byref(h))  # TOKEN_QUERY
    out = {}
    for name, cls in (("TokenElevation", 20), ("TokenElevationType", 18)):
        v = W.DWORD(); n = W.DWORD()
        adv.GetTokenInformation(h, cls, ctypes.byref(v), 4, ctypes.byref(n))
        out[name] = v.value
    out["meaning"] = "TokenElevation 0 = not elevated; TokenElevationType 1=Default 2=Full(elevated) 3=Limited"
    out["IsUserAnAdmin"] = bool(ctypes.windll.shell32.IsUserAnAdmin())
    k32.CloseHandle(h)
    return out


def open0(path):
    h = k32.CreateFileW(path, 0, SHARE, None, OPEN_EXISTING, 0, None)
    if h is None or h == INVALID:
        return None, ctypes.get_last_error()
    return h, 0


def q_drive_type(root):
    return ok(DTYPE.get(k32.GetDriveTypeW(root), "?"))


def q_vol_info(root):
    label = ctypes.create_unicode_buffer(261); fs = ctypes.create_unicode_buffer(261)
    ser = W.DWORD(); mcl = W.DWORD(); fl = W.DWORD()
    if k32.GetVolumeInformationW(root, label, 261, ctypes.byref(ser), ctypes.byref(mcl), ctypes.byref(fl), fs, 261):
        return ok({"label": label.value, "serial": "%08X" % ser.value, "fs": fs.value})
    return err()


def q_disk_free(root):
    a = ctypes.c_ulonglong(); t = ctypes.c_ulonglong(); f = ctypes.c_ulonglong()
    if k32.GetDiskFreeSpaceExW(root, ctypes.byref(a), ctypes.byref(t), ctypes.byref(f)):
        return ok({"avail": a.value, "total": t.value, "free": f.value})
    return err()


def q_shutil(root):
    try:
        u = shutil.disk_usage(root)
        return ok({"total": u.total, "used": u.used, "free": u.free})
    except OSError as e:
        return err(getattr(e, "winerror", None) or e.errno)


def q_open(vol):
    h, e = open0(vol)
    if h is None:
        return err(e)
    k32.CloseHandle(h)
    return ok()


def ioctl(h, code, inbuf, outsize):
    out = ctypes.create_string_buffer(outsize); ret = W.DWORD()
    ib = ctypes.create_string_buffer(inbuf, len(inbuf)) if inbuf else None
    if k32.DeviceIoControl(h, code, ib, len(inbuf) if inbuf else 0, out, outsize, ctypes.byref(ret), None):
        return out.raw[:ret.value], 0
    return None, ctypes.get_last_error()


def _cstr(buf, off):
    if not off or off >= len(buf):
        return ""
    return buf[off:buf.index(b"\0", off)].decode("ascii", "replace").strip()


def parse_device(b):
    # STORAGE_DEVICE_DESCRIPTOR
    _v, _s, devtype, devmod, removable, _cq, vend, prod, rev, ser, bus = struct.unpack_from("<IIBBBBIIIII", b, 0)
    return {"BusType": BUS.get(bus, bus), "RemovableMedia": bool(removable), "DeviceType": devtype,
            "vendor": _cstr(b, vend), "product": _cstr(b, prod), "revision": _cstr(b, rev)}


def q_device_prop(h):
    # STORAGE_PROPERTY_QUERY: PropertyId=0 StorageDeviceProperty, QueryType=0 Standard
    b, e = ioctl(h, IOCTL_STORAGE_QUERY_PROPERTY, struct.pack("<II4s", 0, 0, b"\0" * 4), 1024)
    return ok(parse_device(b)) if b else err(e)


def q_seek(h):
    # PropertyId=7 StorageDeviceSeekPenaltyProperty
    b, e = ioctl(h, IOCTL_STORAGE_QUERY_PROPERTY, struct.pack("<II4s", 7, 0, b"\0" * 4), 64)
    if not b:
        return err(e)
    return ok({"IncursSeekPenalty": bool(struct.unpack_from("<IIB", b, 0)[2])})


def q_extents(h):
    b, e = ioctl(h, IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS, None, 4096)
    if not b:
        return err(e)
    n = struct.unpack_from("<I", b, 0)[0]
    disks = [struct.unpack_from("<I", b, 8 + i * 24)[0] for i in range(n)]
    return ok({"extents": n, "disks": disks})


def q_power(h):
    st = W.BOOL()
    if k32.GetDevicePowerState(h, ctypes.byref(st)):
        return ok("ON" if st.value else "OFF(low power)")
    return err()


def with_handle(path, fn):
    h, e = open0(path)
    if h is None:
        return err(e)
    try:
        return fn(h)
    finally:
        k32.CloseHandle(h)


def stats(ms):
    return {"min": round(min(ms), 3), "median": round(statistics.median(ms), 3), "max": round(max(ms), 3),
            "first": round(ms[0], 3)}


def bench(fn, reps):
    ms = []; last = None
    for _ in range(reps):
        last, d = timed(fn); ms.append(d)
    return {"result": last, "ms": stats(ms)}


def run_unc(label, fn, timeout=30.0):
    box = {}
    def w():
        t = time.perf_counter(); box["r"] = fn(); box["ms"] = (time.perf_counter() - t) * 1000
    th = threading.Thread(target=w, daemon=True)
    t0 = time.perf_counter(); th.start(); th.join(timeout)
    if th.is_alive():
        return {"query": label, "completed": False, "waited_s": round(time.perf_counter() - t0, 2),
                "note": "worker still blocked at outer timeout; abandoned (daemon thread)"}
    return {"query": label, "completed": True, "ms": round(box["ms"], 1), "result": box["r"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=20)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "results.json"))
    ap.add_argument("--unc-timeout", type=float, default=30.0)
    a = ap.parse_args()
    res = {"token": token_info(), "python": sys.version}
    mask = k32.GetLogicalDrives()
    letters = [c for i, c in enumerate(string.ascii_uppercase) if mask >> i & 1]
    res["GetLogicalDrives"] = {"mask": hex(mask), "letters": letters}
    res["drives"] = {}
    for L in letters:
        root, vol = f"{L}:\\", f"\\\\.\\{L}:"
        d = {}
        d["GetDriveTypeW"] = bench(lambda: q_drive_type(root), a.reps)
        d["GetVolumeInformationW"] = bench(lambda: q_vol_info(root), a.reps)
        d["GetDiskFreeSpaceExW"] = bench(lambda: q_disk_free(root), a.reps)
        d["shutil.disk_usage"] = bench(lambda: q_shutil(root), a.reps)
        d["CreateFileW(0)"] = bench(lambda: q_open(vol), a.reps)
        # full sequence on one handle, as the product would do it
        d["handle_seq(open+device+seek+extents+close)"] = bench(lambda: with_handle(vol, lambda h: {
            "device": q_device_prop(h), "seek": q_seek(h), "extents": q_extents(h)}), a.reps)
        d["IOCTL device_prop (handle open)"] = bench_handle(vol, q_device_prop, a.reps)
        d["IOCTL seek_penalty (handle open)"] = bench_handle(vol, q_seek, a.reps)
        d["IOCTL disk_extents (handle open)"] = bench_handle(vol, q_extents, a.reps)
        d["GetDevicePowerState(volume)"] = bench_handle(vol, q_power, a.reps)
        res["drives"][L] = d
    # physical disks: power state + properties, disk numbers from extents
    disks = sorted({n for L in letters for n in
                    (res["drives"][L]["IOCTL disk_extents (handle open)"]["result"].get("value") or {}).get("disks", [])})
    res["physical"] = {}
    for n in disks:
        p = f"\\\\.\\PhysicalDrive{n}"
        res["physical"][n] = {
            "open": bench(lambda: q_open(p), a.reps),
            "device_prop": bench_handle(p, q_device_prop, a.reps),
            "seek": bench_handle(p, q_seek, a.reps),
            "power": bench_handle(p, q_power, a.reps)}
    # UNC unresponsive path (nothing mapped)
    unc = "\\\\192.0.2.1\\share\\"
    res["unc"] = {"path": unc, "timeout_s": a.unc_timeout, "runs": [
        run_unc("GetDriveTypeW", lambda: q_drive_type(unc), a.unc_timeout),
        run_unc("GetVolumeInformationW", lambda: q_vol_info(unc), a.unc_timeout),
        run_unc("GetDiskFreeSpaceExW", lambda: q_disk_free(unc), a.unc_timeout)]}
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
    print("wrote", a.out)


def bench_handle(path, q, reps):
    """Open handle once, time only the query (handle open cost measured separately)."""
    h, e = open0(path)
    if h is None:
        return {"result": err(e), "ms": None}
    try:
        return bench(lambda: q(h), reps)
    finally:
        k32.CloseHandle(h)


if __name__ == "__main__":
    main()
