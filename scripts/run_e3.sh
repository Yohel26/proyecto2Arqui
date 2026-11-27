#!/usr/bin/env bash
# ==============================================================================
# E3: Extensiones vectoriales SVE (ArmO3CPU, 1 núcleo, caché clásica L1+L2)
# Escalar vs. SVE con VL = 128, 256, 512, 1024 bits para N = 64 y 128
# (10 corridas). Genera results/e3/e3.csv y la evidencia de vectorización.
#
#   bash scripts/run_e3.sh            # experimento completo
#   SMOKE=1 bash scripts/run_e3.sh    # validación rápida con N = 16
# Variables: JOBS (corridas simultáneas, 4), OUT_ROOT, FORCE=1 para rehacer.
# ==============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/lib.sh

if [[ "${SMOKE:-0}" == 1 ]]; then
    OUT_ROOT="${OUT_ROOT:-results/e3_smoke}"; SIZES=(16); VLS=(128 512 1024)
else
    OUT_ROOT="${OUT_ROOT:-results/e3}"; SIZES=(64 128); VLS=(128 256 512 1024)
fi
GEM5_BIN="$(gem5_bin mesi)"
CPU=ArmO3CPU
# Mismas banderas para ambas versiones; el núcleo escalar desactiva la
# vectorización con optimize("no-tree-vectorize"), así que solo cambia el núcleo.
CFLAGS=(-O3 -march=armv8-a+sve)

fresh_out_root "$OUT_ROOT"
BIN="$OUT_ROOT/bin"

# --- Compilación y evidencia de vectorización ---
echo "[E3] Compilando gemm_scalar y gemm_sve (${CFLAGS[*]})"
compile_benchmark src/gemm_scalar.c "$BIN/gemm_scalar" "${CFLAGS[@]}"
compile_benchmark src/gemm_sve.c "$BIN/gemm_sve" "${CFLAGS[@]}" -fopt-info-vec 2> "$OUT_ROOT/opt_info_vec.txt"

disasm() { aarch64-linux-gnu-objdump -d --no-show-raw-insn "$1" | awk -v f="<$2>:" '$0 ~ f {p=1} p && /^$/ {p=0} p'; }
disasm "$BIN/gemm_sve" gemm_sve > "$OUT_ROOT/gemm_sve.dis"
disasm "$BIN/gemm_scalar" gemm_scalar > "$OUT_ROOT/gemm_scalar.dis"
for insn in whilelo ld1w fmla st1w; do
    grep -qw "$insn" "$OUT_ROOT/gemm_sve.dis" || { echo "[E3] gemm_sve no contiene $insn" >&2; exit 1; }
done
if grep -Eq '\bz[0-9]+\.' "$OUT_ROOT/gemm_scalar.dis"; then
    echo "[E3] gemm_scalar contiene instrucciones SVE" >&2; exit 1
fi
echo "[E3] Vectorización confirmada: $OUT_ROOT/gemm_sve.dis"

# --- Corridas ---
run_case() {
    local dir=$1 expected=$2; shift 2
    mkdir -p "$dir"
    "$GEM5_BIN" -d "$dir" "$SE_SCRIPT" --cpu-type="$CPU" --caches --l2cache "$@" \
        > "$dir/run.log" 2>&1 || { echo "[ERROR] gem5 falló en $dir" >&2; return 1; }
    check_run "$dir" "$expected" && echo "[E3] OK $dir"
}

for n in "${SIZES[@]}"; do
    launch run_case "$OUT_ROOT/scalar_N$n" "GEMM escalar N=$n: OK" \
        -c "$BIN/gemm_scalar" -o "$n"
    for vl in "${VLS[@]}"; do
        mapfile -t vl_args < <(sve_vl_param "$vl")
        launch run_case "$OUT_ROOT/sve_vl${vl}_N$n" "GEMM SVE N=$n VL=$vl bits: OK" \
            "${vl_args[@]}" -c "$BIN/gemm_sve" -o "$n"
    done
done
wait_all || { echo "[E3] Hubo corridas fallidas" >&2; exit 1; }

python3 scripts/e3_report.py "$OUT_ROOT" -o "$OUT_ROOT/e3.csv"
echo "[E3] Listo: $OUT_ROOT/e3.csv"
