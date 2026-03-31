# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Longview Health Python engine.

Produces a --onedir bundle containing the Python interpreter, all
dependencies (Docling, MLX, pydantic, etc.), and the `longview` CLI
entry point. This bundle is embedded in the Mac app.

Build with:
    pyinstaller packaging/longview.spec --distpath dist/
"""

from pathlib import Path
from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_submodules,
    copy_metadata,
)

project_root = Path(SPECPATH).parent

# ---------------------------------------------------------------------------
# Data files: package metadata (dist-info), resource dirs, Metal shaders
# ---------------------------------------------------------------------------

_datas = []

# Package metadata required by importlib.metadata at runtime.
# Only list packages that actually call importlib.metadata on themselves
# or are looked up by other packages via entry points / version checks.
for pkg in [
    "docling",
    "docling_core",
    "docling_ibm_models",
    "docling_parse",
    "deepsearch_glm",
    "huggingface_hub",
    "transformers",
    "tokenizers",
    "pydantic",
    "pydantic_core",
]:
    try:
        _datas += copy_metadata(pkg)
    except Exception:
        pass

# Resource files: PDF parsing resources, model configs, Metal shaders.
for pkg in ["docling", "docling_core", "docling_parse", "deepsearch_glm"]:
    try:
        _datas += collect_data_files(pkg)
    except Exception:
        pass

# MLX Metal shader library (mlx.metallib) -- required for GPU inference.
try:
    _datas += collect_data_files("mlx", include_py_files=False)
except Exception:
    pass

# ---------------------------------------------------------------------------
# Hidden imports: dynamically-imported submodules
# ---------------------------------------------------------------------------

_hidden = []

# Packages with heavy use of dynamic imports, plugins, or lazy loading.
# collect_submodules ensures PyInstaller finds everything.
for pkg in [
    "longview_health",  # Our own code (auto-tracks new modules)
    "docling",
    "docling_core",
    "docling_parse",
    "mlx",
    "mlx_lm",
    "transformers",
    "huggingface_hub",
    "pydantic",
    "pydantic_core",
]:
    try:
        _hidden += collect_submodules(pkg)
    except Exception:
        pass

# Packages whose top-level import is sufficient (no dynamic submodules).
_hidden += [
    "tokenizers",
    "pdfplumber",
    "reportlab",
    "click",
    "httpx",
]

# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

a = Analysis(
    [str(project_root / "src" / "longview_health" / "cli" / "main.py")],
    pathex=[str(project_root / "src")],
    binaries=[],
    datas=_datas,
    hiddenimports=_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(project_root / "packaging" / "pyi_rth_multiprocessing.py")],
    excludes=[
        "pytest",
        "pytest_tmp_files",
        "_pytest",
        "test",
        "tests",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="longview",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
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
    upx=False,
    upx_exclude=[],
    name="longview-engine",
)
