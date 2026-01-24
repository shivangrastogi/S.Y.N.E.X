# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['DESKTOP_APP\\main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('BACKEND/MAIN','MAIN'),
        (r'BACKEND/DATA/MODELS/NLU_MODELS/model-best', r'data/MODELS/NLU_MODELS/model-best'),
        ('BACKEND/CORE','CORE'),
        ('BACKEND/DATA','DATA'),
        ('DESKTOP_APP','DESKTOP_APP'),
        ('BACKEND/AUTOMATION','AUTOMATION'),
        ('BACKEND/BRAIN','BRAIN'),
        ('DESKTOP_APP/GUI/assets','assets'),
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

# -------------------------------------------------------------
# 🟢 MODIFIED EXE BLOCK FOR --onefile
# -------------------------------------------------------------
exe = EXE(
    pyz,
    a.scripts,
    # Pass binaries and data directly to EXE for onefile mode
    a.binaries, # Pass binaries
    a.datas,    # Pass bundled data (assets/files)

    exclude_binaries=False, # 🟢 CHANGE: Must be False for onefile to include DLLs

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

# -------------------------------------------------------------
# ❌ REMOVE THE COLLECT BLOCK COMPLETELY
# -------------------------------------------------------------
