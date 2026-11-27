#!/usr/bin/env bash
# ==============================================================================
# E6: Exploración bajo presupuesto (costo <= 32) con GEMM paralelo + SVE.
# Corre cada diseño de configs/e6.csv (núcleos O3, ancho, VL, protocolo Ruby)
# y genera results/e6/e6.csv y results/e6/e6_summary.md.
#
#   bash scripts/run_e6.sh                         # todos los diseños, N = 128
#   SIZES=256 FILTER='c8_w4|c4_w8' bash scripts/run_e6.sh   # sensibilidad
#   SMOKE=1 bash scripts/run_e6.sh                 # validación rápida, N = 16
# Las corridas ya válidas se reutilizan; FORCE=1 las repite.
# Variables: JOBS (4), PLAN, OUT_ROOT, SIZES, FILTER (regex sobre el nombre).
# ==============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/lib.sh

PLAN="${PLAN:-configs/e6.csv}"
if [[ "${SMOKE:-0}" == 1 ]]; then
    OUT_ROOT="${OUT_ROOT:-results/e6_smoke}"; SIZES="${SIZES:-16}"
else
    OUT_ROOT="${OUT_ROOT:-results/e6}"; SIZES="${SIZES:-128}"
fi
FILTER="${FILTER:-.}"
BIN="$OUT_ROOT/bin/gemm_omp_sve"

mkdir -p "$OUT_ROOT"
mapfile -t DESIGNS < <(python3 scripts/e6_plan.py "$PLAN" --shell | grep -E -- "$FILTER" || true)
(( ${#DESIGNS[@]} > 0 )) || { echo "[E6] Ningún diseño coincide con FILTER=$FILTER" >&2; exit 1; }

echo "[E6] Compilando gemm_omp_sve"
compile_benchmark src/gemm_omp_sve.c "$BIN" -O3 -march=armv8-a+sve -fopenmp

run_case() {
    local dir=$1 gem5=$2 expected=$3; shift 3
    if [[ "${FORCE:-0}" != 1 && -f "$dir/run.log" ]] && check_run "$dir" "$expected" 2>/dev/null; then
        echo "[E6] Reutilizada $dir"; return 0
    fi
    rm -rf "$dir"; mkdir -p "$dir"
    "$gem5" -d "$dir" "$SE_SCRIPT" "$@" > "$dir/run.log" 2>&1 \
        || { echo "[ERROR] gem5 falló en $dir" >&2; return 1; }
    check_run "$dir" "$expected" && grep -Fq 'm5_exit instruction encountered' "$dir/run.log" \
        && echo "[E6] OK $dir"
}

for n in $SIZES; do
    for line in "${DESIGNS[@]}"; do
        read -r name cores width vl protocol <<< "$line"
        mapfile -t width_args < <(o3_width_params "$width")
        mapfile -t vl_args < <(sve_vl_param "$vl")
        launch run_case "$OUT_ROOT/${name}_N$n" "$(gem5_bin "$protocol")" \
            "GEMM OpenMP SVE N=$n hilos=$cores VL=$vl bits: OK" \
            -n "$cores" --cpu-type=ArmO3CPU "${RUBY_ARGS[@]}" "${width_args[@]}" "${vl_args[@]}" \
            -c "$BIN" -o "$n $cores"
    done
done
wait_all || { echo "[E6] Hubo corridas fallidas" >&2; exit 1; }

python3 scripts/e6_report.py "$OUT_ROOT" --plan "$PLAN" \
    -o "$OUT_ROOT/e6.csv" --summary "$OUT_ROOT/e6_summary.md"
echo "[E6] Listo: $OUT_ROOT/e6.csv y $OUT_ROOT/e6_summary.md"
