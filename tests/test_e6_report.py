from __future__ import annotations

import unittest

import support  # noqa: F401
from e6_plan import Design
from e6_report import best, build_table, parse_run_name, protocol_pairs, summary_markdown

DESIGNS = [
    Design(1, 8, 1024, "mesi", "a"),   # costo 12
    Design(8, 2, 128, "mesi", "b"),    # costo 16
    Design(8, 4, 256, "mesi", "c"),    # costo 32
    Design(8, 4, 256, "moesi", "d"),   # costo 32
]


def run(config: str, ticks: int) -> dict:
    return {"config": config, "simTicks": ticks, "simInsts": 1000}


ROWS = [
    run("c1_w8_vl1024_mesi_N128", 4_000_000_000),   # 4000 us
    run("c8_w2_vl128_mesi_N128", 1_000_000_000),    # 1000 us
    run("c8_w4_vl256_mesi_N128", 500_000_000),      # 500 us
    run("c8_w4_vl256_moesi_N128", 550_000_000),     # 550 us
    run("c8_w4_vl256_mesi_N256", 3_000_000_000),
]


class ParseRunNameTests(unittest.TestCase):
    def test_splits_design_and_size(self):
        self.assertEqual(parse_run_name("c8_w4_vl256_mesi_N128"), ("c8_w4_vl256_mesi", 128))

    def test_invalid_name_raises(self):
        with self.assertRaises(ValueError):
            parse_run_name("c8_w4_vl256_mesi")


class BuildTableTests(unittest.TestCase):
    def setUp(self):
        self.table = build_table(DESIGNS, ROWS)
        self.by_run = {(r["design"], r["N"]): r for r in self.table}

    def test_time_performance_and_cost_columns(self):
        r = self.by_run[("c8_w2_vl128_mesi", 128)]
        self.assertEqual(r["cost"], 16)
        self.assertEqual(r["time_us"], 1000.0)
        self.assertAlmostEqual(r["gflops"], 2 * 128**3 / 1e-3 / 1e9, places=4)
        self.assertAlmostEqual(r["gflops_per_cost"], r["gflops"] / 16, places=4)
        self.assertEqual((r["cores"], r["width"], r["vl_bits"], r["protocol"]), (8, 2, 128, "mesi"))

    def test_sorted_by_n_then_time(self):
        order = [(r["design"], r["N"]) for r in self.table]
        self.assertEqual(order[0], ("c8_w4_vl256_mesi", 128))
        self.assertEqual(order[-1], ("c8_w4_vl256_mesi", 256))

    def test_speedup_against_slowest_design_of_same_n(self):
        self.assertEqual(self.by_run[("c1_w8_vl1024_mesi", 128)]["speedup"], 1.0)
        self.assertEqual(self.by_run[("c8_w4_vl256_mesi", 128)]["speedup"], 8.0)

    def test_unknown_run_raises(self):
        with self.assertRaisesRegex(ValueError, "no está en el plan"):
            build_table(DESIGNS, ROWS + [run("c2_w2_vl128_mesi_N128", 1)])


class BestTests(unittest.TestCase):
    def setUp(self):
        self.table = build_table(DESIGNS, ROWS)

    def test_best_by_time(self):
        self.assertEqual(best(self.table, "time", n=128)["design"], "c8_w4_vl256_mesi")

    def test_best_by_performance_per_cost(self):
        # 1000 us / costo 16 supera a 500 us / costo 32 en perf/costo (empate) -> menor costo
        winner = best(self.table, "perf_cost", n=128)
        self.assertEqual(winner["design"], "c8_w2_vl128_mesi")

    def test_best_within_smaller_budget(self):
        self.assertEqual(best(self.table, "time", n=128, budget=16)["design"], "c8_w2_vl128_mesi")

    def test_no_candidate_returns_none(self):
        self.assertIsNone(best(self.table, "time", n=128, budget=10))


class SummaryTests(unittest.TestCase):
    def test_summary_names_best_designs(self):
        text = summary_markdown(build_table(DESIGNS, ROWS))
        self.assertIn("# Resumen E6 (N = 128)", text)
        self.assertIn("Mejor por tiempo: `c8_w4_vl256_mesi`", text)
        self.assertIn("presupuesto 16: `c8_w2_vl128_mesi`", text)
        self.assertIn("MOESI +10.00 %", text)
        self.assertIn("## Sensibilidad N = 256", text)

    def test_summary_falls_back_to_largest_size_without_main_n(self):
        text = summary_markdown(build_table(DESIGNS, [run("c8_w2_vl128_mesi_N16", 10_000_000)]))
        self.assertIn("# Resumen E6 (N = 16)", text)
        self.assertIn("Mejor por tiempo: `c8_w2_vl128_mesi`", text)


class ProtocolPairsTests(unittest.TestCase):
    def test_pairs_same_design_across_protocols(self):
        pairs = protocol_pairs(build_table(DESIGNS, ROWS), n=128)
        self.assertEqual(len(pairs), 1)
        mesi, moesi, delta = pairs[0]
        self.assertEqual((mesi["design"], moesi["design"]), ("c8_w4_vl256_mesi", "c8_w4_vl256_moesi"))
        self.assertAlmostEqual(delta, 10.0)  # MOESI 10 % más lento


if __name__ == "__main__":
    unittest.main()
