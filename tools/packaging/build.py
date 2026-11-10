"""Build a development portable artifact from clean committed source.

Run in a disposable environment with requirements.txt installed. Output must
not exist; failed attempts remain available for diagnosis.
"""

import argparse
import ast
import hashlib
import io
import json
import os
import platform
import shutil
import struct
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from importlib.metadata import distributions
from pathlib import Path

if __package__:
    from .notices import write_notices
else:
    from notices import write_notices

ROOT = Path(__file__).resolve().parents[2]
SOURCE_PATHS = ("namisync", "tools/packaging", "pyproject.toml", "README.md", "LICENSE", ".gitattributes")


def source_snapshot(root: Path) -> tuple[str, int, bytes]:
    if subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=all"], cwd=root):
        raise RuntimeError("Build requires a clean checkout; commit or isolate changes first")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root).decode().strip()
    epoch = int(subprocess.check_output(["git", "show", "-s", "--format=%ct", revision], cwd=root))
    archive = subprocess.check_output([
        "git", "-c", "core.autocrlf=false", "-c", "core.eol=lf",
        "archive", "--format=zip", revision, *SOURCE_PATHS,
    ], cwd=root)
    return revision, epoch, archive


def check_environment(directory: Path) -> dict[str, str]:
    normalize = lambda name: name.lower().replace("_", "-").replace(".", "-")
    expected = {}
    for name in ("bootstrap.txt", "requirements.txt"):
        for line in (directory / name).read_text(encoding="utf-8").splitlines():
            if line and not line.startswith(("#", "-")):
                package, version = line.split()[0].split("==")
                expected[normalize(package)] = version
    actual = {normalize(item.metadata["Name"]): item.version for item in distributions()}
    actual.pop("namisync", None)  # Replaced with this build's wheel before freezing.
    if actual != expected:
        raise RuntimeError(f"Build environment differs from lock: expected {expected}, got {actual}")
    return actual


def write_archive(path: Path, base: Path, names: list[str], epoch: int) -> None:
    timestamp = datetime.fromtimestamp(epoch, timezone.utc).timetuple()[:6]
    with zipfile.ZipFile(path, "x", zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(names):
            entry = zipfile.ZipInfo(name, timestamp)
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, (base / name).read_bytes())


def run(*args: str, cwd: Path, env: dict[str, str] | None = None) -> None:
    subprocess.run(args, cwd=cwd, check=True, env=env)


def freezer_environment() -> dict[str, str]:
    """Do not let unrelated applications on PATH supply bundled DLLs."""
    windows = Path(os.environ["SystemRoot"])
    environment = os.environ.copy()
    environment["PATH"] = os.pathsep.join(str(path) for path in (
        Path(sys.prefix) / "Scripts", Path(sys.base_prefix),
        Path(sys.base_prefix) / "DLLs", windows / "System32", windows,
    ))
    return environment


def record_native_origins(work: Path, bundle: Path, output: Path) -> None:
    """Bind collected native bytes to the locked environment/Python installation."""
    roots = (Path(sys.prefix).resolve(), Path(sys.base_prefix).resolve())
    rows = []
    entries = ast.literal_eval((work / "COLLECT-00.toc").read_text(encoding="utf-8"))[0]
    for name, source, kind in entries:
        if kind not in {"BINARY", "EXTENSION"}:
            continue
        path = Path(source).resolve()
        if not any(path.is_relative_to(root) for root in roots):
            raise RuntimeError(f"Native input outside build environment/Python: {path}")
        lowered = Path(name).name.lower()
        if lowered == "ucrtbase.dll" or lowered.startswith(("api-ms-win-core-", "api-ms-win-crt-")):
            raise RuntimeError(f"Windows-provided runtime must not be bundled: {name}")
        destination = bundle / "_internal" / name
        sha256 = digest(path)
        if digest(destination) != sha256:
            raise RuntimeError(f"Collected native bytes differ from input: {name}")
        rows.append({"path": name, "source": str(path), "kind": kind, "sha256": sha256})
    (output / "native-origins.json").write_text(json.dumps({
        "native_files": rows,
        "scope": "COLLECT BINARY/EXTENSION inputs; raw freezer tables also retain embedded/bootloader inputs",
    }, indent=2), encoding="utf-8")
    tables = output / "freezer-tables"
    tables.mkdir()
    for path in sorted(work.glob("*.toc")):
        shutil.copyfile(path, tables / path.name)


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
        parser.error("Build on Windows x64 with CPython 3.15.2")
    if platform.python_implementation() != "CPython" or sys.version_info[:3] != (3, 15, 2) or sys.prefix == sys.base_prefix:
        parser.error("Use a disposable CPython 3.15.2 virtual environment")
    revision, epoch, committed = source_snapshot(ROOT)
    dependencies = check_environment(ROOT / "tools/packaging")
    os.environ["SOURCE_DATE_EPOCH"] = str(epoch)
    os.environ["PYTHONHASHSEED"] = "0"
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    source = output / "source"
    source.mkdir()
    manifest = {}
    with zipfile.ZipFile(io.BytesIO(committed)) as archive:
        for name in sorted(archive.namelist()):
            if name.endswith("/"):
                continue
            destination = source / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(archive.read(name))
            manifest[name] = digest(destination)
    (output / "source-identity.json").write_text(json.dumps({
        "commit": revision, "files": manifest, "python": sys.version,
        "python_executable_sha256": digest(Path(sys.base_prefix) / "python.exe"),
        "platform": platform.platform(), "source_date_epoch": epoch,
        "dependencies": dependencies,
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
        str(source / "tools/packaging/namisync.spec"), cwd=output, env=freezer_environment())
    bundle = output / "dist/NamiSync"
    record_native_origins(output / "work/namisync", bundle, output)
    check_executable(bundle / "namisync.exe", 3)
    check_executable(bundle / "namisync-gui.exe", 2)
    shutil.copyfile(source / "LICENSE", bundle / "LICENSE")
    for name in ("START-HERE.txt", "BUILDING.txt"):
        shutil.copyfile(source / "tools/packaging" / name, bundle / name)
    write_notices(source, bundle)
    run(str(bundle / "namisync.exe"), "--help", cwd=output)
    frozen = subprocess.check_output([sys.executable, "-m", "pip", "freeze", "--all"], cwd=output).decode()
    (output / "build-environment.txt").write_text(frozen, encoding="utf-8")
    bundle_files = sorted(p.relative_to(output / "dist").as_posix()
                          for p in bundle.rglob("*") if p.is_file())
    (output / "bundle-identity.json").write_text(json.dumps({
        name: digest(output / "dist" / name) for name in bundle_files
    }, indent=2), encoding="utf-8")
    archive = output / "NamiSync-windows-x64-dev.zip"
    write_archive(archive, output / "dist", bundle_files, epoch)
    source_archive = output / "NamiSync-source-dev.zip"
    write_archive(source_archive, source, list(manifest), epoch)
    (output / "SHA256SUMS.txt").write_text(
        f"{digest(archive)}  {archive.name}\n{digest(wheel)}  wheel/{wheel.name}\n"
        f"{digest(source_archive)}  {source_archive.name}\n",
        encoding="utf-8",
    )
    print(f"Development package: {archive}")


if __name__ == "__main__":
    main()
