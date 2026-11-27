from __future__ import annotations

import unittest

import support  # noqa: F401  (agrega scripts/ al path)
from e3_report import build_table, parse_config


def row(config: str, cycles: int, insts: int) -> dict:
    return {"config": config, "numCycles": cycles, "simInsts": insts,
            "ipc_total": insts / cycles, "simSeconds": cycles * 5e-10,
            "dcache_miss_rate": 0.01, "l2_miss_rate": 0.5}


class ParseConfigTests(unittest.TestCase):
    def test_scalar(self):
        self.assertEqual(parse_config("scalar_N128"), ("scalar", 0, 128))

    def test_sve(self):
        self.assertEqual(parse_config("sve_vl256_N64"), ("sve", 256, 64))

    def test_invalid_names_raise(self):
        for name in ("sve_N64", "scalar_vl128_N64", "foo", "sve_vl100_N64", "sve_vl256"):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    parse_config(name)


class BuildTableTests(unittest.TestCase):
    def test_speedup_and_instruction_reduction_against_scalar_of_same_n(self):
        rows = [
            row("scalar_N64", 1000, 4000),
            row("sve_vl128_N64", 500, 1000),
            row("sve_vl512_N64", 250, 250),
            row("scalar_N128", 8000, 32000),
            row("sve_vl128_N128", 2000, 8000),
        ]
        table = {r["config"]: r for r in build_table(rows)}
        self.assertEqual(table["scalar_N64"]["speedup"], 1.0)
        self.assertEqual(table["sve_vl128_N64"]["speedup"], 2.0)
        self.assertEqual(table["sve_vl512_N64"]["speedup"], 4.0)
        self.assertEqual(table["sve_vl512_N64"]["inst_reduction"], 16.0)
        self.assertEqual(table["sve_vl128_N128"]["speedup"], 4.0)
        self.assertEqual(table["sve_vl128_N128"]["vl_bits"], 128)
        self.assertEqual(table["sve_vl128_N128"]["N"], 128)

    def test_rows_are_sorted_by_n_then_variant_then_vl(self):
        rows = [row("sve_vl512_N64", 1, 1), row("scalar_N128", 1, 1),
                row("sve_vl128_N64", 1, 1), row("scalar_N64", 1, 1)]
        order = [r["config"] for r in build_table(rows)]
        self.assertEqual(order, ["scalar_N64", "sve_vl128_N64", "sve_vl512_N64", "scalar_N128"])

    def test_missing_scalar_baseline_raises(self):
        with self.assertRaises(ValueError):
            build_table([row("sve_vl128_N64", 1, 1)])


if __name__ == "__main__":
    unittest.main()
