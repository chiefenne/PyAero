import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / 'src'
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import Settings


class WindowSettingsTests(unittest.TestCase):
    def test_parse_window_geometry_accepts_four_integers(self):
        self.assertEqual(
            Settings.parse_window_geometry('120, 80, 1800, 1200'),
            (120, 80, 1800, 1200),
        )

    def test_parse_window_geometry_rejects_invalid_length(self):
        with self.assertRaisesRegex(ValueError, 'exactly four integers'):
            Settings.parse_window_geometry('120, 80, 1800')

    def test_parse_window_geometry_rejects_non_positive_size(self):
        with self.assertRaisesRegex(ValueError, 'must be positive'):
            Settings.parse_window_geometry('120, 80, 0, 1200')

    def test_normalize_window_startup_mode_accepts_preset(self):
        self.assertEqual(
            Settings.normalize_window_startup_mode('Preset_2'),
            'preset_2',
        )

    def test_normalize_window_startup_mode_rejects_unknown_mode(self):
        with self.assertRaisesRegex(ValueError, 'must be one of'):
            Settings.normalize_window_startup_mode('fullscreen')


if __name__ == '__main__':
    unittest.main()
