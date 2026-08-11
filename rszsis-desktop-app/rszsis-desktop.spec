# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Determine base paths dynamically relative to spec file location
spec_dir = Path(os.path.abspath(SPECPATH))
ruis_dir = (spec_dir.parent / 'Road-User-Intelligence-System').resolve()

datas = [
    (str(spec_dir / '.env'), '.'),
    (str(ruis_dir / 'safety_events.db'), 'Road-User-Intelligence-System'),
    (str(ruis_dir / 'app'), 'Road-User-Intelligence-System/app'),
    (str(ruis_dir / 'data' / 'models' / 'yolov8m_visdrone.pt'), 'Road-User-Intelligence-System/data/models'),
    (str(ruis_dir / 'data' / 'calibration'), 'Road-User-Intelligence-System/data/calibration'),
]

try:
    datas += collect_data_files('ultralytics')
except Exception as e:
    print('collect_data_files ultralytics exception:', e)

try:
    datas += collect_data_files('supervision')
except Exception as e:
    print('collect_data_files supervision exception:', e)

hiddenimports = [
    'app',
    'app.config',
    'app.database',
    'app.database.db',
    'app.database.models',
    'app.database.importer',
    'app.detection',
    'app.safety',
    'app.speed',
    'app.tracking',
    'ultralytics',
    'supervision',
    'lap',
    'shapely',
    'scipy',
    'cv2',
    'supabase',
    'sqlalchemy',
    'PIL',
    'dotenv',
]

try:
    hiddenimports += collect_submodules('app')
except Exception as e:
    print('collect_submodules app exception:', e)

a = Analysis(
    [str(spec_dir / 'main.py')],
    pathex=[str(spec_dir), str(ruis_dir)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='rszsis-desktop',
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
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='rszsis-desktop',
)
