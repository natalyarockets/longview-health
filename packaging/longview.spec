# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Longview Health Python engine.

Produces a --onedir bundle containing the Python interpreter, all
dependencies (Docling, MLX, pydantic, etc.), and the `longview` CLI
entry point. This bundle is embedded in the Mac app.

Build with:
    pyinstaller packaging/longview.spec --distpath dist/
"""

import sys
from pathlib import Path
from PyInstaller.utils.hooks import copy_metadata, collect_data_files

block_cipher = None

# Project root (one level up from packaging/)
project_root = Path(SPECPATH).parent

# Collect package metadata that importlib.metadata needs at runtime.
# Docling and its ecosystem use metadata for version checks and entry points.
_metadata_packages = [
    "docling",
    "docling_core",
    "docling_ibm_models",
    "docling_parse",
    "deepsearch_glm",
    "pydantic",
    "pydantic_core",
    "huggingface_hub",
    "transformers",
    "tokenizers",
    "mlx",
    "mlx_lm",
    "pdfplumber",
    "reportlab",
    "httpx",
]

_datas = []
for pkg in _metadata_packages:
    try:
        _datas += copy_metadata(pkg)
    except Exception:
        pass  # Skip packages not installed

# Collect data files (model configs, pdf resources, etc.)
for _pkg in ["docling", "docling_core", "docling_parse", "deepsearch_glm"]:
    try:
        _datas += collect_data_files(_pkg)
    except Exception:
        pass

a = Analysis(
    [str(project_root / "src" / "longview_health" / "cli" / "main.py")],
    pathex=[str(project_root / "src")],
    binaries=[],
    datas=_datas,
    hiddenimports=[
        # Docling dynamic imports
        "docling.document_converter",
        "docling.datamodel.base_models",
        "docling.datamodel.document",
        "docling_core.types.doc",
        # MLX C extensions and submodules
        "mlx",
        "mlx.core",
        "mlx.nn",
        "mlx_lm",
        "mlx_lm.utils",
        "mlx_lm.models",
        "mlx_lm.models.qwen2",
        # Transformers (used by mlx-lm for tokenizer)
        "transformers",
        "tokenizers",
        # huggingface_hub
        "huggingface_hub",
        "huggingface_hub.utils",
        # Pydantic
        "pydantic",
        "pydantic.deprecated",
        "pydantic_core",
        # Other
        "pdfplumber",
        "reportlab",
        "click",
        "httpx",
        # All longview_health submodules
        "longview_health",
        "longview_health.cli",
        "longview_health.cli.main",
        "longview_health.cli.vault",
        "longview_health.cli.rescan",
        "longview_health.cli.search",
        "longview_health.cli.results",
        "longview_health.cli.trend",
        "longview_health.cli.export",
        "longview_health.cli.review",
        "longview_health.cli.model",
        "longview_health.cli.settings",
        "longview_health.core",
        "longview_health.core.config",
        "longview_health.core.paths",
        "longview_health.core.errors",
        "longview_health.core.protocols",
        "longview_health.domain",
        "longview_health.domain.models",
        "longview_health.domain.enums",
        "longview_health.domain.identifiers",
        "longview_health.extract",
        "longview_health.extract.llm_extractor",
        "longview_health.extract.mlx_extractor",
        "longview_health.extract.extraction_chain",
        "longview_health.extract.docling_parser",
        "longview_health.extract.parser_chain",
        "longview_health.extract.pdf_parser",
        "longview_health.extract.table_parser",
        "longview_health.extract.region_grouper",
        "longview_health.extract.result_merger",
        "longview_health.extract.section_router",
        "longview_health.ingest",
        "longview_health.ingest.enumerator",
        "longview_health.ingest.orchestrator",
        "longview_health.storage",
        "longview_health.storage.database",
        "longview_health.storage.document_store",
        "longview_health.storage.results_store",
        "longview_health.storage.review_store",
        "longview_health.storage.search_store",
        "longview_health.storage.vault_store",
        "longview_health.storage.migrations",
        "longview_health.search",
        "longview_health.search.indexer",
        "longview_health.trends",
        "longview_health.trends.engine",
        "longview_health.trends.export",
        "longview_health.validate",
        "longview_health.validate.engine",
        "longview_health.validate.rules",
        "longview_health.validate.confidence",
        "longview_health.review",
        "longview_health.review.queue",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
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

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

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
