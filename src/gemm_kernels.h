/*
 * Núcleo vectorial compartido por gemm_sve.c y gemm_omp_sve.c.
 *
 * axpy_row_f32: c_row[0..n) += alpha * b_row[0..n)
 * Con SVE recorre la fila en bloques de svcntw() elementos con predicado
 * (código agnóstico a la longitud vectorial); sin SVE usa un bucle escalar
 * para las pruebas nativas.
 */
#ifndef GEMM_KERNELS_H
#define GEMM_KERNELS_H

#include <stddef.h>
#include <stdint.h>

#if defined(__ARM_FEATURE_SVE)
#include <arm_sve.h>
#elif !defined(NATIVE)
#error "Compilar para ARM con -march=armv8-a+sve"
#endif

static inline void axpy_row_f32(float alpha, const float *b_row, float *c_row, size_t n)
{
#if defined(__ARM_FEATURE_SVE)
    for (size_t j = 0; j < n; j += svcntw()) {
        svbool_t pg = svwhilelt_b32((uint64_t)j, (uint64_t)n);
        svfloat32_t bv = svld1_f32(pg, &b_row[j]);
        svfloat32_t cv = svld1_f32(pg, &c_row[j]);
        cv = svmla_n_f32_m(pg, cv, bv, alpha);
        svst1_f32(pg, &c_row[j], cv);
    }
#else
    for (size_t j = 0; j < n; ++j)
        c_row[j] += alpha * b_row[j];
#endif
}

/* Longitud vectorial en bits (0 en la ruta nativa sin SVE). */
static inline size_t vector_length_bits(void)
{
#if defined(__ARM_FEATURE_SVE)
    return (size_t)svcntb() * 8;
#else
    return 0;
#endif
}

#endif /* GEMM_KERNELS_H */
