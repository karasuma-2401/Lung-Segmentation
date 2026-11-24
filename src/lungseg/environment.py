"""Record actual imports and CUDA capability without requiring medical data."""

from datetime import datetime, timezone
import importlib
import hashlib
from importlib import metadata
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys


def git_state(cwd: str | Path = ".") -> dict:
    def call(*args: str) -> str:
        proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=10)
        if proc.returncode:
            raise RuntimeError(proc.stderr.strip())
        return proc.stdout.strip()

    try:
        revision = call("rev-parse", "--verify", "HEAD")
    except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
        return {"revision": None, "status": "unavailable", "reason": str(exc)}
    try:
        dirty = bool(call("status", "--porcelain"))
    except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
        return {"revision": revision, "status": "unavailable", "reason": str(exc)}
    return {"revision": revision, "status": "dirty" if dirty else "clean"}


def collect_environment() -> dict:
    packages = {}
    required = {"torch", "monai", "numpy", "PyYAML"}
    for distribution, module in (("torch", "torch"), ("monai", "monai"), ("numpy", "numpy"),
                                 ("PyYAML", "yaml"), ("pytest", "pytest"),
                                 ("SimpleITK", "SimpleITK"), ("nibabel", "nibabel"),
                                 ("matplotlib", "matplotlib"), ("pydicom", "pydicom")):
        try:
            version = metadata.version(distribution)
            importlib.import_module(module)
            packages[distribution] = {"version": version, "import": "pass"}
        except Exception as exc:
            packages[distribution] = {"import": "failed", "reason": f"{type(exc).__name__}: {exc}"}
    cuda = {"available": False, "devices": [], "status": "not_checked"}
    if packages["torch"]["import"] == "pass":
        import torch

        cuda.update(available=torch.cuda.is_available(), compiled_cuda=torch.version.cuda, status="checked")
        if cuda["available"]:
            cuda["devices"] = [{"index": i, "name": torch.cuda.get_device_name(i),
                                "total_memory_bytes": torch.cuda.get_device_properties(i).total_memory}
                               for i in range(torch.cuda.device_count())]
    disk = shutil.disk_usage(Path.cwd())
    memory = {"total_bytes": None, "status": "unavailable"}
    if sys.platform == "win32":
        import ctypes

        class MemoryStatus(ctypes.Structure):
            _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong),
                        *[(key, ctypes.c_ulonglong) for key in
                          ("total", "available", "page_total", "page_available", "virtual_total",
                           "virtual_available", "extended_available")]]

        info = MemoryStatus()
        info.length = ctypes.sizeof(info)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(info)):
            memory = {"total_bytes": info.total, "available_bytes": info.available, "status": "checked"}
    elif hasattr(os, "sysconf"):
        try:
            memory = {"total_bytes": os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES"),
                      "status": "checked"}
        except (OSError, ValueError):
            pass
    source_hash = hashlib.sha256()
    source_root = Path(__file__).parent
    for source in sorted(source_root.rglob("*.py")):
        source_hash.update(source.relative_to(source_root).as_posix().encode("utf-8") + b"\0" + source.read_bytes())
    return {"timestamp_utc": datetime.now(timezone.utc).isoformat(), "python": sys.version,
            "executable": sys.executable, "platform": platform.platform(), "packages": packages,
            "required_imports_pass": all(packages[p]["import"] == "pass" for p in required),
            "cuda": cuda, "ram": memory, "disk": {"total_bytes": disk.total, "free_bytes": disk.free},
            "git": git_state(), "package_source_sha256": source_hash.hexdigest(),
            "scope": "P0 environment; CUDA availability is not a GPU smoke pass"}
