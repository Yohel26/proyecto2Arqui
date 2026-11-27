
# Proyecto gem5 — Aceleración de GEMM

EL4314 Arquitectura de Computadores · TEC · II semestre 2026

Exploración de arquitectura en gem5 (ARM, modo SE) para minimizar el tiempo de
C = A × B bajo el presupuesto Costo = Nnúcleos × (Wissue/2 + VL/128) ≤ 32.

## Integrantes

| Integrante | Responsabilidades |
|---|---|
| Alejandro Bejarano Rodríguez | Scripts de automatización, E2 Superescalar, E4 Multiprocesador |
| Yohel Alas Gómez | Entorno gem5/Docker, E3 Vectorial, E6 Integración |
| Julio Quesada Hernández | Benchmarks, E1 Línea base, E5 Coherencia |

E1 y E6 se hacen entre todos.

### Estructura

- `src/` — benchmarks en C (GEMM escalar, SVE, paralelo, falso compartido)
- `configs/` — configuraciones de gem5 y de E6
- `scripts/` — corridas por experimento y extracción de métricas
- `results/` — salidas de gem5 por corrida y CSV
- `report/` — informe IEEE y figuras
- `docker/` — recetas del entorno (Dockerfile y configuraciones de compilación de gem5)

## Entorno

| Componente | Versión |
|---|---|
| gem5 | v26.0.0.0 (commit fed0e07e930fecf1e73dce94dd44e69a5bf70c46) |
| Protocolos Ruby | MESI_Two_Level (`build/ARM_MESI`), MOESI_CMP_directory (`build/ARM_MOESI`) |
| Modelos de CPU | ArmTimingSimpleCPU, ArmMinorCPU, ArmO3CPU |
| Compilador cruzado | aarch64-linux-gnu-gcc 13.3.0 (Ubuntu 13.3.0-6ubuntu2~24.04.1) |
| Sistema base | Ubuntu 24.04 (contenedor Docker) |

### Usar el entorno

    docker pull yohel0926/gem5-gemm:v26-slim
    docker run --rm -it -v "$PWD":/work yohel0926/gem5-gemm:v26-slim bash

El repositorio queda montado en `/work` dentro del contenedor.
Digest de la imagen usada en el proyecto:
`sha256:7a93182bf1f8dd0b0d4a8d844e2177cbe9197d4e53db83c7e306d2d69b015379`

### Reconstruir la imagen desde cero (2–3 h)

    docker build -t gem5-gemm:v26 docker/
    docker build -f docker/Dockerfile.slim -t gem5-gemm:v26-slim docker/
    
La imagen slim se genera a partir de la completa, así que se construyen en ese orden.
La compilación usa 2 procesos en paralelo (`JOBS=2`) para no agotar la RAM; se puede cambiar con `--build-arg JOBS=n`.

## Reproducción

Todos los comandos se ejecutan desde la raíz del repositorio. `scripts/docker.sh`
corre un comando dentro del contenedor con el repositorio en `/work` y deja los
archivos a nombre del usuario actual (dentro del contenedor se puede omitir).

### Pruebas

    bash scripts/docker.sh python3 -m unittest discover -s tests

Compilan los benchmarks para el host (`-DNATIVE`) y verifican el resultado de
GEMM y la validación de argumentos; también prueban el modelo de costo, el plan
de E6 y las tablas de E3 y E6. Las rutas SVE se validan en gem5 con `SMOKE=1`.

### Experimentos

| Exp. | Comando | Salida |
|---|---|---|
| E1 | `bash scripts/docker.sh bash scripts/run_e1.sh` | `results/e1/e1.csv` |
| E2 | `bash scripts/docker.sh bash scripts/run_e2.sh` | `results/e2/e2.csv` |
| E3 | `bash scripts/docker.sh bash scripts/run_e3.sh` | `results/e3/e3.csv`, `gemm_sve.dis` |
| E4 | `bash scripts/docker.sh bash scripts/run_e4.sh` | `results/e4/e4.csv` |
| E5 | `bash scripts/docker.sh bash scripts/run_e5.sh` | `results/e5/e5.csv`, `e5_states.csv` |
| E6 | `bash scripts/docker.sh bash scripts/run_e6.sh` | `results/e6/e6.csv`, `e6_summary.md` |

Gráficos (en `report/figures/`):

    bash scripts/docker.sh python3 scripts/plot_results.py
    bash scripts/docker.sh python3 scripts/plot_e5.py

Opciones de E3 y E6 (variables de entorno):

- `SMOKE=1`: validación rápida con N = 16 en `results/e3_smoke` o `results/e6_smoke`.
- `JOBS=n`: simulaciones simultáneas (4 por defecto; cada una usa ~1 GB de RAM).
- `FORCE=1`: repite corridas existentes. E6 reutiliza las corridas que ya pasaron
  la verificación, así que se puede reanudar si se interrumpe.
- E6: `SIZES="128 256"` y `FILTER='regex'` seleccionan tamaños y diseños, p. ej.
  `SIZES=256 FILTER='c8_w4_vl256_mesi' bash scripts/run_e6.sh` (sensibilidad).

### E6: modelo de costo y plan

- `scripts/cost.py` es la única definición de `Costo = Nnúcleos × (Wissue/2 + VL/128)`,
  del presupuesto (32) y de los rangos válidos.
- `configs/e6.csv` lista los diseños (núcleos, ancho, VL, protocolo, justificación);
  `python3 scripts/e6_plan.py configs/e6.csv` muestra su costo y rechaza los que
  exceden el presupuesto.
- Todos los diseños usan núcleos `ArmO3CPU` con Ruby (misma jerarquía de E5) y
  `src/gemm_omp_sve.c` con un hilo por núcleo.

### Benchmarks

`src/gemm_common.h` concentra la lectura de argumentos, la ROI
(`m5_reset_stats`/`m5_dump_stats`), la inicialización y verificación de GEMM y el
reparto de filas con OpenMP; `src/gemm_kernels.h` contiene el núcleo SVE
compartido por `gemm_sve.c` y `gemm_omp_sve.c`. Cada benchmark solo define su
núcleo de cómputo. Las métricas se toman solo del bloque de la ROI de `stats.txt`.
