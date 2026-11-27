# E6: Exploración bajo presupuesto y propuesta

**Metodología.** Cada diseño de `configs/e6.csv` define núcleos, ancho de emisión
O3 (fetch/decode/rename/dispatch/issue/wb/commit iguales), VL de SVE y protocolo.
`scripts/cost.py` valida `Costo = N × (W/2 + VL/128) ≤ 32`. Todos usan
`ArmO3CPU` (ROB 192) con Ruby y la jerarquía de E5 (L1D 64 kB privada, L2
compartida de 2 MB, 2 GHz), y `src/gemm_omp_sve.c`: filas de C repartidas
estáticamente entre hilos (uno por núcleo) y cada fila calculada con el núcleo
SVE de E3. El tiempo es el de la ROI (`simTicks`); GFLOP/s = 2N³ / tiempo.
Cada corrida verifica C contra la referencia en doble precisión.

## Resultados, N = 128 (`results/e6/e6.csv`)

| Diseño | Costo | Tiempo (µs) | GFLOP/s | GFLOP/s por unidad |
|---|---|---|---|---|
| 4 núcleos · ancho 8 · VL 512 · MESI | 32 | **130.2** | **32.2** | 1.01 |
| 8 · 4 · 256 · MOESI | 32 | 133.5 | 31.4 | 0.98 |
| **4 · 4 · 512 · MESI** | **24** | **134.0** | **31.3** | **1.30** |
| 4 · 8 · 512 · MOESI | 32 | 135.8 | 30.9 | 0.97 |
| 8 · 4 · 256 · MESI | 32 | 138.1 | 30.4 | 0.95 |
| 2 · 8 · 1024 · MESI | 24 | 142.7 | 29.4 | 1.22 |
| 8 · 2 · 256 · MESI | 24 | 155.4 | 27.0 | 1.12 |
| 16 · 2 · 128 · MESI | 32 | 171.4 | 24.5 | 0.76 |
| 4 · 4 · 256 · MESI | 16 | 213.1 | 19.7 | 1.23 |
| 2 · 8 · 512 · MESI | 16 | 217.0 | 19.3 | 1.21 |
| 1 · 8 · 1024 · MESI | 12 | 226.9 | 18.5 | 1.54 |
| 1 · 4 · 1024 · MESI | 10 | 237.0 | 17.7 | 1.77 |
| 8 · 2 · 128 · MESI | 16 | 240.4 | 17.4 | 1.09 |

Figura: `report/figures/e6_designs.png`. Resumen automático: `results/e6/e6_summary.md`.

## Lectura de los resultados

1. **La VL es el recurso más rentable hasta 512 bits.** Con 4 núcleos y ancho 4,
   pasar de VL 256 a 512 (costo 16 → 24) baja el tiempo de 213 a 134 µs (1.59×).
   Es coherente con E3: la reducción de instrucciones escala con VL.
2. **El ancho 8 casi no aporta.** 4·8·512 es solo 2.9 % más rápido que 4·4·512
   y cuesta 8 unidades más; en un núcleo, 1·8·1024 es 4.3 % más rápido que
   1·4·1024. El bucle SVE tiene pocas instrucciones por iteración (2 cargas,
   `fmla`, almacenamiento, control) y está limitado por memoria, así que un
   ancho de emisión de 4 ya extrae casi todo el ILP disponible.
3. **Muchos núcleos simples pierden (Hill y Marty).** 16·2·128 (costo 32) tarda
   171 µs, peor que 4·4·512 (costo 24). Con VL 128 cada núcleo ejecuta 4× más
   instrucciones que con VL 512, y el arranque y la barrera de OpenMP más el
   tráfico de coherencia crecen con el número de núcleos.
4. **VL 1024 con pocos núcleos no alcanza.** 2·8·1024 (142.7 µs) queda detrás de
   4·4·512 con el mismo costo: con N = 128 una fila es de 512 B y cada `ld1w` de
   1024 bits ocupa 2 líneas, lo que agrava el cuello de botella de memoria que se
   vio en E3.
5. **El protocolo es de segundo orden.** MOESI fue 4.3 % más lento en 4·8·512 y
   3.4 % más rápido en 8·4·256. GEMM reparte filas sin compartir líneas
   escritas, así que hay poco tráfico de coherencia y el signo de la diferencia
   cambia según el diseño (no se midió la causa por estado). Coincide con
   E5, donde las diferencias de GEMM entre protocolos fueron del 1–5 %.

## Propuesta

- **Mejor por tiempo:** 4 núcleos · ancho 8 · VL 512 · MESI (costo 32, 130.2 µs).
- **Recomendada:** **4 núcleos · ancho 4 · VL 512 · MESI (costo 24, 134.0 µs).**
  Queda a 2.9 % del mejor tiempo con 25 % menos costo, tiene el mejor
  rendimiento/costo entre los diseños rápidos (1.30 GFLOP/s por unidad) y con
  N = 256 empata en tiempo con el diseño de costo 32. Las 8 unidades restantes
  no compran rendimiento medible en esta carga.
- El máximo rendimiento/costo absoluto es 1·4·1024 (1.77), pero tarda 1.8× más
  que la propuesta; solo conviene si el objetivo es costo y no tiempo.

## Sensibilidad

**Presupuesto 16.** El mejor es 4·4·256 (213 µs), seguido de cerca por 2·8·512
(217 µs). Ambos son 1.6× más lentos que la propuesta, porque no alcanza para
VL 512 con 4 núcleos: con presupuesto bajo conviene repartir el costo de forma
equilibrada entre núcleos y VL en lugar de maximizar un solo recurso
(8·2·128 es el peor, 240 µs).

**N = 256 (corrido) y N = 1024 (extrapolado).**

| Diseño | Costo | N = 128 (µs) | N = 256 (µs) | GFLOP/s N = 256 |
|---|---|---|---|---|
| 4·8·512 | 32 | 130.2 | 2391.0 | 14.0 |
| 4·4·512 | 24 | 134.0 | 2392.9 | 14.0 |
| 8·4·256 | 32 | 138.1 | 2396.3 | 14.0 |
| 2·8·1024 | 24 | 142.7 | 2411.4 | 13.9 |
| 1·8·1024 | 12 | 226.9 | 2796.9 | 12.0 |

El trabajo crece 8×, pero el tiempo crece 18×. Todos los diseños multinúcleo
convergen a ≈ 2390 µs (14 GFLOP/s) sin importar su costo: con N = 256, B
(256 kB) ya no cabe en la L1D de ningún núcleo y todos la leen en cada fila
desde la única L2 compartida, que pasa a ser el cuello de botella. Con
N = 1024 las tres matrices ocupan 12 MB y superan la L2 de 2 MB, así que el
límite pasa a ser la memoria principal y se espera un rendimiento todavía menor.
No se simuló porque requiere ~64× el trabajo de N = 256 más una verificación
O(N³) en un solo núcleo (días de simulación). La conclusión cambia: para N
grande conviene el diseño más barato que sature el ancho de banda (p. ej.
2·8·1024 o 4·4·512), y más VL o más núcleos solo ayudan si el código usa
bloqueo (tiling) para reutilizar datos en L1, como plantean Goto y van de Geijn.
