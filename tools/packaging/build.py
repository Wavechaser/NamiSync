"""Build a development portable artifact from an identified source snapshot.

Run in a disposable environment with requirements.txt installed. Output must
not exist; failed attempts remain available for diagnosis.
"""

import argparse
import hashlib
import json
import platform
import shutil
import struct
import subprocess
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def run(*args: str, cwd: Path) -> None:
    subprocess.run(args, cwd=cwd, check=True)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_executable(path: Path, subsystem: int) -> None:
    data = path.read_bytes()
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if data[:2] != b"MZ" or data[pe:pe + 4] != b"PE\0\0":
        raise RuntimeError(f"Not a PE executable: {path}")
    machine = struct.unpack_from("<H", data, pe + 4)[0]
    actual = struct.unpack_from("<H", data, pe + 24 + 68)[0]
    if machine != 0x8664 or actual != subsystem:
        raise RuntimeError(f"Wrong Windows architecture/subsystem: {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if sys.platform != "win32" or platform.machine().lower() not in ("amd64", "x86_64"):
        parser.error("Build on Windows x64 with CPython 3.13")
    if sys.version_info[:2] != (3, 13) or sys.prefix == sys.base_prefix:
        parser.error("Use a disposable CPython 3.13 virtual environment")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    source = output / "source"
    source.mkdir()
    names = subprocess.check_output([
        "git", "ls-files", "-z", "--cached", "--others", "--exclude-standard",
        "namisync", "tools/packaging", "pyproject.toml", "README.md", "LICENSE",
    ], cwd=ROOT).decode().split("\0")
    manifest = {}
    for name in sorted(set(filter(None, names))):
        original = ROOT / name
        destination = source / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        before = digest(original)
        shutil.copyfile(original, destination)
        if digest(destination) != before or digest(original) != before:
            raise RuntimeError(f"Source changed during staging: {name}")
        manifest[name] = before
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
    (output / "source-identity.json").write_text(json.dumps({
        "commit": revision, "files": manifest, "python": sys.version,
        "purpose": "development package; not release acceptance",
    }, indent=2), encoding="utf-8")
    run(sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation",
        "--wheel-dir", str(output / "wheel"), str(source), cwd=output)
    wheel, = (output / "wheel").glob("*.whl")
    run(sys.executable, "-m", "pip", "install", "--no-deps", "--force-reinstall",
        str(wheel), cwd=output)
    run(sys.executable, "-m", "pip", "check", cwd=output)
    run(sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
        "--distpath", str(output / "dist"), "--workpath", str(output / "work"),
        str(source / "tools/packaging/namisync.spec"), cwd=output)
    bundle = output / "dist/NamiSync"
    check_executable(bundle / "namisync.exe", 3)
    check_executable(bundle / "namisync-gui.exe", 2)
    shutil.copyfile(source / "LICENSE", bundle / "LICENSE")
    (bundle / "START-HERE.txt").write_text(
        "NamiSync development package (not a release candidate)\n\n"
        "Extract the whole folder, then run namisync-gui.exe.\n"
        "Requires Windows 11 x64, Microsoft Edge WebView2 Runtime and .NET Framework 4.8.\n"
        "Python installation is not required. No administrator launch is needed.\n"
        "Settings/history use %LOCALAPPDATA%\\NamiSync.\n"
        "For an isolated debug profile: namisync-gui.exe --data-dir C:\\absolute\\new-profile\n"
        "Keep test source/target folders separate from valuable data. Review the plan before Execute.\n"
        "Close the app before replacing its folder. Deleting this folder does not delete application data.\n"
        "namisync.exe is the command-line entry point; run --help for usage.\n",
        encoding="utf-8",
    )
    run(str(bundle / "namisync.exe"), "--help", cwd=output)
    dependencies = subprocess.check_output([sys.executable, "-m", "pip", "freeze"], cwd=output).decode()
    (output / "build-environment.txt").write_text(dependencies, encoding="utf-8")
    archive = Path(shutil.make_archive(str(output / "NamiSync-windows-x64-dev"),
                                    "zip", output / "dist"))
    source_archive = output / "NamiSync-source-dev.zip"
    with zipfile.ZipFile(source_archive, "w", zipfile.ZIP_DEFLATED) as archive_file:
        for name in manifest:
            archive_file.write(source / name, name)
    (output / "SHA256SUMS.txt").write_text(
        f"{digest(archive)}  {archive.name}\n{digest(wheel)}  wheel/{wheel.name}\n"
        f"{digest(source_archive)}  {source_archive.name}\n",
        encoding="utf-8",
    )
    print(f"Development package: {archive}")


if __name__ == "__main__":
    main()
