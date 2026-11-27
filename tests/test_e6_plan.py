from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import support
from e6_plan import Design, load_plan

HEADER = "cores,width,vl_bits,protocol,rationale\n"


def write_plan(body: str) -> Path:
    tmp = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8")
    tmp.write(HEADER + body)
    tmp.close()
    return Path(tmp.name)


SIX = "".join(f"{c},2,128,mesi,r{c}\n" for c in (1, 2, 3, 4, 5, 6))


class LoadPlanTests(unittest.TestCase):
    def test_designs_get_name_and_cost(self):
        designs = load_plan(write_plan(SIX))
        self.assertEqual(len(designs), 6)
        self.assertEqual(designs[3], Design(cores=4, width=2, vl_bits=128, protocol="mesi",
                                            rationale="r4"))
        self.assertEqual(designs[3].name, "c4_w2_vl128_mesi")
        self.assertEqual(designs[3].cost, 8)

    def test_protocol_is_normalized(self):
        designs = load_plan(write_plan(SIX.replace("1,2,128,mesi", "1,2,128,MOESI")))
        self.assertEqual(designs[0].protocol, "moesi")

    def test_over_budget_design_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "presupuesto"):
            load_plan(write_plan(SIX + "4,2,1024,mesi,caro\n"))

    def test_fewer_than_minimum_designs_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "al menos 6"):
            load_plan(write_plan("1,2,128,mesi,x\n"))

    def test_minimum_can_be_relaxed(self):
        self.assertEqual(len(load_plan(write_plan("1,2,128,mesi,x\n"), min_designs=1)), 1)

    def test_duplicate_design_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "repetido"):
            load_plan(write_plan(SIX + "1,2,128,mesi,otra\n"))

    def test_unknown_protocol_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Protocolo"):
            load_plan(write_plan(SIX + "1,2,128,msi,x\n"))

    def test_missing_rationale_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "justificación"):
            load_plan(write_plan(SIX + "7,1,128,mesi,\n"))

    def test_repository_plan_is_valid(self):
        designs = load_plan(support.ROOT / "configs" / "e6.csv")
        self.assertGreaterEqual(len(designs), 6)
        self.assertTrue(all(d.cost <= 32 for d in designs))


if __name__ == "__main__":
    unittest.main()
