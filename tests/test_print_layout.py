import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / 'src'
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

try:
    import PrintLayout
except ModuleNotFoundError as error:
    if error.name != 'PySide6':
        raise
    PrintLayout = None


@unittest.skipIf(PrintLayout is None, 'PySide6 is not available in the test environment.')
class PrintLayoutTests(unittest.TestCase):
    def test_normalize_frame_mode_maps_legacy_iso_to_frame(self):
        self.assertEqual(
            PrintLayout.normalize_frame_mode('ISO'),
            PrintLayout.FRAME_MODE_FRAME,
        )

    def test_normalize_paper_size_rejects_unknown_size(self):
        with self.assertRaisesRegex(ValueError, 'Paper size must be one of'):
            PrintLayout.normalize_paper_size('Letter')

    def test_build_metrics_from_contour_extracts_max_values(self):
        coordinates = (
            [1.0, 0.5, 0.0, 0.5, 1.0],
            [0.0, 0.10, 0.0, -0.02, 0.0],
        )

        metrics = PrintLayout.build_metrics_from_contour(
            coordinates,
            name='test',
            contour_label='raw contour',
        )

        self.assertAlmostEqual(metrics.chord, 1.0)
        self.assertAlmostEqual(metrics.max_thickness, 0.12, places=3)
        self.assertAlmostEqual(metrics.max_thickness_position, 0.5, places=2)
        self.assertAlmostEqual(metrics.max_camber, 0.04, places=3)
        self.assertAlmostEqual(metrics.max_camber_position, 0.5, places=2)

    def test_default_print_layout_options_prefills_airfoil_data(self):
        class DummyAirfoil:
            name = 'RG15'

        options = PrintLayout.default_print_layout_options(DummyAirfoil())

        self.assertEqual(options.paper_size, PrintLayout.PAPER_SIZE_A4)
        self.assertFalse(options.footer.show_author)
        self.assertFalse(options.footer.show_date)
        self.assertTrue(options.footer.author)
        self.assertTrue(options.footer.date_of_issue)


if __name__ == '__main__':
    unittest.main()
