"""Two Windows entry points sharing one portable dependency directory."""
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, copy_metadata

root = Path(SPECPATH).parents[1]
icon = str(root / "namisync/interfaces/branding/namisync.ico")
datas = collect_data_files("namisync") + copy_metadata("namisync", recursive=True)
executables = []
binaries = []
collected = []
for shim, name, console in (
    ("console.py", "namisync", True),
    ("desktop.py", "namisync-gui", False),
):
    analysis = Analysis(
        [str(Path(SPECPATH) / shim)],
        pathex=[], datas=datas, binaries=[],
        hiddenimports=["webview.platforms.winforms", "webview.platforms.edgechromium"],
        excludes=["PyQt5", "PyQt6", "PySide2", "PySide6", "webview.platforms.cef"],
    )
    archive = PYZ(analysis.pure)
    executables.append(EXE(
        archive, analysis.scripts, [], exclude_binaries=True,
        name=name, console=console, icon=icon, upx=False,
    ))
    binaries.extend(analysis.binaries)
    collected.extend(analysis.datas)
COLLECT(*executables, binaries, collected, name="NamiSync", upx=False)
