"""Build a portable Windows folder, ZIP, and per-user Inno Setup installer."""
from __future__ import annotations

import argparse
import ast
import hashlib
import importlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
from importlib.metadata import distribution, version
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
WORK = ROOT / "build" / "windows-release"
APP_NAME = "CanyonGlow"
APP_EXE = f"{APP_NAME}.exe"
BUNDLE = DIST / APP_NAME
ICON = ROOT / "picture" / f"{APP_NAME}.ico"
PACKAGES = ("pyinstaller", "pyserial", "pyinstaller-hooks-contrib", "altgraph", "packaging", "pefile", "pywin32-ctypes", "setuptools")


def workspace_path(path: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(ROOT) or resolved == ROOT:
        raise RuntimeError(f"Unsafe build output outside the project: {resolved}")
    return path


def app_version() -> tuple[str, str]:
    tree = ast.parse((ROOT / "canyonglow.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "APP_VERSION" for t in node.targets):
            tag = ast.literal_eval(node.value)
            match = re.fullmatch(r"v(\d+)(?:\.(\d+))?(?:\.(\d+))?", tag)
            if match:
                return tag, ".".join(part or "0" for part in match.groups())
    raise RuntimeError("APP_VERSION must have the form v1.0 or v1.0.1")


def find_iscc(explicit: str | None) -> Path | None:
    if explicit or os.environ.get("NUC_INNO_ISCC"):
        candidate = Path(explicit or os.environ["NUC_INNO_ISCC"])
        if not candidate.is_file():
            raise RuntimeError(f"Inno Setup compiler not found: {candidate}")
        return candidate
    candidates = []
    if shutil.which("ISCC.exe"):
        candidates.append(Path(shutil.which("ISCC.exe")))
    for base in (os.environ.get("ProgramFiles", ""), os.environ.get("ProgramFiles(x86)", ""), str(Path.home() / "AppData" / "Local" / "Programs")):
        if base:
            candidates.extend(Path(base) / name / "ISCC.exe" for name in ("Inno Setup 7", "Inno Setup 6"))
    candidates.append(ROOT / "build" / "tools" / "InnoSetup" / "ISCC.exe")
    return next((path for path in candidates if path.is_file()), None)


def run(command: list[str], **kwargs) -> None:
    subprocess.run(command, cwd=ROOT, check=True, **kwargs)


def write_version_info(release: str) -> Path:
    from PyInstaller.utils.win32.versioninfo import FixedFileInfo, StringFileInfo, StringStruct, StringTable, VarFileInfo, VarStruct, VSVersionInfo
    info = VSVersionInfo(
        ffi=FixedFileInfo(filevers=tuple(map(int, release.split("."))) + (0,), prodvers=tuple(map(int, release.split("."))) + (0,), mask=0x3F, flags=0, OS=0x40004, fileType=1, subtype=0, date=(0, 0)),
        kids=[StringFileInfo([StringTable("040904B0", [
            StringStruct("FileDescription", f"{APP_NAME} - RGB Control for NUC 11 & 12 Extreme"),
            StringStruct("FileVersion", release),
            StringStruct("InternalName", APP_NAME),
            StringStruct("OriginalFilename", APP_EXE),
            StringStruct("ProductName", APP_NAME),
            StringStruct("ProductVersion", release),
        ])]), VarFileInfo([VarStruct("Translation", [1033, 1200])])],
    )
    path = workspace_path(WORK / "version_info.txt")
    path.write_text(str(info), encoding="utf-8")
    return path


def copy_release_files() -> None:
    for name in ("README_DE.md", "README_EN.md", "example_default_green_profile.json", "THIRD_PARTY_NOTICES.txt"):
        shutil.copy2(ROOT / name, workspace_path(BUNDLE / name))
    project_license = ROOT / "LICENSE"
    if project_license.is_file():
        shutil.copy2(project_license, workspace_path(BUNDLE / "LICENSE"))
    drivers = workspace_path(BUNDLE / "drivers")
    drivers.mkdir(exist_ok=True)
    for name in ("README_DE.txt", "README_EN.txt"):
        shutil.copy2(ROOT / "drivers" / name, workspace_path(drivers / name))
    licenses = workspace_path(BUNDLE / "licenses")
    licenses.mkdir(exist_ok=True)
    for source in (ROOT / "licenses").glob("*"):
        if source.is_file():
            shutil.copy2(source, workspace_path(licenses / source.name))
    python_root = Path(sys.base_prefix)
    for source, name in (
        (python_root / "LICENSE.txt", "Python-LICENSE.txt"),
        (python_root / "tcl" / "tcl8.6" / "license.terms", "Tcl-LICENSE.txt"),
        (python_root / "tcl" / "tk8.6" / "license.terms", "Tk-LICENSE.txt"),
    ):
        if source.is_file():
            shutil.copy2(source, workspace_path(licenses / name))
    for package in ("pyserial", "pyinstaller"):
        package_dist = distribution(package)
        for item in package_dist.files or []:
            if "license" in item.name.lower() or "copying" in item.name.lower():
                source = Path(package_dist.locate_file(item))
                if source.is_file():
                    shutil.copy2(source, workspace_path(licenses / f"{package}-{item.name}"))
    notices = f"{APP_NAME} {app_version()[0]}\n\nBundled runtime components:\nPython, Tcl/Tk, pyserial, PyInstaller runtime.\n\n" + "\n".join(f"{name}=={version(name)}" for name in PACKAGES)
    workspace_path(BUNDLE / "BUILD_INFO.txt").write_text(notices + "\n", encoding="utf-8")


def portable_zip(tag: str) -> Path:
    archive = workspace_path(DIST / f"{APP_NAME}-{tag}-Portable-x64.zip")
    with ZipFile(archive, "w", compression=ZIP_DEFLATED) as output:
        for path in sorted(BUNDLE.rglob("*")):
            if path.is_file():
                workspace_path(path)
                output.write(path, path.relative_to(DIST))
    return archive


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-only", action="store_true", help="Build the folder and ZIP without Inno Setup")
    parser.add_argument("--skip-smoke-test", action="store_true", help="Skip the hidden, hardware-free GUI check")
    parser.add_argument("--iscc", help="Full path to Inno Setup's ISCC.exe")
    args = parser.parse_args()
    if os.name != "nt" or struct.calcsize("P") != 8:
        raise RuntimeError("Build with a 64-bit Python installation on Windows")
    for module in ("tkinter", "serial", "PyInstaller"):
        try:
            importlib.import_module(module)
        except ImportError as exc:
            raise RuntimeError("Build dependency missing. Run: python -m pip install -r requirements-build.txt") from exc
    tag, release = app_version()
    print(f"Building {APP_NAME} {tag} with Python {sys.version.split()[0]} and PyInstaller {version('pyinstaller')}", flush=True)
    for path in (DIST, WORK, BUNDLE, WORK / "pyinstaller-cache", WORK / "spec"):
        workspace_path(path).mkdir(parents=True, exist_ok=True)
    resource = write_version_info(release)
    if not ICON.is_file():
        raise RuntimeError(f"Application icon missing: {ICON}")
    environment = dict(os.environ, PYINSTALLER_CONFIG_DIR=str(WORK / "pyinstaller-cache"))
    run([sys.executable, "-B", "-m", "PyInstaller", "--clean", "--noconfirm", "--onedir", "--noupx", "--windowed", "--name", APP_NAME, "--distpath", str(DIST), "--workpath", str(WORK / "pyinstaller"), "--specpath", str(WORK / "spec"), "--version-file", str(resource), "--icon", str(ICON), "--add-data", f"{ICON};picture", str(ROOT / "windows_launcher.py")], env=environment)
    copy_release_files()
    report = None
    if not args.skip_smoke_test:
        report_path = workspace_path(WORK / "smoke-test.json")
        if report_path.exists():
            report_path.unlink()
        run([str(BUNDLE / APP_EXE), "--self-test-report", str(report_path)], timeout=45, creationflags=subprocess.CREATE_NO_WINDOW)
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if not report.get("ok") or not report.get("frozen") or report.get("app_version") != tag:
            raise RuntimeError(f"Packaged GUI check failed: {report}")
        print("Packaged GUI check passed without hardware access.", flush=True)
    archive = portable_zip(tag)
    artifacts = [BUNDLE / APP_EXE, archive]
    compiler = None if args.bundle_only else find_iscc(args.iscc)
    if compiler:
        run([str(compiler), f"/DAppVersion={release}", f"/DReleaseTag={tag}", f"/DBundleDir={BUNDLE}", f"/DReleaseDir={DIST}", str(ROOT / "installer.iss")])
        setup = workspace_path(DIST / f"{APP_NAME}-{tag}-Setup-x64.exe")
        if not setup.is_file():
            raise RuntimeError("Inno Setup did not create the expected installer")
        artifacts.append(setup)
    hashes = {str(path.relative_to(DIST)): hashlib.sha256(path.read_bytes()).hexdigest() for path in artifacts}
    workspace_path(DIST / f"{APP_NAME}-{tag}-SHA256SUMS.txt").write_text("".join(f"{digest}  {name}\n" for name, digest in hashes.items()), encoding="utf-8")
    metadata = {"app_name": APP_NAME, "app_version": tag, "file_version": release, "python": sys.version.split()[0], "packages": {name: version(name) for name in PACKAGES}, "source_sha256": hashlib.sha256((ROOT / "canyonglow.py").read_bytes()).hexdigest(), "smoke_test": report, "sha256": hashes, "signed": False}
    workspace_path(WORK / "release-info.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    for artifact in artifacts:
        print(f"Created: {artifact}")
    if not args.bundle_only and compiler is None:
        print("Folder and ZIP are ready. Inno Setup is missing: install Inno Setup 6.3+ or use --iscc / NUC_INNO_ISCC.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
        print(f"Build failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
