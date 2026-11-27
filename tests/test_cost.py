from __future__ import annotations

import unittest

import support  # noqa: F401
from cost import BUDGET, cost, validate_design


class CostTests(unittest.TestCase):
    def test_formula_matches_spec_example(self):
        # Calculadora del enunciado: 4 núcleos, ancho 4, VL 256 -> 16 unidades
        self.assertEqual(cost(cores=4, width=4, vl_bits=256), 16)

    def test_formula_other_points(self):
        self.assertEqual(cost(cores=1, width=1, vl_bits=128), 1.5)
        self.assertEqual(cost(cores=8, width=2, vl_bits=128), 16)
        self.assertEqual(cost(cores=2, width=8, vl_bits=1024), 24)
        self.assertEqual(cost(cores=16, width=2, vl_bits=128), 32)

    def test_budget_is_32(self):
        self.assertEqual(BUDGET, 32)


class ValidateDesignTests(unittest.TestCase):
    def test_valid_design_returns_cost(self):
        self.assertEqual(validate_design(cores=4, width=8, vl_bits=512), 32)

    def test_over_budget_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "presupuesto"):
            validate_design(cores=4, width=2, vl_bits=1024)  # 36

    def test_custom_budget(self):
        self.assertEqual(validate_design(cores=8, width=2, vl_bits=128, budget=16), 16)
        with self.assertRaises(ValueError):
            validate_design(cores=8, width=2, vl_bits=256, budget=16)

    def test_invalid_width_is_rejected(self):
        for width in (0, 3, 16):
            with self.subTest(width=width), self.assertRaisesRegex(ValueError, "Ancho"):
                validate_design(cores=1, width=width, vl_bits=128)

    def test_invalid_vl_is_rejected(self):
        for vl in (0, 64, 200, 2048):
            with self.subTest(vl=vl), self.assertRaisesRegex(ValueError, "VL"):
                validate_design(cores=1, width=1, vl_bits=vl)

    def test_invalid_cores_are_rejected(self):
        for cores in (0, -1, 17):
            with self.subTest(cores=cores), self.assertRaisesRegex(ValueError, "núcleos"):
                validate_design(cores=cores, width=1, vl_bits=128)


if __name__ == "__main__":
    unittest.main()
