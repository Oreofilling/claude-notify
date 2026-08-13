# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec：onedir 打包（启动快、误报少）。
打包命令： pyinstaller --noconfirm build/ClaudeNotify.spec
产物：dist/ClaudeNotify/ClaudeNotify.exe（整文件夹分发）
"""
from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = ["pystray._win32"]

# win11toast / winsdk 依赖大量子模块，必须 collect_all
for pkg in ("winsdk", "win11toast"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    ["../main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, a.scripts)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ClaudeNotify",
    console=False,          # 窗口程序，无控制台
    disable_windowed_traceback=False,
    icon="assets/icon_idle.ico" if __import__("os").path.exists("assets/icon_idle.ico") else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="ClaudeNotify",
)
