#!/usr/bin/env python3
"""Tabla final y resumen de E6 (exploración bajo presupuesto).

Une las corridas results/e6/<diseño>_N<n>/stats.txt con el plan configs/e6.csv
y calcula tiempo de la ROI, GFLOP/s, rendimiento/costo y speedup. El resumen
en Markdown indica el mejor diseño por tiempo y por rendimiento/costo, el
mejor con presupuesto 16 y la diferencia MESI vs. MOESI.

Uso:
    python3 scripts/e6_report.py results/e6 --plan configs/e6.csv \
        -o results/e6/e6.csv --summary results/e6/e6_summary.md
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from e6_plan import Design, load_plan
from parse_stats import find_stats_files, summarize_run

MAIN_N = 128
SENSITIVITY_BUDGET = 16
TICKS_PER_US = 1_000_000  # gem5 usa 1 tick = 1 ps
RUN_RE = re.compile(r"^(?P<design>.+)_N(?P<n>\d+)$")

COLUMNS = ["design", "cores", "width", "vl_bits", "protocol", "cost", "N", "time_us",
           "gflops", "gflops_per_cost", "speedup", "simInsts"]


def parse_run_name(name: str) -> Tuple[str, int]:
    match = RUN_RE.match(name)
    if not match:
        raise ValueError(f"Nombre de corrida de E6 inválido: {name}")
    return match["design"], int(match["n"])


def build_table(designs: Iterable[Design], rows: Iterable[Dict[str, object]]) -> List[Dict[str, object]]:
    plan = {d.name: d for d in designs}
    table = []
    for r in rows:
        name, n = parse_run_name(str(r["config"]))
        design = plan.get(name)
        if design is None:
            raise ValueError(f"La corrida {r['config']} no está en el plan")
        time_us = int(r["simTicks"]) / TICKS_PER_US
        gflops = 2 * n**3 / (time_us * 1e-6) / 1e9
        table.append({
            "design": name, "cores": design.cores, "width": design.width,
            "vl_bits": design.vl_bits, "protocol": design.protocol, "cost": design.cost,
            "N": n, "time_us": round(time_us, 3), "gflops": round(gflops, 6),
            "gflops_per_cost": round(gflops / design.cost, 6),
            "simInsts": r["simInsts"],
        })

    slowest = {}
    for r in table:
        slowest[r["N"]] = max(slowest.get(r["N"], 0.0), r["time_us"])
    for r in table:
        r["speedup"] = round(slowest[r["N"]] / r["time_us"], 4)

    table.sort(key=lambda r: (r["N"], r["time_us"]))
    return [{col: r[col] for col in COLUMNS} for r in table]


def best(table: List[Dict[str, object]], criterion: str, n: int = MAIN_N,
         budget: Optional[float] = None) -> Optional[Dict[str, object]]:
    """criterion: 'time' (menor tiempo) o 'perf_cost' (mayor GFLOP/s por unidad de costo).
    Los empates se resuelven a favor del menor costo."""
    candidates = [r for r in table if r["N"] == n and (budget is None or r["cost"] <= budget)]
    if not candidates:
        return None
    if criterion == "time":
        return min(candidates, key=lambda r: (r["time_us"], r["cost"]))
    if criterion == "perf_cost":
        return min(candidates, key=lambda r: (-round(r["gflops_per_cost"], 6), r["cost"]))
    raise ValueError(f"Criterio desconocido: {criterion}")


def protocol_pairs(table: List[Dict[str, object]], n: int = MAIN_N):
    """Pares (mesi, moesi, % de tiempo extra de MOESI) del mismo diseño."""
    key = lambda r: (r["cores"], r["width"], r["vl_bits"])  # noqa: E731
    by_protocol = {(key(r), r["protocol"]): r for r in table if r["N"] == n}
    pairs = []
    for (k, protocol), mesi in sorted(by_protocol.items()):
        moesi = by_protocol.get((k, "moesi"))
        if protocol == "mesi" and moesi:
            pairs.append((mesi, moesi, 100 * (moesi["time_us"] / mesi["time_us"] - 1)))
    return pairs


def _describe(r: Optional[Dict[str, object]]) -> str:
    if r is None:
        return "ninguno"
    return (f"`{r['design']}` (costo {r['cost']:g}, {r['time_us']:.1f} µs, "
            f"{r['gflops']:.3f} GFLOP/s, {r['gflops_per_cost']:.4f} GFLOP/s por unidad)")


def summary_markdown(table: List[Dict[str, object]]) -> str:
    sizes = {r["N"] for r in table}
    n = MAIN_N if MAIN_N in sizes or not sizes else max(sizes)
    lines = [f"# Resumen E6 (N = {n})", "",
             f"- Mejor por tiempo: {_describe(best(table, 'time', n=n))}",
             f"- Mejor por rendimiento/costo: {_describe(best(table, 'perf_cost', n=n))}",
             f"- Mejor por tiempo con presupuesto {SENSITIVITY_BUDGET}: "
             f"{_describe(best(table, 'time', n=n, budget=SENSITIVITY_BUDGET))}", ""]
    pairs = protocol_pairs(table, n=n)
    if pairs:
        lines.append("## MESI vs. MOESI")
        lines += [f"- {m['cores']} núcleos, ancho {m['width']}, VL {m['vl_bits']}: "
                  f"MOESI {d:+.2f} % de tiempo respecto a MESI" for m, _, d in pairs]
        lines.append("")
    other_sizes = sorted(sizes - {n})
    for n in other_sizes:
        lines.append(f"## Sensibilidad N = {n}")
        lines += [f"- `{r['design']}`: {r['time_us']:.1f} µs, {r['gflops']:.3f} GFLOP/s"
                  for r in table if r["N"] == n]
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("target", type=Path)
    parser.add_argument("--plan", type=Path, default=Path("configs/e6.csv"))
    parser.add_argument("-o", "--output", type=Path)
    parser.add_argument("--summary", type=Path)
    args = parser.parse_args()

    runs = find_stats_files(args.target)
    if not runs:
        print(f"Error: no hay stats.txt en {args.target}", file=sys.stderr)
        return 1
    table = build_table(load_plan(args.plan),
                        (summarize_run(name, path, block_index=0) for name, path in runs))

    out = args.output.open("w", newline="", encoding="utf-8") if args.output else sys.stdout
    try:
        writer = csv.DictWriter(out, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(table)
    finally:
        if args.output:
            out.close()
    if args.summary:
        args.summary.write_text(summary_markdown(table), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
