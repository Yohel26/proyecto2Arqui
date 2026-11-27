#!/usr/bin/env python3
"""Tabla de E3 (escalar vs. SVE): speedup y reducción de instrucciones por VL.

Lee las corridas de results/e3/<config>/stats.txt con parse_stats.py y agrega
variante, VL, N, speedup y reducción de instrucciones respecto a la corrida
escalar con el mismo N. Nombres de carpeta: scalar_N<n> y sve_vl<bits>_N<n>.

Uso:
    python3 scripts/e3_report.py results/e3 -o results/e3/e3.csv
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from parse_stats import find_stats_files, summarize_run

CONFIG_RE = re.compile(r"^(?:(?P<scalar>scalar)|sve_vl(?P<vl>\d+))_N(?P<n>\d+)$")

COLUMNS = ["config", "variant", "vl_bits", "N", "simInsts", "numCycles", "ipc_total",
           "simSeconds", "dcache_miss_rate", "l2_miss_rate", "speedup", "inst_reduction"]


def parse_config(name: str) -> Tuple[str, int, int]:
    """'sve_vl256_N64' -> ('sve', 256, 64); 'scalar_N128' -> ('scalar', 0, 128)."""
    match = CONFIG_RE.match(name)
    if not match:
        raise ValueError(f"Nombre de corrida de E3 inválido: {name}")
    n = int(match["n"])
    if match["scalar"]:
        return "scalar", 0, n
    vl = int(match["vl"])
    if vl % 128 != 0:
        raise ValueError(f"VL debe ser múltiplo de 128 bits: {name}")
    return "sve", vl, n


def build_table(rows: Iterable[Dict[str, object]]) -> List[Dict[str, object]]:
    """Agrega speedup e inst_reduction contra la corrida escalar del mismo N."""
    enriched = []
    for r in rows:
        variant, vl, n = parse_config(str(r["config"]))
        enriched.append({**r, "variant": variant, "vl_bits": vl, "N": n})

    baselines = {r["N"]: r for r in enriched if r["variant"] == "scalar"}
    table = []
    for r in enriched:
        base = baselines.get(r["N"])
        if base is None:
            raise ValueError(f"Falta la corrida escalar con N={r['N']} para {r['config']}")
        r["speedup"] = round(base["numCycles"] / r["numCycles"], 4)
        r["inst_reduction"] = round(base["simInsts"] / r["simInsts"], 4)
        table.append({col: r[col] for col in COLUMNS})

    table.sort(key=lambda r: (r["N"], r["variant"] != "scalar", r["vl_bits"]))
    return table


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("target", type=Path, help="Carpeta con las corridas de E3")
    parser.add_argument("-o", "--output", type=Path, help="CSV de salida (por defecto stdout)")
    args = parser.parse_args()

    runs = find_stats_files(args.target)
    if not runs:
        print(f"Error: no hay stats.txt en {args.target}", file=sys.stderr)
        return 1
    table = build_table(summarize_run(name, path, block_index=0) for name, path in runs)

    out = args.output.open("w", newline="", encoding="utf-8") if args.output else sys.stdout
    try:
        writer = csv.DictWriter(out, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(table)
    finally:
        if args.output:
            out.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
