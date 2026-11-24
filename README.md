
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

## Estructura

- `src/` — benchmarks en C (GEMM escalar, SVE, paralelo, falso compartido)
- `configs/` — configuraciones de gem5 y de E6
- `scripts/` — corridas por experimento y extracción de métricas
- `results/` — salidas de gem5 por corrida y CSV
- `report/` — informe IEEE y figuras

## Entorno

| Componente | Versión |
|---|---|
| gem5 | v26.0.0.0 (commit fed0e07e930fecf1e73dce94dd44e69a5bf70c46) |
| Compilador cruzado | aarch64-linux-gnu-gcc (Ubuntu 15.2.0-16ubuntu1) 15.2.0 |
| Sistema base | Ubuntu 24.04 (contenedor Docker) |

## Reproducción

_Pendiente: construcción del contenedor y comandos para regenerar todos los CSV y gráficos._
