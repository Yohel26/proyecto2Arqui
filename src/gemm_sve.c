#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
#include <stddef.h>
#include <stdint.h>

#if defined(__ARM_FEATURE_SVE)
#include <arm_sve.h>
#elif !defined(NATIVE)
#error "Compilar para ARM con -march=armv8-a+sve"
#endif

#ifndef NATIVE
#include <gem5/m5ops.h>
#endif

/* Inicializacion determinista con valores exactamente representables. */
static void init(float *a, float *b, float *c, size_t elements)
{
    for (size_t i = 0; i < elements; ++i) {
        a[i] = (float)((int)(i % 17) - 8) / 8.0f;
        b[i] = (float)((int)(i % 13) - 6) / 8.0f;
        c[i] = 0.0f;
    }
}

/* Mismo orden i-k-j que GEMM escalar; vectorizar las columnas. */
__attribute__((noinline))
static void gemm_sve(const float *a, const float *b, float *c, size_t n)
{
    for (size_t i = 0; i < n; ++i) {
        for (size_t k = 0; k < n; ++k) {
            const float aik = a[i*n + k];
#if defined(__ARM_FEATURE_SVE)
            for (size_t j = 0; j < n; j += svcntw()) {
                svbool_t pg = svwhilelt_b32((uint64_t)j, (uint64_t)n);
                svfloat32_t bv = svld1_f32(pg, &b[k*n + j]);
                svfloat32_t cv = svld1_f32(pg, &c[i*n + j]);
                cv = svmla_n_f32_m(pg, cv, bv, aik);
                svst1_f32(pg, &c[i*n + j], cv);
            }
#else
            /* Referencia portable para pruebas nativas sin SVE. */
            for (size_t j = 0; j < n; ++j)
                c[i*n + j] += aik * b[k*n + j];
#endif
        }
    }
}

/* Referencia independiente: producto punto por cada elemento de C. */
static int check(const float *a, const float *b, const float *c, size_t n)
{
    for (size_t i = 0; i < n; ++i) {
        for (size_t j = 0; j < n; ++j) {
            double ref = 0.0;
            for (size_t k = 0; k < n; ++k)
                ref += (double)a[i*n + k] * (double)b[k*n + j];
            if ((double)c[i*n + j] != ref) {
                fprintf(stderr, "ERROR C[%zu,%zu]: obtenido=%g esperado=%g\n",
                        i, j, (double)c[i*n + j], ref);
                return 0;
            }
        }
    }
    return 1;
}

int main(int argc, char **argv)
{
    if (argc != 2) {
        fprintf(stderr, "Uso: %s N (1..4096)\n", argv[0]);
        return EXIT_FAILURE;
    }
    char *end;
    errno = 0;
    long value = strtol(argv[1], &end, 10);
    if (errno || end == argv[1] || *end != '\0' || value < 1 || value > 4096) {
        fprintf(stderr, "N invalido (1..4096)\n");
        return EXIT_FAILURE;
    }
    size_t n = (size_t)value;
    size_t elements = n*n;
    float *a = malloc(elements * sizeof *a);
    float *b = malloc(elements * sizeof *b);
    float *c = malloc(elements * sizeof *c);
    if (!a || !b || !c) {
        fprintf(stderr, "Error al reservar memoria\n");
        free(a); free(b); free(c);
        return EXIT_FAILURE;
    }

    init(a, b, c, elements);

#ifndef NATIVE
    m5_reset_stats(0, 0);
#endif
    gemm_sve(a, b, c, n);
#ifndef NATIVE
    m5_dump_stats(0, 0);
#endif

    int ok = check(a, b, c, n);
    if (ok) {
#if defined(__ARM_FEATURE_SVE)
        printf("GEMM SVE N=%zu VL=%zu bits: OK\n", n, (size_t)svcntb()*8);
#else
        printf("GEMM SVE (ruta nativa sin SVE) N=%zu: OK\n", n);
#endif
    }
    free(a); free(b); free(c);
    return ok ? EXIT_SUCCESS : EXIT_FAILURE;
}
