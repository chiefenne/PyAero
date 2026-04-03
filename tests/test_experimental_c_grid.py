import sys
import unittest
from pathlib import Path

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / 'src'
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import Connect
from ExperimentalCGrid import (
    ExperimentalCGridGenerator,
    ExperimentalCGridSettings,
)
import Mesh
import MeshBuilders


class ExperimentalCGridTests(unittest.TestCase):
    def setUp(self):
        self.generator = ExperimentalCGridGenerator()
        self.settings = ExperimentalCGridSettings(
            normal_divisions=24,
            wake_points=18,
            initial_smoothing_iterations=8,
            final_smoothing_iterations=3,
        )
        self.sharp_contour = (
            np.array([1.0, 0.75, 0.35, 0.0, 0.35, 0.75, 1.0], dtype=float),
            np.array([0.0, 0.05, 0.08, 0.0, -0.08, -0.05, 0.0], dtype=float),
        )
        self.blunt_contour = (
            np.array([1.0, 0.7, 0.2, 0.0, 0.2, 0.7, 1.0], dtype=float),
            np.array([0.03, 0.08, 0.10, 0.0, -0.10, -0.08, -0.03], dtype=float),
        )

    @staticmethod
    def _minimum_cell_area(vertices, connectivity):
        points = np.asarray(vertices, dtype=float)
        cells = np.asarray(connectivity, dtype=int)
        areas = []
        for cell in cells:
            polygon = points[cell]
            x_values = polygon[:, 0]
            y_values = polygon[:, 1]
            areas.append(
                0.5 * abs(
                    np.dot(x_values, np.roll(y_values, -1)) -
                    np.dot(y_values, np.roll(x_values, -1))
                )
            )
        return min(areas) if areas else 0.0

    def test_build_block_creates_structured_experimental_c_grid(self):
        block = self.generator.build_block(
            self.sharp_contour,
            radius=3.5,
            wake_length=7.0,
            settings=self.settings,
        )

        u_divisions, v_divisions = block.getDivUV()
        self.assertGreater(u_divisions, 0)
        self.assertEqual(v_divisions, self.settings.normal_divisions)

        inner_boundary = np.asarray(block.getULines()[0], dtype=float)
        self.assertTrue(np.allclose(inner_boundary[0], inner_boundary[-1]))

        connector = Connect.Connect()
        vertices, connectivity = connector.connectAllBlocks([block])
        self.assertGreater(len(vertices), 0)
        self.assertGreater(len(connectivity), 0)
        self.assertGreater(self._minimum_cell_area(vertices, connectivity), 1.0e-10)

        topology = Mesh.MeshTopology.from_mesh(vertices, connectivity)
        self.assertGreater(len(topology.boundary_tags['airfoil']), 0)
        self.assertGreater(len(topology.boundary_tags['inlet']), 0)
        self.assertGreater(len(topology.boundary_tags['outlet']), 0)

    def test_build_block_rejects_blunt_trailing_edge(self):
        with self.assertRaisesRegex(ValueError, 'sharp trailing edge'):
            self.generator.build_block(
                self.blunt_contour,
                radius=3.5,
                wake_length=7.0,
                settings=self.settings,
            )

    def test_local_te_smoothing_iterations_are_not_capped(self):
        settings = ExperimentalCGridSettings(local_te_smoothing_iterations=25)
        self.assertEqual(settings.local_te_smoothing_iterations, 25)

    def test_build_blunt_blocks_creates_connected_mesh(self):
        trailing_edge_settings = MeshBuilders.TrailingEdgeBlockSettings(
            name='block_experimental_te',
            trailing_edge_divisions=3,
            thickness=0.03,
            divisions=8,
            growth=1.05,
        )

        blocks = self.generator.build_blunt_blocks(
            self.blunt_contour,
            radius=3.5,
            wake_length=7.0,
            settings=self.settings,
            trailing_edge_settings=trailing_edge_settings,
        )

        self.assertEqual(len(blocks), 3)

        connector = Connect.Connect()
        vertices, connectivity = connector.connectAllBlocks(blocks)
        self.assertGreater(len(vertices), 0)
        self.assertGreater(len(connectivity), 0)
        self.assertGreater(self._minimum_cell_area(vertices, connectivity), 1.0e-10)

        topology = Mesh.MeshTopology.from_mesh(vertices, connectivity)
        self.assertGreater(len(topology.boundary_tags['airfoil']), 0)
        self.assertGreater(len(topology.boundary_tags['inlet']), 0)
        self.assertGreater(len(topology.boundary_tags['outlet']), 0)


if __name__ == '__main__':
    unittest.main()
