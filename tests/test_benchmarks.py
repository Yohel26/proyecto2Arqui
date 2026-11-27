"""Pruebas nativas de los benchmarks en C (compilados con -DNATIVE para el host).

Verifican el resultado de GEMM contra la referencia interna y la validación de
argumentos. Las rutas SVE reales se validan en gem5 (scripts/run_e3.sh SMOKE=1).
"""

from __future__ import annotations

import unittest

from support import build_native, run

SIZES = ("1", "7", "16", "33")
BAD_SIZES = ("0", "-3", "abc", "12x", "4097", "")


class SingleThreadGemmTests(unittest.TestCase):
    CASES = {
        "gemm_scalar": "GEMM escalar N={n}: OK",
        "gemm_sve": "GEMM SVE (ruta nativa sin SVE) N={n}: OK",
    }

    def test_valid_sizes_produce_correct_result(self):
        for source, message in self.CASES.items():
            binary = build_native(source)
            for n in SIZES:
                with self.subTest(source=source, n=n):
                    result = run(binary, n)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout.strip(), message.format(n=n))

    def test_invalid_size_is_rejected(self):
        for source in self.CASES:
            binary = build_native(source)
            for n in BAD_SIZES:
                with self.subTest(source=source, n=n):
                    self.assertNotEqual(run(binary, n).returncode, 0)

    def test_wrong_argument_count_is_rejected(self):
        for source in self.CASES:
            binary = build_native(source)
            with self.subTest(source=source):
                self.assertNotEqual(run(binary).returncode, 0)
                self.assertNotEqual(run(binary, "16", "2").returncode, 0)


class ParallelGemmTests(unittest.TestCase):
    CASES = {
        "gemm_omp": ("GEMM OpenMP N={n} hilos={t}: OK", 8),
        "gemm_omp_sve": ("GEMM OpenMP SVE (ruta nativa sin SVE) N={n} hilos={t}: OK", 16),
    }

    def test_valid_sizes_and_threads_produce_correct_result(self):
        for source, (message, max_threads) in self.CASES.items():
            binary = build_native(source, openmp=True)
            for n in SIZES:
                for t in ("1", "2", "3", str(max_threads)):
                    with self.subTest(source=source, n=n, t=t):
                        result = run(binary, n, t)
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertEqual(result.stdout.strip(), message.format(n=n, t=t))

    def test_invalid_threads_are_rejected(self):
        for source, (_, max_threads) in self.CASES.items():
            binary = build_native(source, openmp=True)
            for t in ("0", str(max_threads + 1), "x", ""):
                with self.subTest(source=source, t=t):
                    self.assertNotEqual(run(binary, "16", t).returncode, 0)

    def test_invalid_size_is_rejected(self):
        for source in self.CASES:
            binary = build_native(source, openmp=True)
            for n in BAD_SIZES:
                with self.subTest(source=source, n=n):
                    self.assertNotEqual(run(binary, n, "2").returncode, 0)

    def test_wrong_argument_count_is_rejected(self):
        for source in self.CASES:
            binary = build_native(source, openmp=True)
            with self.subTest(source=source):
                self.assertNotEqual(run(binary, "16").returncode, 0)


class FalseSharingTests(unittest.TestCase):
    def setUp(self):
        self.binary = build_native("false_sharing", openmp=True)

    def test_counts_are_correct_in_both_modes(self):
        for mode in ("pad", "nopad"):
            for t in ("1", "4", "8"):
                with self.subTest(mode=mode, t=t):
                    result = run(self.binary, t, mode, "1000")
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(
                        result.stdout.strip(),
                        f"False sharing hilos={t} modo={mode} iteraciones=1000: OK",
                    )

    def test_default_iterations(self):
        result = run(self.binary, "2", "pad")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("iteraciones=100000: OK", result.stdout)

    def test_invalid_arguments_are_rejected(self):
        for args in (("0", "pad"), ("9", "pad"), ("2", "half"), ("2", "pad", "0"),
                     ("2", "pad", "-5"), ("2", "pad", "1000000001"), ("2",)):
            with self.subTest(args=args):
                self.assertNotEqual(run(self.binary, *args).returncode, 0)


if __name__ == "__main__":
    unittest.main()
