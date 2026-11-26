#!/usr/bin/env bash
# Detiene el script inmediatamente si ocurre un error, se usa una variable no definida o falla un pipe
set -euo pipefail

# ==============================================================================
# E2: Exploración superescalar (ArmO3CPU, 1 núcleo, GEMM escalar)
# Barre ancho del pipeline {1, 2, 4, 8} x tamaño de ROB {32, 64, 192} = 12 corridas
# y genera results/e2/e2.csv automáticamente.
# ==============================================================================

# --- Bloque 1: Rutas dentro del contenedor Docker ---
GEM5_BIN="${GEM5_BIN:-/opt/gem5/build/ARM_MESI/gem5.opt}"
SE_SCRIPT="${SE_SCRIPT:-/opt/gem5/configs/deprecated/example/se.py}"
GEM5_ROOT="${GEM5_ROOT:-/opt/gem5}"

SRC="src/gemm_scalar.c"
BIN="results/e2/gemm_scalar"
OUT_ROOT="results/e2"
# Tamaño de matriz por defecto N=128 (se puede cambiar corriendo: N=64 bash scripts/run_e2.sh)
N="${N:-128}"

if [[ ! -f "$SRC" ]]; then
    echo "Error: no se encontró $SRC. Asegúrate de tener el benchmark escalar en src/." >&2
    exit 1
fi

mkdir -p "$OUT_ROOT"

# --- Bloque 2: Compilación cruzada estática para AArch64 con m5ops (ROI) ---
echo "[E2] Compilando $SRC -> $BIN"
aarch64-linux-gnu-gcc -O2 -static \
    -I"${GEM5_ROOT}/include" \
    "$SRC" "${GEM5_ROOT}/util/m5/build/arm64/out/libm5.a" \
    -o "$BIN"

# --- Bloque 3: Barrido de 12 configuraciones (4 anchos x 3 tamaños de ROB) ---
WIDTHS=(1 2 4 8)
ROBS=(32 64 192)

for w in "${WIDTHS[@]}"; do
    for rob in "${ROBS[@]}"; do
        out_dir="${OUT_ROOT}/w${w}_rob${rob}_N${N}"
        echo "[E2] Ejecutando width=${w}, ROB=${rob}, N=${N} -> ${out_dir}"
        # Se ajustan de forma coherente los 5 anchos del pipeline O3 y numROBEntries
        # El '&' ejecuta en paralelo los 3 ROB de cada ancho; quitar '&' si hay poca RAM
        "$GEM5_BIN" -d "$out_dir" "$SE_SCRIPT" \
            --cpu-type=ArmO3CPU \
            --caches --l2cache \
            --param "system.cpu[0].fetchWidth=${w}" \
            --param "system.cpu[0].decodeWidth=${w}" \
            --param "system.cpu[0].renameWidth=${w}" \
            --param "system.cpu[0].issueWidth=${w}" \
            --param "system.cpu[0].commitWidth=${w}" \
            --param "system.cpu[0].numROBEntries=${rob}" \
            -c "$BIN" -o "$N" &
    done
    # Espera a que terminen los 3 ROB del ancho actual antes de pasar al siguiente
    wait
done

# --- Bloque 4: Extracción de métricas de la ROI a CSV ---
echo "[E2] Extrayendo métricas de la ROI -> ${OUT_ROOT}/e2.csv"
python3 scripts/parse_stats.py "$OUT_ROOT" -o "${OUT_ROOT}/e2.csv"
echo "[E2] Listo: ${OUT_ROOT}/e2.csv"
