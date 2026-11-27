/* GEMM paralelo escalar por filas (E4, E5). Uso: gemm_omp N hilos */
#include "gemm_common.h"

#define MAX_THREADS 8

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

GEMM_DEFINE_PARALLEL_ROWS(gemm_omp, gemm_row)

int main(int argc, char **argv)
{
    if (argc != 3) {
        fprintf(stderr, "Uso: %s N (1..%d) hilos (1..%d)\n", argv[0], GEMM_MAX_N, MAX_THREADS);
        return EXIT_FAILURE;
    }
    size_t n;
    int threads;
    if (!parse_size_arg(argv[1], &n) || !parse_threads_arg(argv[2], MAX_THREADS, &threads))
        return EXIT_FAILURE;

    gemm_problem p;
    if (!gemm_problem_create(&p, n))
        return EXIT_FAILURE;
    omp_set_dynamic(0);

    roi_begin();
    int actual = gemm_omp(p.a, p.b, p.c, p.n, threads);
    roi_end();

    int ok = gemm_problem_check(&p);
    if (actual != threads) {
        fprintf(stderr, "ERROR: hilos solicitados=%d reales=%d\n", threads, actual);
        ok = 0;
    }
    if (ok)
        printf("GEMM OpenMP N=%zu hilos=%d: OK\n", n, actual);
    gemm_problem_destroy(&p);
#if defined(GEM5_EXPLICIT_EXIT)
    /* E5: evita la aserción de exit_group de TimingSimpleCPU fuera de la ROI. */
    return gem5_finish(ok);
#else
    return ok ? EXIT_SUCCESS : EXIT_FAILURE;
#endif
}
