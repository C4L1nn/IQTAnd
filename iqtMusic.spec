# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
from PyInstaller.utils.hooks import copy_metadata

datas = [('assets', 'assets'), ('bin', 'bin'), ('plugins', 'plugins'), ('iqticon.ico', '.')]
binaries = [('libvlc.dll', '.'), ('libvlccore.dll', '.')]
hiddenimports = [
    'PySide6.QtSvg',
    'PySide6.QtNetwork',
    'pynput.keyboard._win32',
    'pypresence',
    'paho.mqtt',
    'paho.mqtt.client',
    'paho.mqtt.publish',
    'requests',
    'vlc',
]
datas += copy_metadata('yt-dlp')
datas += copy_metadata('ytmusicapi')
tmp_ret = collect_all('yt_dlp')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('ytmusicapi')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=2,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='iqtMusic',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['iqticon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='iqtMusic',
)
