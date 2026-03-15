# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

# Collect dynamic imports
hiddenimports = []
hiddenimports += collect_submodules("xhtml2pdf")
hiddenimports += collect_submodules("reportlab.graphics.barcode")
hiddenimports += [
    "reportlab.graphics.barcode.code128",
]

a = Analysis(
    ["app.py"],
    pathex=["."],
    binaries=[],
    datas=[
        ("templates", "templates"),
        ("static", "static"),
        ("assets", "assets"),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Quote Tool",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)