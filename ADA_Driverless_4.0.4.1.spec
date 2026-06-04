# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['ADA_Nova.py'],
    pathex=[],
    binaries=[],
    datas=[('ada_nova.qss', '.'), ('credentials.json', '.'), ('csv.png', '.'), ('pdf.png', '.'), ('AcuerdoMetas.html', '.'), ('manualADA4.html', '.'), ('icons', 'icons')],
    hiddenimports=['gspread', 'oauth2client'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
splash = Splash(
    'splash.png',
    binaries=a.binaries,
    datas=a.datas,
    text_pos=None,
    text_size=12,
    minify_script=True,
    always_on_top=True,
)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    splash,
    splash.binaries,
    [],
    name='ADA_Driverless_4.0.4.1',
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
    icon=['iconBDVicTor_D.ico'],
)
