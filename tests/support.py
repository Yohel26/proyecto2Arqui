"""Utilidades compartidas por las pruebas: rutas del repositorio y compilación nativa."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

_BUILD_DIR = Path(tempfile.mkdtemp(prefix="gemm_native_"))


def build_native(source: str, openmp: bool = False) -> Path:
    """Compila src/<source>.c para el host con -DNATIVE y devuelve el binario."""
    binary = _BUILD_DIR / source
    if not binary.exists():
        cmd = ["gcc", "-O2", "-Wall", "-Wextra", "-Werror", "-DNATIVE"]
        if openmp:
            cmd.append("-fopenmp")
        cmd += [str(SRC / f"{source}.c"), "-o", str(binary)]
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    return binary


def run(binary: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([str(binary), *args], capture_output=True, text=True, timeout=60)
