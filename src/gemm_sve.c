/* GEMM vectorial SVE (E3). Uso: gemm_sve N */
#include "gemm_common.h"
#include "gemm_kernels.h"

/* Mismo orden i-k-j que GEMM escalar; vectorizar las columnas. */
__attribute__((noinline))
static void gemm_sve(const float *a, const float *b, float *c, size_t n)
{
    for (size_t i = 0; i < n; ++i) {
        for (size_t k = 0; k < n; ++k)
            axpy_row_f32(a[i*n + k], &b[k*n], &c[i*n], n);
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
    gemm_sve(p.a, p.b, p.c, p.n);
    roi_end();

    int ok = gemm_problem_check(&p);
    if (ok) {
        size_t vl = vector_length_bits();
        if (vl)
            printf("GEMM SVE N=%zu VL=%zu bits: OK\n", n, vl);
        else
            printf("GEMM SVE (ruta nativa sin SVE) N=%zu: OK\n", n);
    }
    gemm_problem_destroy(&p);
    return ok ? EXIT_SUCCESS : EXIT_FAILURE;
}
