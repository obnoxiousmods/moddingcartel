# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for moddingcartel.exe
This builds send_to_switch.py into a single Windows executable
"""

import sys
from pathlib import Path
from PyInstaller.utils.hooks import copy_metadata

# Get the project root directory
project_root = Path(SPECPATH)

block_cipher = None

# Collect metadata for packages that need it
datas = []
datas += copy_metadata('aioftp')

a = Analysis(
    ['software/send_to_switch.py'],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'yaml',
        'rich',
        'rich.console',
        'rich.layout',
        'rich.live',
        'rich.panel',
        'rich.table',
        'rich.text',
        'rich._unicode_data',
        'rich._unicode_data._versions',
        'rich._unicode_data.unicode4-1-0',
        'rich._unicode_data.unicode5-0-0',
        'rich._unicode_data.unicode5-1-0',
        'rich._unicode_data.unicode5-2-0',
        'rich._unicode_data.unicode6-0-0',
        'rich._unicode_data.unicode6-1-0',
        'rich._unicode_data.unicode6-2-0',
        'rich._unicode_data.unicode6-3-0',
        'rich._unicode_data.unicode7-0-0',
        'rich._unicode_data.unicode8-0-0',
        'rich._unicode_data.unicode9-0-0',
        'rich._unicode_data.unicode10-0-0',
        'rich._unicode_data.unicode11-0-0',
        'rich._unicode_data.unicode12-0-0',
        'rich._unicode_data.unicode12-1-0',
        'rich._unicode_data.unicode13-0-0',
        'rich._unicode_data.unicode14-0-0',
        'rich._unicode_data.unicode15-0-0',
        'rich._unicode_data.unicode15-1-0',
        'rich._unicode_data.unicode16-0-0',
        'rich._unicode_data.unicode17-0-0',
        'httpx',
        'aioftp',
        'aiofiles',
        'tqdm',
        'software.cartel',
        'software.sphaira',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude unused packages to reduce size
        'matplotlib',
        'numpy',
        'pandas',
        'PIL',
        'tkinter',
        'pytest',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='moddingcartel',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Opens terminal window when double-clicked
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add icon path here if you have one
)
