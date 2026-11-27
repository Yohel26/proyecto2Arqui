/* Microbenchmark de falso compartido (E5). Uso: false_sharing hilos pad|nopad [iteraciones] */
#include <inttypes.h>
#include <string.h>
#include <omp.h>

#include "gemm_common.h"

#define CACHE_LINE 64
#define MAX_THREADS 8
#define WORDS_PER_LINE (CACHE_LINE / sizeof(uint64_t))
#define DEFAULT_ITERATIONS UINT64_C(100000)
#define MAX_ITERATIONS UINT64_C(1000000000)

/* Each thread updates its own counter. Volatile preserves every access. */
__attribute__((noinline))
static void increment(volatile uint64_t *counter, uint64_t iterations)
{
    for (uint64_t i = 0; i < iterations; ++i)
        ++*counter;
}

/* Palabras entre contadores: 1 los empaqueta en una línea, WORDS_PER_LINE los separa. */
static int parse_mode_arg(const char *text, size_t *stride)
{
    if (strcmp(text, "pad") == 0)
        *stride = WORDS_PER_LINE;
    else if (strcmp(text, "nopad") == 0)
        *stride = 1;
    else {
        fprintf(stderr, "Modo invalido: use pad o nopad\n");
        return 0;
    }
    return 1;
}

int main(int argc, char **argv)
{
    if (argc != 3 && argc != 4) {
        fprintf(stderr, "Uso: %s hilos (1..%d) pad|nopad [iteraciones]\n", argv[0], MAX_THREADS);
        return EXIT_FAILURE;
    }
    int threads;
    size_t stride;
    if (!parse_threads_arg(argv[1], MAX_THREADS, &threads) || !parse_mode_arg(argv[2], &stride))
        return EXIT_FAILURE;
    uint64_t iterations = DEFAULT_ITERATIONS;
    if (argc == 4 && !parse_u64_arg(argv[3], MAX_ITERATIONS, &iterations)) {
        fprintf(stderr, "Iteraciones invalidas (1..%" PRIu64 ")\n", MAX_ITERATIONS);
        return EXIT_FAILURE;
    }

    /* All eight packed counters fit in one 64-byte cache line.
       In padded mode, each counter starts in a separate cache line. */
    _Alignas(CACHE_LINE) volatile uint64_t counters[MAX_THREADS * WORDS_PER_LINE] = {0};
    int actual = 0;
    omp_set_dynamic(0);

    #pragma omp parallel num_threads(threads) default(none) shared(counters,stride,iterations,actual)
    {
        int id = omp_get_thread_num();
        #pragma omp barrier
        #pragma omp master
        {
            actual = omp_get_num_threads();
            roi_begin();
        }
        #pragma omp barrier
        increment(&counters[(size_t)id * stride], iterations);
        #pragma omp barrier
        #pragma omp master
        roi_end();
    }

    int ok = actual == threads;
    if (!ok)
        fprintf(stderr, "ERROR: hilos solicitados=%d reales=%d\n", threads, actual);
    for (int i = 0; i < threads; ++i) {
        uint64_t value = counters[(size_t)i * stride];
        if (value != iterations) {
            fprintf(stderr, "ERROR contador %d: obtenido=%" PRIu64 " esperado=%" PRIu64 "\n",
                    i, value, iterations);
            ok = 0;
        }
    }
    if (ok)
        printf("False sharing hilos=%d modo=%s iteraciones=%" PRIu64 ": OK\n",
               actual, argv[2], iterations);
    /* Finish gem5 explicitly after verification, outside the measured ROI.
       Avoid SE exit_group while OpenMP workers may still be suspended. */
    return gem5_finish(ok);
}
