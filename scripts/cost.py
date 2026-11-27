"""Modelo de costo del proyecto (fuente única de la fórmula y sus límites).

    Costo = Nnúcleos × (Wissue / 2 + VL / 128)

Wissue: ancho de emisión del núcleo O3 (1, 2, 4 u 8).
VL: longitud vectorial SVE en bits (múltiplo de 128, de 128 a 1024).
"""

from __future__ import annotations

BUDGET = 32
WIDTHS = (1, 2, 4, 8)
VL_MIN, VL_MAX, VL_STEP = 128, 1024, 128
# gemm_omp_sve.c admite hasta 16 hilos (un hilo por núcleo simulado)
MAX_CORES = 16


def cost(cores: int, width: int, vl_bits: int) -> float:
    return cores * (width / 2 + vl_bits / 128)


def validate_design(cores: int, width: int, vl_bits: int, budget: float = BUDGET) -> float:
    """Devuelve el costo del diseño o lanza ValueError si no es válido."""
    if not 1 <= cores <= MAX_CORES:
        raise ValueError(f"Número de núcleos fuera de rango (1..{MAX_CORES}): {cores}")
    if width not in WIDTHS:
        raise ValueError(f"Ancho de emisión inválido {width}; use uno de {WIDTHS}")
    if not (VL_MIN <= vl_bits <= VL_MAX and vl_bits % VL_STEP == 0):
        raise ValueError(f"VL inválida {vl_bits}; múltiplo de {VL_STEP} entre {VL_MIN} y {VL_MAX}")
    value = cost(cores, width, vl_bits)
    if value > budget:
        raise ValueError(f"Costo {value:g} excede el presupuesto de {budget:g}")
    return value
