# E3: Extensiones vectoriales SVE

**Configuración.** `ArmO3CPU` (parámetros por defecto, ROB 192), un núcleo, caché
clásica (L1D 64 kB 2 vías, L2 2 MB), GEMM en orden i-k-j, N = 64 y 128.
Escalar y SVE se compilan con las mismas banderas (`-O3 -march=armv8-a+sve`);
el núcleo escalar desactiva la vectorización con `optimize("no-tree-vectorize")`.
VL se fija con `system.cpu[:].isa[:].sve_vl_se = VL/128`; cada corrida imprime
la VL leída con `svcntb()` y el script verifica que coincide con la pedida.

**Vectorización.** El núcleo usa intrínsecos ACLE (`svwhilelt`, `svld1`,
`svmla_n`, `svst1`), agnósticos a la VL. El desensamblado
(`results/e3/gemm_sve.dis`) contiene `whilelo`, `ld1w`, `fmla` y `st1w`; el
escalar (`gemm_scalar.dis`) no contiene registros `z`. El mismo binario corre con
todas las VL.

**Validación cruzada.** La corrida escalar de E3 (N = 128) ejecuta 16 909 200
instrucciones en 19 012 034 ciclos; E1 con O3 dio 16 909 201 y 19 012 220.

## Resultados (`results/e3/e3.csv`)

| N | VL | Instrucciones | Ciclos | IPC | Speedup | Reducción instr. |
|---|---|---|---|---|---|---|
| 64 | escalar | 2 130 384 | 2 351 933 | 0.91 | 1.0 | 1.0 |
| 64 | 128 | 561 617 | 303 895 | 1.85 | 7.7 | 3.8 |
| 64 | 256 | 299 473 | 135 897 | 2.20 | 17.3 | 7.1 |
| 64 | 512 | 168 401 | 98 320 | 1.71 | 23.9 | 12.7 |
| 64 | 1024 | 102 865 | 49 185 | 2.09 | 47.8 | 20.7 |
| 128 | escalar | 16 909 200 | 19 012 034 | 0.89 | 1.0 | 1.0 |
| 128 | 128 | 4 342 673 | 2 290 708 | 1.90 | 8.3 | 3.9 |
| 128 | 256 | 2 245 521 | 1 253 284 | 1.79 | 15.2 | 7.5 |
| 128 | 512 | 1 196 945 | 968 977 | 1.24 | 19.6 | 14.1 |
| 128 | 1024 | 672 657 | 567 723 | 1.18 | 33.5 | 25.1 |

Figuras: `report/figures/e3_speedup_vl.png`, `report/figures/e3_instructions_ipc.png`.

## ¿La ganancia escala con VL?

Speedup = (reducción de instrucciones) × (IPC SVE / IPC escalar).

1. **Con VL = 128 ya hay 8×**, más que los 4 carriles: además de procesar 4
   elementos por instrucción, el bucle vectorial elimina el control por
   elemento (≈ 3.9× menos instrucciones) y el IPC sube de 0.89 a 1.9 porque las
   cargas, el `fmla` y el almacenamiento de iteraciones distintas son
   independientes y O3 los solapa.
2. **La reducción de instrucciones sí escala con VL** (3.9 → 7.5 → 14.1 → 25.1
   para N = 128). No es exactamente 2× por paso porque las instrucciones fuera
   del bucle interno (bucles i y k, carga de `a[i][k]`) no se vectorizan y pesan
   cada vez más (Amdahl dentro del núcleo).
3. **El IPC cae con VL grande cuando los datos no caben en L1.** Con N = 64,
   A, B y C ocupan 48 kB y caben en la L1D de 64 kB: casi no hay fallos y el
   speedup se mantiene cerca del ideal (47.8× con VL = 1024). Con N = 128 ocupan
   192 kB: B se vuelve a traer de L2 para cada fila i. El tráfico L2 → L1 no
   disminuye con VL (son las mismas líneas), mientras el cómputo sí, así que el
   núcleo queda limitado por memoria: los ciclos con la caché bloqueada por falta
   de MSHR suben de 36 k (VL 128) a 155 k (VL 1024) y con VL = 1024 aparecen
   63 801 eventos de LSQ lleno (0 con VL ≤ 512). Cada `ld1w` de 1024 bits ocupa
   2 líneas de caché de 64 B.

**Conclusión.** La ganancia escala casi proporcionalmente con VL mientras el
conjunto de trabajo cabe en L1; con N = 128 escala de forma sublineal (eficiencia
por carril de 2.1 con VL 128 a 1.05 con VL 1024) porque el límite pasa a ser el
ancho de banda L1/L2. Para N más grandes haría falta bloqueo (tiling) para que
la VL larga siga rindiendo; esto se usa en el análisis de E6.
