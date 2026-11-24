
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

_Pendiente: construcción del contenedor y comandos para regenerar todos los CSV y gráficos._
