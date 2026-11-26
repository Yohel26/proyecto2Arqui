#!/usr/bin/env python3
"""Extractor de métricas de gem5 (stats.txt) hacia formato CSV.

Por defecto extrae únicamente el primer bloque de estadísticas (índice 0),
que corresponde a la Región de Interés (ROI) cuando el programa en C usa:
    m5_reset_stats(0, 0);
    // Código medido (ROI)
    m5_dump_stats(0, 0);

Uso:
    python3 scripts/parse_stats.py results/e2 > results/e2/e2.csv
    python3 scripts/parse_stats.py results/e1 -o results/e1/e1.csv
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

# Marcadores con los que gem5 delimita cada volcado de estadísticas en stats.txt
BEGIN_MARKER = "---------- Begin Simulation Statistics ----------"
END_MARKER = "---------- End Simulation Statistics   ----------"

# Expresión regular para leer líneas tipo: "nombre.de.metrica    12345.67   # comentario"
# Captura: grupo 1 = nombre de la métrica, grupo 2 = valor numérico (entero, decimal, científico, nan/inf)
STAT_LINE_RE = re.compile(
    r"^([A-Za-z0-9_.:-]+)\s+([+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?|nan|inf|-inf)\b"
)

# Expresión regular para detectar métricas por núcleo:
# - En 1 núcleo gem5 escribe: system.cpu.numCycles
# - En N núcleos gem5 escribe: system.cpu0.numCycles, system.cpu1.numCycles, etc.
CPU_STAT_RE = re.compile(r"^system\.cpu(\d*)\.(.+)$")


# ---------------------------------------------------------------------------
# Bloque 1: Lectura y separación de bloques de estadísticas (ROI vs resto)
# ---------------------------------------------------------------------------
def extract_block(stats_path: Path, block_index: int = 0) -> tuple[List[str], int]:
    """Lee stats.txt, separa todos los bloques y devuelve el bloque pedido."""
    blocks: List[List[str]] = []
    current: Optional[List[str]] = None

    with stats_path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            stripped = line.strip()
            if stripped == BEGIN_MARKER:
                # Inicia un nuevo bloque de estadísticas
                current = []
            elif stripped == END_MARKER:
                # Termina el bloque actual y se guarda en la lista
                if current is not None:
                    blocks.append(current)
                    current = None
            elif current is not None:
                # Línea perteneciente al bloque activo
                current.append(line)

    # Por seguridad, si el último bloque no tuviera marcador de cierre, igual se guarda
    if current is not None:
        blocks.append(current)

    if not blocks:
        return [], 0
    if block_index >= len(blocks):
        raise IndexError(
            f"{stats_path}: se pidió el bloque {block_index}, pero solo hay {len(blocks)} bloque(s)."
        )
    return blocks[block_index], len(blocks)


# ---------------------------------------------------------------------------
# Bloque 2: Conversión de líneas de texto a diccionario {métrica: valor}
# ---------------------------------------------------------------------------
def parse_block_metrics(lines: List[str]) -> Dict[str, float]:
    """Convierte las líneas de un bloque en un diccionario {nombre: float}."""
    metrics: Dict[str, float] = {}
    for line in lines:
        s = line.strip()
        # Ignora líneas vacías o comentarios
        if not s or s.startswith("#"):
            continue
        match = STAT_LINE_RE.match(s)
        if not match:
            continue
        key, raw_val = match.group(1), match.group(2)
        try:
            metrics[key] = float(raw_val)
        except ValueError:
            continue
    return metrics


def collect_cpu_values(metrics: Dict[str, float], suffix: str) -> List[float]:
    """Recoge una métrica de todos los núcleos (sirve tanto para 1 como para N núcleos)."""
    values: List[float] = []
    for key, val in metrics.items():
        m = CPU_STAT_RE.match(key)
        # m.group(2) es el nombre después de "system.cpu." o "system.cpuN."
        if m and m.group(2) == suffix:
            values.append(val)
    return values


# ---------------------------------------------------------------------------
# Bloque 3: Cálculo y resumen de las métricas clave para los experimentos E1–E6
# ---------------------------------------------------------------------------
def summarize_run(config_name: str, stats_path: Path, block_index: int) -> Dict[str, object]:
    """Extrae las métricas relevantes de una corrida y devuelve una fila para el CSV."""
    lines, num_blocks = extract_block(stats_path, block_index=block_index)
    m = parse_block_metrics(lines)

    # Métricas por núcleo (listas de tamaño 1 en mononúcleo o N en multinúcleo)
    cycles_list = collect_cpu_values(m, "numCycles")
    ipc_list = collect_cpu_values(m, "ipc")
    cpi_list = collect_cpu_values(m, "cpi")

    # Caché de datos L1D (sumada entre todos los núcleos)
    dcache_hits = sum(collect_cpu_values(m, "dcache.overallHits::total"))
    dcache_misses = sum(collect_cpu_values(m, "dcache.overallMisses::total"))
    dcache_accesses = dcache_hits + dcache_misses
    dcache_miss_rate = (dcache_misses / dcache_accesses) if dcache_accesses > 0 else 0.0

    # Caché L2 compartida (si se usa caché clásica con --l2cache)
    l2_hits = m.get("system.l2.overallHits::total", 0.0)
    l2_misses = m.get("system.l2.overallMisses::total", 0.0)
    l2_accesses = l2_hits + l2_misses
    l2_miss_rate = (
        m["system.l2.overallMissRate::total"]
        if "system.l2.overallMissRate::total" in m
        else ((l2_misses / l2_accesses) if l2_accesses > 0 else 0.0)
    )

    # Predictor de saltos (para analizar pérdidas de ILP en E2)
    bp_pred = sum(collect_cpu_values(m, "branchPred.condPredicted"))
    bp_inc = sum(collect_cpu_values(m, "branchPred.condIncorrect"))
    bp_mispred_rate = (bp_inc / bp_pred) if bp_pred > 0 else 0.0

    # En multinúcleo, los ciclos efectivos de la región paralela los marca el núcleo más lento (max)
    sim_insts = m.get("simInsts", 0.0)
    num_cycles = max(cycles_list) if cycles_list else 0.0
    ipc_agg = (sim_insts / num_cycles) if num_cycles > 0 else 0.0

    return {
        "config": config_name,
        "stat_blocks": num_blocks,  # Debe ser >= 2 cuando m5_reset_stats + m5_dump_stats están activos
        "num_cpus": len(cycles_list) if cycles_list else 1,
        "simSeconds": m.get("simSeconds", 0.0),
        "simTicks": int(m.get("simTicks", 0.0)),
        "simInsts": int(sim_insts),
        "numCycles": int(num_cycles),
        "ipc_avg": round(sum(ipc_list) / len(ipc_list), 6) if ipc_list else 0.0,
        "ipc_total": round(ipc_agg, 6),
        "cpi_avg": round(sum(cpi_list) / len(cpi_list), 6) if cpi_list else 0.0,
        "dcache_hits": int(dcache_hits),
        "dcache_misses": int(dcache_misses),
        "dcache_miss_rate": round(dcache_miss_rate, 6),
        "l2_hits": int(l2_hits),
        "l2_misses": int(l2_misses),
        "l2_miss_rate": round(l2_miss_rate, 6),
        # Eventos de saturación de colas y ROB (clave para E2)
        "iq_full_events": int(sum(collect_cpu_values(m, "iew.iqFullEvents"))),
        "lsq_full_events": int(sum(collect_cpu_values(m, "iew.lsqFullEvents"))),
        "rename_iq_full": int(sum(collect_cpu_values(m, "rename.IQFullEvents"))),
        "rename_rob_full": int(sum(collect_cpu_values(m, "rename.ROBFullEvents"))),
        "rename_blocked_cycles": int(sum(collect_cpu_values(m, "rename.status::Blocked"))),
        "commit_squashed_insts": int(sum(collect_cpu_values(m, "commit.commitSquashedInsts"))),
        "bp_cond_predicted": int(bp_pred),
        "bp_cond_incorrect": int(bp_inc),
        "bp_mispred_rate": round(bp_mispred_rate, 6),
        # Ciclos de Ruby (usado en E5 cuando se simula con --ruby)
        "ruby_cycles": int(m.get("system.ruby.cycles", 0.0)),
    }


# ---------------------------------------------------------------------------
# Bloque 4: Búsqueda de archivos stats.txt y generación del CSV final
# ---------------------------------------------------------------------------
def find_stats_files(target: Path) -> List[tuple[str, Path]]:
    """Busca stats.txt directamente en target o en todas sus subcarpetas."""
    if target.is_file():
        return [(target.parent.name, target)]

    direct = target / "stats.txt"
    if direct.is_file():
        return [(target.name, direct)]

    runs: List[tuple[str, Path]] = []
    # rglob("stats.txt") recorre todas las subcarpetas de configuraciones ordenadas alfabéticamente
    for stats_file in sorted(target.rglob("stats.txt")):
        rel_parent = stats_file.parent.relative_to(target)
        runs.append((str(rel_parent).replace("\\", "/"), stats_file))
    return runs


def main() -> int:
    # Definición de argumentos de línea de comandos
    parser = argparse.ArgumentParser(
        description="Extrae métricas de la ROI desde stats.txt de gem5 hacia CSV."
    )
    parser.add_argument(
        "target",
        type=Path,
        help="Carpeta del experimento (ej. results/e2) o archivo stats.txt individual.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Ruta del CSV de salida (si se omite, imprime en pantalla).",
    )
    parser.add_argument(
        "--block-index",
        type=int,
        default=0,
        help="Índice del bloque a extraer (por defecto 0 = ROI).",
    )
    args = parser.parse_args()

    if not args.target.exists():
        print(f"Error: no existe la ruta: {args.target}", file=sys.stderr)
        return 1

    runs = find_stats_files(args.target)
    if not runs:
        print(f"Error: no se encontraron archivos stats.txt en {args.target}", file=sys.stderr)
        return 1

    # Procesa cada corrida y arma la lista de filas
    rows = [
        summarize_run(name, path, block_index=args.block_index)
        for name, path in runs
    ]

    # Escribe el CSV en archivo (-o) o en salida estándar (stdout)
    fieldnames = list(rows[0].keys())
    out_fh = args.output.open("w", newline="", encoding="utf-8") if args.output else sys.stdout
    try:
        writer = csv.DictWriter(out_fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    finally:
        if args.output:
            out_fh.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
