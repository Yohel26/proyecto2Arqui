#!/usr/bin/env bash
# Funciones comunes para los scripts de corrida (se carga con `source`).
# Rutas de gem5 dentro del contenedor; se pueden sobreescribir con variables de entorno.

GEM5_ROOT="${GEM5_ROOT:-/opt/gem5}"
SE_SCRIPT="${SE_SCRIPT:-$GEM5_ROOT/configs/deprecated/example/se.py}"
M5_LIB="${M5_LIB:-$GEM5_ROOT/util/m5/build/arm64/out/libm5.a}"
JOBS="${JOBS:-4}"

# gem5.opt para un protocolo: mesi | moesi
gem5_bin() {
    case "$1" in
        mesi)  echo "${MESI_BIN:-$GEM5_ROOT/build/ARM_MESI/gem5.opt}" ;;
        moesi) echo "${MOESI_BIN:-$GEM5_ROOT/build/ARM_MOESI/gem5.opt}" ;;
        *) echo "Protocolo desconocido: $1" >&2; return 1 ;;
    esac
}

# compile_benchmark <fuente.c> <binario> [flags extra...]
# Compilación cruzada estática para AArch64 con m5ops (ROI).
compile_benchmark() {
    local src=$1 out=$2; shift 2
    mkdir -p "$(dirname "$out")"
    aarch64-linux-gnu-gcc -static -Wall -Wextra -Isrc -I"$GEM5_ROOT/include" \
        "$@" "$src" "$M5_LIB" -o "$out" 2> >(grep -v -e dlopen -e gomp_load -e 'libgomp.a' >&2)
}

# Parámetros O3 coherentes para un ancho de emisión: o3_width_params <ancho>
o3_width_params() {
    local w=$1 p
    for p in fetchWidth decodeWidth renameWidth dispatchWidth issueWidth wbWidth commitWidth; do
        printf -- '--param\nsystem.cpu[:].%s=%s\n' "$p" "$w"
    done
}

# Parámetro de longitud vectorial SVE en bits (múltiplo de 128).
sve_vl_param() {
    printf -- '--param\nsystem.cpu[:].isa[:].sve_vl_se=%s\n' "$(( $1 / 128 ))"
}

# check_run <carpeta> <texto esperado en run.log>
# Verifica que el programa validó su resultado y que existe el bloque de la ROI.
check_run() {
    local dir=$1 expected=$2 blocks
    if ! grep -Fq "$expected" "$dir/run.log"; then
        echo "[ERROR] $dir: falta '$expected' en run.log" >&2; return 1
    fi
    blocks=$(grep -c 'Begin Simulation Statistics' "$dir/stats.txt" 2>/dev/null || true)
    if (( blocks < 2 )); then
        echo "[ERROR] $dir: stats.txt sin bloque de ROI ($blocks bloques)" >&2; return 1
    fi
}

# launch <comando...>: lo corre en segundo plano con a lo sumo $JOBS simultáneos.
PIDS=()
launch() {
    while (( $(jobs -rp | wc -l) >= JOBS )); do wait -n || true; done
    "$@" &
    PIDS+=("$!")
}

# Espera todos los trabajos lanzados; falla si alguno falló
# (bash conserva el estado de los procesos ya recogidos por wait -n).
wait_all() {
    local failed=0 pid
    for pid in "${PIDS[@]}"; do wait "$pid" || failed=1; done
    PIDS=()
    return $failed
}

# Prepara una carpeta de salida nueva; no sobreescribe resultados existentes.
fresh_out_root() {
    if [[ -e "$1" && "${FORCE:-0}" != 1 ]]; then
        echo "Ya existe $1. Use FORCE=1 para sobreescribir u OUT_ROOT=otra/carpeta." >&2
        return 1
    fi
    rm -rf "$1"; mkdir -p "$1"
}
