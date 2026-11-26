#!/usr/bin/env bash
# Detiene el script inmediatamente si ocurre un error, se usa una variable no definida o falla un pipe
set -euo pipefail

# ==============================================================================
# E4: Multiprocesador de memoria compartida (ArmO3CPU ancho 2, GEMM paralelo)
# Barre 1, 2, 4 y 8 núcleos con N = 128 (4 corridas en total)
# y genera results/e4/e4.csv automáticamente.
# ==============================================================================

# --- Bloque 1: Rutas dentro del contenedor Docker ---
GEM5_BIN="${GEM5_BIN:-/opt/gem5/build/ARM_MESI/gem5.opt}"
SE_SCRIPT="${SE_SCRIPT:-/opt/gem5/configs/deprecated/example/se.py}"
GEM5_ROOT="${GEM5_ROOT:-/opt/gem5}"

SRC="src/gemm_omp.c"
BIN="results/e4/gemm_omp"
OUT_ROOT="results/e4"
# Tamaño de matriz por defecto N=128 (se puede cambiar: N=64 bash scripts/run_e4.sh)
N="${N:-128}"

if [[ ! -f "$SRC" ]]; then
    echo "Error: no se encontró $SRC. Asegúrate de tener el benchmark paralelo en src/." >&2
    exit 1
fi

mkdir -p "$OUT_ROOT"

# --- Bloque 2: Compilación cruzada estática con OpenMP y m5ops (ROI) ---
# -fopenmp habilita OpenMP (validado en modo SE con -static en gem5 v26)
echo "[E4] Compilando $SRC -> $BIN"
aarch64-linux-gnu-gcc -O2 -static -fopenmp \
    -I"${GEM5_ROOT}/include" \
    "$SRC" "${GEM5_ROOT}/util/m5/build/arm64/out/libm5.a" \
    -o "$BIN"

# --- Bloque 3: Barrido de núcleos (1, 2, 4 y 8 núcleos O3 de ancho 2) ---
CORES=(1 2 4 8)

for ncores in "${CORES[@]}"; do
    out_dir="${OUT_ROOT}/n${ncores}_N${N}"
    echo "[E4] Ejecutando ${ncores} núcleo(s) ArmO3CPU (ancho 2), N=${N} -> ${out_dir}"
    # system.cpu[:] aplica los parámetros a todos los núcleos (0..ncores-1)
    # -o "${N} ${ncores}" pasa tamaño de matriz y número de hilos al programa C
    # Nota: se corre secuencialmente porque cada simulación multicore usa bastante RAM/CPU
    "$GEM5_BIN" -d "$out_dir" "$SE_SCRIPT" \
        -n "$ncores" \
        --cpu-type=ArmO3CPU \
        --caches --l2cache \
        --param "system.cpu[:].fetchWidth=2" \
        --param "system.cpu[:].decodeWidth=2" \
        --param "system.cpu[:].renameWidth=2" \
        --param "system.cpu[:].issueWidth=2" \
        --param "system.cpu[:].commitWidth=2" \
        -c "$BIN" -o "${N} ${ncores}"
done

# --- Bloque 4: Extracción de métricas de la ROI a CSV ---
echo "[E4] Extrayendo métricas de la ROI -> ${OUT_ROOT}/e4.csv"
python3 scripts/parse_stats.py "$OUT_ROOT" -o "${OUT_ROOT}/e4.csv"
echo "[E4] Listo: ${OUT_ROOT}/e4.csv"
