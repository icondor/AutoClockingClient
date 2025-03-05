# -*- mode: python ; coding: utf-8 -*-

import os
import site
from PyInstaller.utils.hooks import collect_dynamic_libs, collect_data_files

a = Analysis(
    ['power_monitor.py'],
    pathex=['.'],
    binaries=[],
    datas=[('config.json', '.')],
    hiddenimports=[
        'win32api',
        'win32con',
        'win32event',
        'win32service',
        'win32serviceutil',
        'win32com',
        'win32com.client',
        'win32gui',
        'win32gui_struct',
        'win32ts',
        'pywintypes',
        'pythoncom',
        'win32process'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False
)

# Collect all pywin32 dependencies
binaries = (
    collect_dynamic_libs('win32gui') +
    collect_dynamic_libs('win32ts') +
    collect_dynamic_libs('win32con') +
    collect_dynamic_libs('win32api') +
    collect_dynamic_libs('win32event') +
    collect_dynamic_libs('pywintypes') +
    collect_dynamic_libs('pythoncom') +
    collect_dynamic_libs('win32process')
)
a.binaries += binaries

datas = (
    collect_data_files('win32gui') +
    collect_data_files('win32ts') +
    collect_data_files('win32con') +
    collect_data_files('pywintypes') +
    collect_data_files('pythoncom')
)
# Explicitly include pywin32 DLLs
pywin32_dir = os.path.join(site.getsitepackages()[0], 'pywin32_system32')
if os.path.exists(pywin32_dir):
    a.datas += [
        (os.path.join(pywin32_dir, 'pywintypes312.dll'), '.'),
        (os.path.join(pywin32_dir, 'pythoncom312.dll'), '.')
    ]
else:
    print("Warning: pywin32_system32 not found locally; CI should handle it")
a.datas += datas

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='PowerMonitor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Keep for debugging runtime errors
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)