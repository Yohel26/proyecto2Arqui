#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
#include <stddef.h>
#include <omp.h>

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

/* Cada hilo calcula filas distintas de C; no necesita atomicos. */
__attribute__((noinline, optimize("no-tree-vectorize")))
static void gemm_row(const float *a, const float *b, float *c,
                     size_t n, size_t i)
{
    for (size_t k = 0; k < n; ++k) {
        const float aik = a[i*n + k];
        for (size_t j = 0; j < n; ++j)
            c[i*n + j] += aik * b[k*n + j];
    }
}

static int gemm_omp(const float *a, const float *b, float *c,
                    size_t n, int threads)
{
    int actual = 0;
    #pragma omp parallel num_threads(threads) default(none) shared(a,b,c,n,actual)
    {
        if (omp_get_thread_num() == 0)
            actual = omp_get_num_threads();
        #pragma omp for schedule(static)
        for (size_t i = 0; i < n; ++i)
            gemm_row(a, b, c, n, i);
    }
    return actual;
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
    if (argc != 3) {
        fprintf(stderr, "Uso: %s N (1..4096) hilos (1..8)\n", argv[0]);
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
    errno = 0;
    long requested = strtol(argv[2], &end, 10);
    if (errno || end == argv[2] || *end != '\0' || requested < 1 || requested > 8) {
        fprintf(stderr, "Numero de hilos invalido (1..8)\n");
        return EXIT_FAILURE;
    }
    int threads = (int)requested;
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
    omp_set_dynamic(0);

#ifndef NATIVE
    m5_reset_stats(0, 0);
#endif
    int actual = gemm_omp(a, b, c, n, threads);
#ifndef NATIVE
    m5_dump_stats(0, 0);
#endif

    int ok = check(a, b, c, n);
    if (actual != threads) {
        fprintf(stderr, "ERROR: hilos solicitados=%d reales=%d\n", threads, actual);
        ok = 0;
    }
    if (ok)
        printf("GEMM OpenMP N=%zu hilos=%d: OK\n", n, actual);
    free(a); free(b); free(c);
#if !defined(NATIVE) && defined(GEM5_EXPLICIT_EXIT)
    /* E5: avoid the TimingSimpleCPU exit_group assertion outside the ROI. */
    fflush(stdout);
    fflush(stderr);
    if (ok)
        m5_exit(0);
    else
        m5_fail(0, 1);
#endif
    return ok ? EXIT_SUCCESS : EXIT_FAILURE;
}
