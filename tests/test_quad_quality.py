import sys
import unittest
from pathlib import Path

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / 'src'
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import QuadQuality


class QuadQualityTests(unittest.TestCase):
    def test_k2inf_is_one_for_unit_square(self):
        report = QuadQuality.QuadQualityEvaluator.evaluate(
            vertices=[
                (0.0, 0.0),
                (1.0, 0.0),
                (1.0, 1.0),
                (0.0, 1.0),
            ],
            connectivity=[(0, 1, 2, 3)],
        )

        self.assertEqual(report.criterion, 'k2inf')
        self.assertAlmostEqual(report.values[0], 1.0)
        self.assertAlmostEqual(report.signed_areas[0], 1.0)
        self.assertFalse(report.has_inverted_cells)

    def test_k2inf_penalizes_a_sheared_quad(self):
        square = QuadQuality.QuadQualityEvaluator.evaluate(
            vertices=[
                (0.0, 0.0),
                (1.0, 0.0),
                (1.0, 1.0),
                (0.0, 1.0),
            ],
            connectivity=[(0, 1, 2, 3)],
        )
        sheared = QuadQuality.QuadQualityEvaluator.evaluate(
            vertices=[
                (0.0, 0.0),
                (1.0, 0.0),
                (1.4, 1.0),
                (0.4, 1.0),
            ],
            connectivity=[(0, 1, 2, 3)],
        )

        self.assertGreater(sheared.values[0], square.values[0])
        self.assertGreater(sheared.minimum_signed_area, 0.0)

    def test_report_flags_inverted_cells_from_signed_area(self):
        report = QuadQuality.QuadQualityEvaluator.evaluate(
            vertices=[
                (0.0, 0.0),
                (0.0, 1.0),
                (1.0, 1.0),
                (1.0, 0.0),
            ],
            connectivity=[(0, 1, 2, 3)],
        )

        self.assertTrue(report.has_inverted_cells)
        self.assertLess(report.minimum_signed_area, 0.0)
        np.testing.assert_array_equal(
            report.inverted_cell_indices,
            np.array([0], dtype=int),
        )

    def test_evaluate_rejects_non_quad_connectivity(self):
        with self.assertRaisesRegex(ValueError, 'M x 4'):
            QuadQuality.QuadQualityEvaluator.evaluate(
                vertices=[
                    (0.0, 0.0),
                    (1.0, 0.0),
                    (0.0, 1.0),
                ],
                connectivity=[(0, 1, 2)],
            )


if __name__ == '__main__':
    unittest.main()
