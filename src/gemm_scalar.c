/* GEMM escalar (E1, E2, E3). Uso: gemm_scalar N */
#include "gemm_common.h"

/* Orden i-k-j: las filas de B y C se recorren consecutivamente. */
__attribute__((noinline, optimize("no-tree-vectorize")))
static void gemm_scalar(const float *a, const float *b, float *c, size_t n)
{
    for (size_t i = 0; i < n; ++i) {
        for (size_t k = 0; k < n; ++k) {
            const float aik = a[i*n + k];
            for (size_t j = 0; j < n; ++j) {
                c[i*n + j] += aik * b[k*n + j];
            }
        }
    }
}

int main(int argc, char **argv)
{
    if (argc != 2) {
        fprintf(stderr, "Uso: %s N (1..%d)\n", argv[0], GEMM_MAX_N);
        return EXIT_FAILURE;
    }
    size_t n;
    if (!parse_size_arg(argv[1], &n))
        return EXIT_FAILURE;

    gemm_problem p;
    if (!gemm_problem_create(&p, n))
        return EXIT_FAILURE;

    roi_begin();
    gemm_scalar(p.a, p.b, p.c, p.n);
    roi_end();

    int ok = gemm_problem_check(&p);
    if (ok)
        printf("GEMM escalar N=%zu: OK\n", n);
    gemm_problem_destroy(&p);
    return ok ? EXIT_SUCCESS : EXIT_FAILURE;
}
