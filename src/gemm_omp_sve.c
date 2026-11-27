/*
 * GEMM paralelo y vectorial (E6): las filas de C se reparten entre hilos
 * OpenMP y cada fila se calcula con el núcleo SVE de gemm_kernels.h.
 * Uso: gemm_omp_sve N hilos
 */
#include "gemm_common.h"
#include "gemm_kernels.h"

#define MAX_THREADS 16

__attribute__((noinline))
static void gemm_row_sve(const float *a, const float *b, float *c, size_t n, size_t i)
{
    for (size_t k = 0; k < n; ++k)
        axpy_row_f32(a[i*n + k], &b[k*n], &c[i*n], n);
}

GEMM_DEFINE_PARALLEL_ROWS(gemm_omp_sve, gemm_row_sve)

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
    int actual = gemm_omp_sve(p.a, p.b, p.c, p.n, threads);
    roi_end();

    int ok = gemm_problem_check(&p);
    if (actual != threads) {
        fprintf(stderr, "ERROR: hilos solicitados=%d reales=%d\n", threads, actual);
        ok = 0;
    }
    if (ok) {
        size_t vl = vector_length_bits();
        if (vl)
            printf("GEMM OpenMP SVE N=%zu hilos=%d VL=%zu bits: OK\n", n, actual, vl);
        else
            printf("GEMM OpenMP SVE (ruta nativa sin SVE) N=%zu hilos=%d: OK\n", n, actual);
    }
    gemm_problem_destroy(&p);
    return gem5_finish(ok);
}
