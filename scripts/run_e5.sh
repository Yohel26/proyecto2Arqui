#!/usr/bin/env bash
# Run inside the project Docker container, from any directory.
set -euo pipefail
cd "$(dirname "$0")/.."
ulimit -c 0
GEM5_ROOT=${GEM5_ROOT:-/opt/gem5}
SE_SCRIPT=${SE_SCRIPT:-$GEM5_ROOT/configs/deprecated/example/se.py}
MESI_BIN=${MESI_BIN:-$GEM5_ROOT/build/ARM_MESI/gem5.opt}
MOESI_BIN=${MOESI_BIN:-$GEM5_ROOT/build/ARM_MOESI/gem5.opt}
ITERATIONS=${ITERATIONS:-100000}
SMOKE=${SMOKE:-0}
if [[ "$SMOKE" == 1 ]]; then
    OUT_ROOT=${OUT_ROOT:-results/e5_smoke}
    CORES=(4); SIZES=(16); EXPECT=6; ITERATIONS=10000
else
    OUT_ROOT=${OUT_ROOT:-results/e5}
    CORES=(2 4 8); SIZES=(64 128); EXPECT=24
fi
if [[ -e "$OUT_ROOT" ]]; then
    echo "Output already exists: $OUT_ROOT. Use OUT_ROOT=results/e5_retry or move old folder." >&2; exit 1
fi
mkdir -p "$OUT_ROOT"
BUILD=$(mktemp -d)
trap 'rm -rf "$BUILD"' EXIT
FLAGS=(-O2 -static -fopenmp -I"$GEM5_ROOT/include")
LIB="$GEM5_ROOT/util/m5/build/arm64/out/libm5.a"
for f in "$MESI_BIN" "$MOESI_BIN" "$SE_SCRIPT" "$LIB"; do [[ -f "$f" ]] || { echo "Missing $f" >&2; exit 1; }; done
grep -q GEM5_EXPLICIT_EXIT src/gemm_omp.c || { echo 'Install E5-compatible gemm_omp.c first' >&2; exit 1; }
aarch64-linux-gnu-gcc "${FLAGS[@]}" src/false_sharing.c "$LIB" -o "$BUILD/false_sharing"
aarch64-linux-gnu-gcc "${FLAGS[@]}" -DGEM5_EXPLICIT_EXIT src/gemm_omp.c "$LIB" -o "$BUILD/gemm_omp"
run_case() {
    local dir=$1 binary=$2 args=$3 expected=$4
    mkdir -p "$dir"
    echo "[E5] $dir"
    "$GEM5_BIN" -d "$dir" "$SE_SCRIPT" --cpu-type=ArmTimingSimpleCPU --ruby \
        --cacheline_size=64 --l1d_size=64kB --l1i_size=32kB --l1d_assoc=2 --l1i_assoc=2 \
        --l2_size=2MB --l2_assoc=8 --num-l2caches=1 --num-dirs=1 \
        --cpu-clock=2GHz --ruby-clock=2GHz -n "$ncores" -c "$binary" -o "$args" 2>&1 | tee "$dir/run.log"
    grep -Fq "$expected" "$dir/run.log"
    grep -Fq 'm5_exit instruction encountered' "$dir/run.log"
    [[ $(grep -c 'Begin Simulation Statistics' "$dir/stats.txt") == 2 ]]
    [[ $(grep -c 'End Simulation Statistics' "$dir/stats.txt") == 2 ]]
}
for protocol in mesi moesi; do
    if [[ "$protocol" == mesi ]]; then GEM5_BIN=$MESI_BIN; else GEM5_BIN=$MOESI_BIN; fi
    for ncores in "${CORES[@]}"; do
        for mode in nopad pad; do
            dir="$OUT_ROOT/${protocol}_n${ncores}_${mode}"
            run_case "$dir" "$BUILD/false_sharing" "$ncores $mode $ITERATIONS" "False sharing hilos=$ncores modo=$mode iteraciones=$ITERATIONS: OK"
            printf '%s\n' "$ITERATIONS" > "$dir/iterations.txt"
        done
        for n in "${SIZES[@]}"; do
            run_case "$OUT_ROOT/${protocol}_n${ncores}_gemm_N${n}" "$BUILD/gemm_omp" "$n $ncores" "GEMM OpenMP N=$n hilos=$ncores: OK"
        done
    done
done
python3 scripts/parse_e5.py "$OUT_ROOT" --expect "$EXPECT"
