#!/usr/bin/env bash
# Detiene el script inmediatamente si ocurre un error, se usa una variable no definida o falla un pipe
set -euo pipefail

# ==============================================================================
# E1: Línea base de un núcleo (TimingSimple, Minor, O3) en modo SE (ARM)
# Ejecuta GEMM escalar para tamaños N = 64 y N = 128 (6 corridas en total)
# y genera results/e1/e1.csv automáticamente.
# ==============================================================================

# --- Bloque 1: Rutas dentro del contenedor Docker (pueden sobreescribirse con env vars) ---
GEM5_BIN="${GEM5_BIN:-/opt/gem5/build/ARM_MESI/gem5.opt}"
SE_SCRIPT="${SE_SCRIPT:-/opt/gem5/configs/deprecated/example/se.py}"
GEM5_ROOT="${GEM5_ROOT:-/opt/gem5}"

SRC="src/gemm_scalar.c"
BIN="results/e1/gemm_scalar"
OUT_ROOT="results/e1"

# Verifica que exista el código fuente en C antes de empezar
if [[ ! -f "$SRC" ]]; then
    echo "Error: no se encontró $SRC. Asegúrate de tener el benchmark de E1 en src/." >&2
    exit 1
fi

mkdir -p "$OUT_ROOT"

# --- Bloque 2: Compilación cruzada estática para AArch64 con soporte de m5ops (ROI) ---
# -static: necesario porque gem5 en modo SE no carga librerías dinámicas del host
# -I.../include y libm5.a: habilitan m5_reset_stats() y m5_dump_stats()
echo "[E1] Compilando $SRC -> $BIN"
aarch64-linux-gnu-gcc -O2 -static \
    -I"${GEM5_ROOT}/include" \
    "$SRC" "${GEM5_ROOT}/util/m5/build/arm64/out/libm5.a" \
    -o "$BIN"

# --- Bloque 3: Barrido de simulaciones (3 modelos de CPU x 2 tamaños de matriz) ---
CPUS=("ArmTimingSimpleCPU" "ArmMinorCPU" "ArmO3CPU")
SIZES=(64 128)

for cpu in "${CPUS[@]}"; do
    for n in "${SIZES[@]}"; do
        out_dir="${OUT_ROOT}/${cpu}_N${n}"
        echo "[E1] Ejecutando ${cpu} con N=${n} -> ${out_dir}"
        # -d guarda stats.txt/config.ini en su propia carpeta
        # --caches --l2cache activa la jerarquía de caché clásica (L1I/L1D + L2)
        # El '&' al final lanza las 6 corridas en paralelo; si una PC tiene poca RAM, quitar el '&'
        "$GEM5_BIN" -d "$out_dir" "$SE_SCRIPT" \
            --cpu-type="$cpu" \
            --caches --l2cache \
            -c "$BIN" -o "$n" &
    done
done

# Espera a que terminen todas las simulaciones lanzadas en segundo plano
wait

# --- Bloque 4: Extracción de métricas de la ROI a CSV ---
echo "[E1] Extrayendo métricas de la ROI -> ${OUT_ROOT}/e1.csv"
python3 scripts/parse_stats.py "$OUT_ROOT" -o "${OUT_ROOT}/e1.csv"
echo "[E1] Listo: ${OUT_ROOT}/e1.csv"
