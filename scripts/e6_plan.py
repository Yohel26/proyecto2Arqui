#!/usr/bin/env python3
"""Plan de E6: lee y valida las configuraciones de configs/e6.csv.

Cada fila: cores,width,vl_bits,protocol,rationale. El nombre de la corrida y
el costo se derivan de los parámetros (no se escriben a mano).

Uso:
    python3 scripts/e6_plan.py configs/e6.csv           # tabla legible
    python3 scripts/e6_plan.py configs/e6.csv --shell   # "nombre núcleos ancho vl protocolo"
"""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from cost import BUDGET, validate_design

PROTOCOLS = ("mesi", "moesi")
MIN_DESIGNS = 6


@dataclass(frozen=True)
class Design:
    cores: int
    width: int
    vl_bits: int
    protocol: str
    rationale: str = field(compare=False)

    @property
    def name(self) -> str:
        return f"c{self.cores}_w{self.width}_vl{self.vl_bits}_{self.protocol}"

    @property
    def cost(self) -> float:
        return validate_design(self.cores, self.width, self.vl_bits)


def _parse_row(row: dict, line: int, budget: float) -> Design:
    protocol = row["protocol"].strip().lower()
    if protocol not in PROTOCOLS:
        raise ValueError(f"Línea {line}: Protocolo desconocido '{protocol}' (use {PROTOCOLS})")
    rationale = (row.get("rationale") or "").strip()
    if not rationale:
        raise ValueError(f"Línea {line}: falta la justificación")
    design = Design(int(row["cores"]), int(row["width"]), int(row["vl_bits"]), protocol, rationale)
    try:
        validate_design(design.cores, design.width, design.vl_bits, budget)
    except ValueError as err:
        raise ValueError(f"Línea {line} ({design.name}): {err}") from None
    return design


def load_plan(path: Path, budget: float = BUDGET, min_designs: int = MIN_DESIGNS) -> List[Design]:
    with Path(path).open(newline="", encoding="utf-8") as fh:
        designs = [_parse_row(row, i, budget) for i, row in enumerate(csv.DictReader(fh), start=2)]
    names = [d.name for d in designs]
    duplicates = sorted({n for n in names if names.count(n) > 1})
    if duplicates:
        raise ValueError(f"Diseño repetido: {', '.join(duplicates)}")
    if len(designs) < min_designs:
        raise ValueError(f"Se requieren al menos {min_designs} configuraciones; hay {len(designs)}")
    return designs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("plan", type=Path)
    parser.add_argument("--shell", action="store_true", help="Salida para run_e6.sh")
    args = parser.parse_args()
    try:
        designs = load_plan(args.plan)
    except ValueError as err:
        print(f"Plan inválido: {err}", file=sys.stderr)
        return 1
    for d in designs:
        if args.shell:
            print(d.name, d.cores, d.width, d.vl_bits, d.protocol)
        else:
            print(f"{d.name:24s} costo={d.cost:5g}  {d.rationale}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
