# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['MAIN\\main.py'],
    pathex=[],
    binaries=[],
    datas=[('UTILS','UTILS'),('FUNCTION','FUNCTION'),('DATA','DATA'),('BRAIN','BRAIN'),('AUTOMATION','AUTOMATION')],
    hiddenimports=[
        'speech_recognition',
        'mtranslate',
        'selenium',
        'selenium.webdriver.chrome',
        'selenium.webdriver.chrome.service',
        'selenium.webdriver.common.by',
        'selenium.webdriver.common.keys',
        'selenium.webdriver.support.ui',
        'selenium.webdriver.support.expected_conditions',
        'pyautogui'
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
    a.binaries,
    a.datas,
    [],
    name='main',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
