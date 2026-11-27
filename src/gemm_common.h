/*
 * Infraestructura común de los benchmarks: lectura de argumentos, región de
 * interés (ROI), problema GEMM (reserva, inicialización, verificación) y
 * cierre explícito de gem5. Cada benchmark solo define su núcleo de cómputo.
 *
 * Compilar con -DNATIVE para ejecutar en el host sin gem5 (pruebas).
 */
#ifndef GEMM_COMMON_H
#define GEMM_COMMON_H

#include <errno.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#ifndef NATIVE
#include <gem5/m5ops.h>
#endif

#define GEMM_MAX_N 4096

/* ------------------------------------------------------------------ */
/* Argumentos                                                          */
/* ------------------------------------------------------------------ */

/* Entero decimal en [min, max]; devuelve 1 si es válido. */
static inline int parse_long_arg(const char *text, long min, long max, long *out)
{
    char *end;
    errno = 0;
    long value = strtol(text, &end, 10);
    if (errno || end == text || *end != '\0' || value < min || value > max)
        return 0;
    *out = value;
    return 1;
}

/* Entero sin signo en [1, max]; rechaza signos y espacios iniciales. */
static inline int parse_u64_arg(const char *text, uint64_t max, uint64_t *out)
{
    char *end;
    errno = 0;
    if (text[0] < '0' || text[0] > '9')
        return 0;
    unsigned long long value = strtoull(text, &end, 10);
    if (errno || *end != '\0' || value == 0 || value > max)
        return 0;
    *out = (uint64_t)value;
    return 1;
}

static inline int parse_size_arg(const char *text, size_t *n)
{
    long value;
    if (!parse_long_arg(text, 1, GEMM_MAX_N, &value)) {
        fprintf(stderr, "N invalido (1..%d)\n", GEMM_MAX_N);
        return 0;
    }
    *n = (size_t)value;
    return 1;
}

static inline int parse_threads_arg(const char *text, int max_threads, int *threads)
{
    long value;
    if (!parse_long_arg(text, 1, max_threads, &value)) {
        fprintf(stderr, "Numero de hilos invalido (1..%d)\n", max_threads);
        return 0;
    }
    *threads = (int)value;
    return 1;
}

/* ------------------------------------------------------------------ */
/* Región de interés y fin de la simulación                            */
/* ------------------------------------------------------------------ */

static inline void roi_begin(void)
{
#ifndef NATIVE
    m5_reset_stats(0, 0);
#endif
}

static inline void roi_end(void)
{
#ifndef NATIVE
    m5_dump_stats(0, 0);
#endif
}

/* Termina gem5 con m5_exit/m5_fail fuera de la ROI. Evita el exit_group de
   modo SE mientras hay hilos OpenMP suspendidos. En nativo solo devuelve. */
static inline int gem5_finish(int ok)
{
    fflush(stdout);
    fflush(stderr);
#ifndef NATIVE
    if (ok)
        m5_exit(0);
    else
        m5_fail(0, 1);
#endif
    return ok ? EXIT_SUCCESS : EXIT_FAILURE;
}

/* ------------------------------------------------------------------ */
/* Problema GEMM: C = A x B, matrices N x N en orden por filas          */
/* ------------------------------------------------------------------ */

typedef struct {
    size_t n;
    float *a;
    float *b;
    float *c;
} gemm_problem;

static inline void gemm_problem_destroy(gemm_problem *p)
{
    free(p->a);
    free(p->b);
    free(p->c);
    p->a = p->b = p->c = NULL;
}

/* Inicialización determinista con valores exactamente representables. */
static inline void gemm_problem_init(gemm_problem *p)
{
    size_t elements = p->n * p->n;
    for (size_t i = 0; i < elements; ++i) {
        p->a[i] = (float)((int)(i % 17) - 8) / 8.0f;
        p->b[i] = (float)((int)(i % 13) - 6) / 8.0f;
        p->c[i] = 0.0f;
    }
}

/* Reserva e inicializa; devuelve 1 si tuvo éxito. */
static inline int gemm_problem_create(gemm_problem *p, size_t n)
{
    size_t elements = n * n;
    p->n = n;
    p->a = malloc(elements * sizeof *p->a);
    p->b = malloc(elements * sizeof *p->b);
    p->c = malloc(elements * sizeof *p->c);
    if (!p->a || !p->b || !p->c) {
        fprintf(stderr, "Error al reservar memoria\n");
        gemm_problem_destroy(p);
        return 0;
    }
    gemm_problem_init(p);
    return 1;
}

/* Referencia independiente: producto punto en doble precisión por elemento. */
static inline int gemm_problem_check(const gemm_problem *p)
{
    const size_t n = p->n;
    for (size_t i = 0; i < n; ++i) {
        for (size_t j = 0; j < n; ++j) {
            double ref = 0.0;
            for (size_t k = 0; k < n; ++k)
                ref += (double)p->a[i*n + k] * (double)p->b[k*n + j];
            if ((double)p->c[i*n + j] != ref) {
                fprintf(stderr, "ERROR C[%zu,%zu]: obtenido=%g esperado=%g\n",
                        i, j, (double)p->c[i*n + j], ref);
                return 0;
            }
        }
    }
    return 1;
}

/* ------------------------------------------------------------------ */
/* GEMM paralelo por filas (OpenMP)                                    */
/* ------------------------------------------------------------------ */

#ifdef _OPENMP
#include <omp.h>

/* Define `name(a, b, c, n, threads)`: reparte las filas de C entre los hilos
   con schedule(static) y llama a row_fn(a, b, c, n, i) por fila. Devuelve el
   número real de hilos. Es una macro para que la llamada al núcleo sea
   directa y no por puntero dentro de la ROI. */
#define GEMM_DEFINE_PARALLEL_ROWS(name, row_fn)                                \
    static int name(const float *a, const float *b, float *c,                 \
                    size_t n, int threads)                                    \
    {                                                                         \
        int actual = 0;                                                       \
        _Pragma("omp parallel num_threads(threads) default(none) shared(a,b,c,n,actual)") \
        {                                                                     \
            if (omp_get_thread_num() == 0)                                    \
                actual = omp_get_num_threads();                               \
            _Pragma("omp for schedule(static)")                               \
            for (size_t i = 0; i < n; ++i)                                    \
                row_fn(a, b, c, n, i);                                        \
        }                                                                     \
        return actual;                                                        \
    }
#endif /* _OPENMP */

#endif /* GEMM_COMMON_H */
