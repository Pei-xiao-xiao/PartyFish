# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# 版本信息
VERSION = "1.1.2"

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[os.getcwd()],
    binaries=[
        # 关键 DLL 文件
        ('resources/dxgi4py.dll', '.'),
    ],
    datas=[
        # 收集 QFluentWidgets 数据文件
        *collect_data_files('qfluentwidgets'),
        # 收集 rapidocr_onnxruntime 数据文件
        *collect_data_files('rapidocr_onnxruntime'),
        # 收集 resources 文件夹
        ('resources', 'resources'),
    ],
    hiddenimports=[
        # PySide6 核心模块
        'PySide6.QtCore',
        'PySide6.QtGui', 
        'PySide6.QtWidgets',
        'PySide6.QtNetwork',
        'shiboken6',
        
        # QFluentWidgets 组件
        'qfluentwidgets',
        'qfluentwidgets.common',
        'qfluentwidgets.components',
        'qfluentwidgets.window',
        
        # OCR 和图像处理
        'rapidocr_onnxruntime',
        'onnxruntime',
        'onnxruntime.capi',
        'cv2',
        'numpy',
        
        # 输入控制
        'pynput',
        'pynput.keyboard',
        'pynput.mouse',
        
        # 屏幕截图
        'mss',
        
        # 系统监控
        'psutil',
        'wmi',
        
        # 平台特定
        'ctypes',
        'ctypes.wintypes',
        
        # 项目模块
        'src',
        'src.gui',
        'src.gui.components',
        'src.gui.settings_interface',
        'src.gui.home_interface',
        'src.gui.main_window',
        'src.gui.welcome_dialog',
        'src.workers',
        'src.vision',
        'src.config',
        'src.inputs',
        'src.pokedex',
        'src.services.record_manager',
        
        # 其他可能需要的模块
        'PIL',
        'PIL.Image',
        'json',
        'csv',
        'threading',
        'queue',
        'asyncio',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 排除不必要的模块以减少体积
        'Tkinter',
        'tkinter',
        'matplotlib',
        'scipy',
        'pandas',
        'jupyter',
        'IPython',
        'notebook',
        'setuptools',
        'pip',
        'wheel',
        'test',
        'tests',
        'pytest',
        'unittest',
        'distutils',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# 压缩 Python 字节码
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# 单文件模式配置
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='PartyFish',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    uac_admin=True,
    icon='resources/favicon.ico',
)
