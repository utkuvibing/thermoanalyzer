# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata


# PyInstaller may execute spec files without defining __file__.
# SPECPATH is provided by PyInstaller and points to the spec directory.
_spec_file = globals().get("__file__")
if _spec_file:
    SPEC_ROOT = Path(_spec_file).resolve().parent
else:
    SPEC_ROOT = Path(globals().get("SPECPATH", Path.cwd())).resolve()
REPO_ROOT = SPEC_ROOT.parents[1]


def tree_as_datas(relative_path: str):
    source_root = REPO_ROOT / relative_path
    if source_root.is_file():
        destination = str(Path(relative_path).parent)
        if destination == ".":
            destination = "."
        return [(str(source_root), destination)]
    items = []
    for item in source_root.rglob("*"):
        if item.is_file():
            destination = str(Path(relative_path) / item.relative_to(source_root).parent)
            items.append((str(item), destination))
    return items


datas = []
datas += tree_as_datas("app.py")
datas += tree_as_datas("core")
datas += tree_as_datas("ui")
datas += tree_as_datas("utils")
datas += tree_as_datas("sample_data")
datas += tree_as_datas(".streamlit")
datas += tree_as_datas("README.md")
datas += tree_as_datas("PROFESOR_KURULUM_VE_KULLANIM_KILAVUZU.md")
datas += tree_as_datas("PROFESSOR_SETUP_AND_USAGE_GUIDE.md")
datas += tree_as_datas("PROFESSOR_BETA_GUIDE.md")

datas += collect_data_files("streamlit")
datas += collect_data_files("plotly")
datas += collect_data_files("kaleido")
datas += collect_data_files("reportlab")
datas += copy_metadata("streamlit")
datas += copy_metadata("plotly")
datas += copy_metadata("pandas")
datas += copy_metadata("numpy")
datas += copy_metadata("scipy")
datas += copy_metadata("pybaselines")
datas += copy_metadata("lmfit")
datas += copy_metadata("openpyxl")
datas += copy_metadata("python-docx")
datas += copy_metadata("reportlab")

hiddenimports = []
hiddenimports += collect_submodules("streamlit")
hiddenimports += collect_submodules("plotly")
hiddenimports += collect_submodules("kaleido")
hiddenimports += collect_submodules("reportlab")

block_cipher = None


a = Analysis(
    [str(SPEC_ROOT / "launcher.py")],
    pathex=[str(REPO_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "tests"],
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
    name="ThermoAnalyzerLauncher",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="ThermoAnalyzerLauncher",
)
