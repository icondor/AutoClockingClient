# -*- mode: python ; coding: utf-8 -*-

block_cipher = None
from PyInstaller.utils.hooks import collect_dynamic_libs, collect_submodules, collect_data_files

a = Analysis(
    ['power_monitor.py'],
    pathex=['Client/Windows'],
    binaries=(
        collect_dynamic_libs('win32ts') +
        collect_dynamic_libs('win32gui') +
        collect_dynamic_libs('win32con') +
        collect_dynamic_libs('win32api') +
        collect_dynamic_libs('win32event')
    ),
    datas=collect_data_files('win32gui'),
    hiddenimports=[
        'win32api',
        'win32con',
        'win32event',
        'win32gui',
        'win32ts',
        'win32com.client',
        'win32gui.PyCWnd',
        'win32gui.PyCDialog',
        'win32con.WM_POWERBROADCAST',
        'win32con.PBT_APMRESUMEAUTOMATIC',
        'win32con.WM_WTSSESSION_CHANGE',
        'win32con.WTS_SESSION_UNLOCK',
        'win32con.WM_DESTROY',
        'win32con.ERROR_ALREADY_EXISTS',
        'subprocess'
    ] + collect_submodules('win32gui') + collect_submodules('win32con') + collect_submodules('win32api'),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='power_monitor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch='x86_64',
    codesign_identity=None,
    entitlements_file=None,
    version='file_version_info.txt'
)