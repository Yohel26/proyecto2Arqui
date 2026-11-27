# Resumen E6 (N = 128)

- Mejor por tiempo: `c4_w8_vl512_mesi` (costo 32, 130.2 µs, 32.210 GFLOP/s, 1.0066 GFLOP/s por unidad)
- Mejor por rendimiento/costo: `c1_w4_vl1024_mesi` (costo 10, 237.0 µs, 17.697 GFLOP/s, 1.7697 GFLOP/s por unidad)
- Mejor por tiempo con presupuesto 16: `c4_w4_vl256_mesi` (costo 16, 213.1 µs, 19.684 GFLOP/s, 1.2303 GFLOP/s por unidad)

## MESI vs. MOESI
- 4 núcleos, ancho 8, VL 512: MOESI +4.30 % de tiempo respecto a MESI
- 8 núcleos, ancho 4, VL 256: MOESI -3.36 % de tiempo respecto a MESI

## Sensibilidad N = 256
- `c4_w8_vl512_mesi`: 2391.0 µs, 14.034 GFLOP/s
- `c4_w4_vl512_mesi`: 2392.9 µs, 14.023 GFLOP/s
- `c8_w4_vl256_mesi`: 2396.3 µs, 14.003 GFLOP/s
- `c2_w8_vl1024_mesi`: 2411.4 µs, 13.915 GFLOP/s
- `c1_w8_vl1024_mesi`: 2796.9 µs, 11.997 GFLOP/s
