# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['power_monitor.py'],
    pathex=[],
    binaries=[],
    datas=[('config.json', '.')],
    hiddenimports=[
        'win32api',
        'win32con',
        'win32event',
        'win32service',
        'win32serviceutil',
        'win32com.client',
        'win32gui',
        'win32gui_struct',
        'win32ts',
        'win32ts.constants',
        'win32con.constants',
        'win32.win32gui',
        'win32.win32ts',
        'win32.win32con',
        'win32.win32api',
        'win32.win32event',
        'win32.win32service',
        'win32.win32serviceutil',
        'win32.win32com.client'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

# Collect necessary DLLs and binaries
from PyInstaller.utils.hooks import collect_dynamic_libs, collect_data_files
binaries = collect_dynamic_libs('win32gui')
binaries += collect_dynamic_libs('win32ts')
binaries += collect_dynamic_libs('win32con')
binaries += collect_dynamic_libs('win32api')
binaries += collect_dynamic_libs('win32event')
a.binaries += binaries

# Collect data files from win32 modules
datas = collect_data_files('win32gui')
datas += collect_data_files('win32ts')
datas += collect_data_files('win32con')
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
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)