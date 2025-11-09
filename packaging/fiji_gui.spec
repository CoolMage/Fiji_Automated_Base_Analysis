# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for building the Fiji GUI as a standalone desktop app."""
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

PROJECT_ROOT = Path(__file__).resolve().parent.parent

hiddenimports = collect_submodules("utils") + collect_submodules("examples")

datas = [
    (str(PROJECT_ROOT / "examples" / "sample_documents"), "examples/sample_documents"),
]

# Include top-level resources that are imported dynamically at runtime.
for resource in ("config.py", "core_processor.py", "main.py"):
    datas.append((str(PROJECT_ROOT / resource), "."))

a = Analysis(
    [str(PROJECT_ROOT / "gui.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FijiProcessorGUI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=sys.platform == "darwin",
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="FijiProcessorGUI",
)
