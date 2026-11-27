#!/usr/bin/env bash
# Ejecuta un comando dentro del contenedor del proyecto con el repositorio en /work.
# Los archivos generados quedan a nombre del usuario actual (no de root).
#   bash scripts/docker.sh bash scripts/run_e3.sh
#   bash scripts/docker.sh python3 -m unittest discover -s tests
set -euo pipefail
IMAGE="${IMAGE:-yohel0926/gem5-gemm:v26-slim}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
TTY=()
[[ -t 0 && -t 1 ]] && TTY=(-it)
exec docker run --rm "${TTY[@]}" --user "$(id -u):$(id -g)" -e HOME=/tmp \
    -v "$REPO":/work -w /work "$IMAGE" "$@"
