#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <inttypes.h>
#include <errno.h>
#include <string.h>
#include <omp.h>

#ifndef NATIVE
#include <gem5/m5ops.h>
#endif

#define CACHE_LINE 64
#define MAX_THREADS 8
#define WORDS_PER_LINE (CACHE_LINE / sizeof(uint64_t))
#define DEFAULT_ITERATIONS UINT64_C(100000)

/* Each thread updates its own counter. Volatile preserves every access. */
__attribute__((noinline))
static void increment(volatile uint64_t *counter, uint64_t iterations)
{
    for (uint64_t i = 0; i < iterations; ++i)
        ++*counter;
}

int main(int argc, char **argv)
{
    if (argc != 3 && argc != 4) {
        fprintf(stderr, "Uso: %s hilos (1..8) pad|nopad [iteraciones]\n", argv[0]);
        return EXIT_FAILURE;
    }
    char *end;
    errno = 0;
    long requested = strtol(argv[1], &end, 10);
    if (errno || end == argv[1] || *end || requested < 1 || requested > MAX_THREADS) {
        fprintf(stderr, "Numero de hilos invalido\n");
        return EXIT_FAILURE;
    }
    int threads = (int)requested;
    size_t stride;
    if (strcmp(argv[2], "pad") == 0)
        stride = WORDS_PER_LINE;
    else if (strcmp(argv[2], "nopad") == 0)
        stride = 1;
    else {
        fprintf(stderr, "Modo invalido: use pad o nopad\n");
        return EXIT_FAILURE;
    }
    uint64_t iterations = DEFAULT_ITERATIONS;
    if (argc == 4) {
        errno = 0;
        unsigned long long v = strtoull(argv[3], &end, 10);
        if (errno || argv[3][0] < '0' || argv[3][0] > '9' || *end || v == 0 || v > 1000000000ULL) {
            fprintf(stderr, "Iteraciones invalidas (1..1000000000)\n");
            return EXIT_FAILURE;
        }
        iterations = (uint64_t)v;
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
#ifndef NATIVE
            m5_reset_stats(0, 0);
#endif
        }
        #pragma omp barrier
        increment(&counters[(size_t)id * stride], iterations);
        #pragma omp barrier
        #pragma omp master
        {
#ifndef NATIVE
            m5_dump_stats(0, 0);
#endif
        }
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
#ifndef NATIVE
    /* Finish gem5 explicitly after verification, outside the measured ROI.
       Avoid SE exit_group while OpenMP workers may still be suspended. */
    fflush(stdout);
    fflush(stderr);
    if (ok)
        m5_exit(0);
    else
        m5_fail(0, 1);
#endif
    return ok ? EXIT_SUCCESS : EXIT_FAILURE;
}
