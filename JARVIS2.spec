# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['PC SOFTWARE\\GUI_MAKING\\NEW_UI\\main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('JARVIS_BACKEND/DATA', 'DATA'),
        ('JARVIS_BACKEND/FUNCTION', 'FUNCTION'),
        ('PC SOFTWARE/GUI_MAKING','GUI_MAKING'),
        ('JARVIS_BACKEND/MAIN','MAIN'),
        ('JARVIS_BACKEND/BRAIN','BRAIN'),
        ('JARVIS_BACKEND','JARVIS_BACKEND'),
        ('PC SOFTWARE/GUI_MAKING/NEW_UI/assets','assets')
    ],
    hiddenimports=[
        'firebase_admin',
        'firebase_admin.firestore',
        'resource_rc',
        'dotenv',
        'pyttsx3',
        'speech_recognition',
        'mtranslate',
        'spacy',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='JARVIS',
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
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='JARVIS',
)
