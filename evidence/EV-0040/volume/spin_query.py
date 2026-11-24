"""Run one volume-overview query once against one drive and print a JSON line.

Usage: python spin_query.py <query> <letter>
Read-only: path APIs, zero-access handles; 'positive_read' reads 4 KiB unbuffered
from the first regular file found under the root (a known media access).
"""
import ctypes, json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import probe as p  # noqa: E402

FILE_FLAG_NO_BUFFERING = 0x20000000
GENERIC_READ = 0x80000000


def positive_read(root):
    entries = (e for d, _, files in os.walk(root) for e in os.scandir(d))
    for entry in entries:
        if entry.is_file(follow_symlinks=False) and entry.stat().st_size >= 4096:
            h = p.k32.CreateFileW(entry.path, GENERIC_READ, 1, None, 3, FILE_FLAG_NO_BUFFERING, None)
            if h is None or h == p.INVALID:
                return p.err()
            buf = ctypes.create_string_buffer(4096 + 4096)
            addr = (ctypes.addressof(buf) + 4095) & ~4095
            n = ctypes.c_ulong()
            p.k32.ReadFile.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong,
                                       ctypes.POINTER(ctypes.c_ulong), ctypes.c_void_p]
            okr = p.k32.ReadFile(h, addr, 4096, ctypes.byref(n), None)
            p.k32.CloseHandle(h)
            return p.ok({"file": entry.name, "read": n.value}) if okr else p.err()
    return {"ok": False, "error": "no file >= 4 KiB in root"}


def main():
    query, letter = sys.argv[1], sys.argv[2].upper()
    root, vol = f"{letter}:\\", f"\\\\.\\{letter}:"
    table = {
        "control": lambda: p.ok("no query"),
        "GetLogicalDrives": lambda: p.ok(hex(p.k32.GetLogicalDrives())),
        "GetDriveTypeW": lambda: p.q_drive_type(root),
        "GetVolumeInformationW": lambda: p.q_vol_info(root),
        "GetDiskFreeSpaceExW": lambda: p.q_disk_free(root),
        "CreateFileW0": lambda: p.q_open(vol),
        "device_prop": lambda: p.with_handle(vol, p.q_device_prop),
        "seek_penalty": lambda: p.with_handle(vol, p.q_seek),
        "disk_extents": lambda: p.with_handle(vol, p.q_extents),
        "GetDevicePowerState": lambda: p.with_handle(vol, p.q_power),
        "positive_read": lambda: positive_read(root),
    }
    t = time.perf_counter()
    result = table[query]()
    ms = (time.perf_counter() - t) * 1000
    print(json.dumps({"query": query, "letter": letter, "ms": round(ms, 3), "result": result}))


if __name__ == "__main__":
    main()
