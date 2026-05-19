# PyInstaller spec — InvestNet backend (onedir mode for fast startup)
# Build with: pyinstaller backend.spec
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = []
try:
    datas += collect_data_files('talon', include_py_files=False)
except Exception:
    pass
try:
    datas += collect_data_files('faiss', include_py_files=False)
except Exception:
    pass

hiddenimports = []
hiddenimports += collect_submodules('faiss')
try:
    hiddenimports += collect_submodules('sklearn')
except Exception:
    pass
hiddenimports += [
    'email.mime.multipart', 'email.mime.text',
    'pandas._libs.tslibs.base',
    'ddgs', 'primp',
    'uvicorn.logging', 'uvicorn.loops', 'uvicorn.loops.auto',
    'uvicorn.protocols', 'uvicorn.protocols.http', 'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets', 'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan', 'uvicorn.lifespan.on',
]

block_cipher = None

a = Analysis(
    ['app/main.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=['matplotlib', 'tkinter', 'PyQt5', 'PySide2', 'IPython', 'jupyter', 'pytest'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name='backend',
)
