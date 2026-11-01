# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import os

# Prefer Windows' own ICU over same-named DLLs from unrelated tools on PATH.
# Qt uses the Windows ICU API; a Poppler/Conda ICU may export incompatible names.
system32 = Path(os.environ.get("WINDIR", "C:/Windows")) / "System32"
os.environ["PATH"] = str(system32) + os.pathsep + os.environ.get("PATH", "")

project = Path(SPECPATH)
a = Analysis(
    [str(project / "main.py")],
    pathex=[str(project)],
    binaries=[],
    datas=[(str(project / "assets"), "assets")],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=["PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name="ZuJiChangZheng",
    debug=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)
