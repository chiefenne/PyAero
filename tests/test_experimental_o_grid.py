import sys
import unittest
from pathlib import Path

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / 'src'
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import Connect
from ExperimentalOGrid import (
    ExperimentalOGridGenerator,
    ExperimentalOGridSettings,
)
import Mesh
import MeshBuilders


class ExperimentalOGridTests(unittest.TestCase):
    def setUp(self):
        self.generator = ExperimentalOGridGenerator()
        self.sharp_contour = (
            np.array([1.0, 0.75, 0.35, 0.0, 0.35, 0.75, 1.0], dtype=float),
            np.array([0.0, 0.05, 0.08, 0.0, -0.08, -0.05, 0.0], dtype=float),
        )
        self.blunt_contour = (
            np.array([1.0, 0.7, 0.2, 0.0, 0.2, 0.7, 1.0], dtype=float),
            np.array([0.03, 0.08, 0.10, 0.0, -0.10, -0.08, -0.03], dtype=float),
        )
        self.trailing_edge_settings = MeshBuilders.TrailingEdgeBlockSettings(
            name='block_te',
            trailing_edge_divisions=3,
            thickness=0.03,
            divisions=8,
            growth=1.05,
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

    def _build_topology(self, contour, *, farfield_shape='wind_tunnel',
                        radius=3.5, wake_length=7.0):
        settings = ExperimentalOGridSettings(
            normal_divisions=20,
            farfield_shape=farfield_shape,
            initial_smoothing_iterations=6,
            final_smoothing_iterations=3,
        )
        blocks = self.generator.build_blocks(
            contour,
            radius=radius,
            wake_length=wake_length,
            settings=settings,
            trailing_edge_settings=self.trailing_edge_settings,
        )
        vertices, connectivity = Connect.Connect().connectAllBlocks(blocks)
        topology = Mesh.MeshTopology.from_mesh(vertices, connectivity)
        airfoil_edges = set(topology.boundary_tags['airfoil'])
        outer_edges = [
            edge for edge in topology.boundary_edges if edge not in airfoil_edges
        ]
        return (
            blocks,
            np.asarray(vertices, dtype=float),
            connectivity,
            topology,
            outer_edges,
        )

    def _assert_connected_mesh(self, blocks, vertices, connectivity, topology,
                               outer_edges):
        self.assertEqual(len(blocks), 4)
        self.assertGreater(len(vertices), 0)
        self.assertGreater(len(connectivity), 0)
        self.assertGreater(
            self._minimum_cell_area(vertices, connectivity),
            1.0e-10,
        )
        self.assertGreater(len(topology.boundary_tags['airfoil']), 0)

        classified_outer = sum(
            len(topology.boundary_tags[tag])
            for tag in ('inlet', 'outlet', 'top', 'bottom')
        )
        self.assertEqual(classified_outer, len(outer_edges))

    @staticmethod
    def _outer_boundary_points(vertices, outer_edges):
        vertex_ids = sorted({vertex_id for edge in outer_edges for vertex_id in edge})
        return vertices[vertex_ids]

    def test_build_blocks_creates_connected_sharp_wind_tunnel_o_grid(self):
        blocks, vertices, connectivity, topology, outer_edges = (
            self._build_topology(self.sharp_contour)
        )

        self._assert_connected_mesh(
            blocks,
            vertices,
            connectivity,
            topology,
            outer_edges,
        )
        self.assertGreater(len(topology.boundary_tags['inlet']), 0)
        self.assertGreater(len(topology.boundary_tags['outlet']), 0)
        self.assertGreater(len(topology.boundary_tags['top']), 0)
        self.assertGreater(len(topology.boundary_tags['bottom']), 0)

    def test_build_blocks_creates_connected_blunt_wind_tunnel_o_grid(self):
        blocks, vertices, connectivity, topology, outer_edges = (
            self._build_topology(self.blunt_contour)
        )

        self._assert_connected_mesh(
            blocks,
            vertices,
            connectivity,
            topology,
            outer_edges,
        )
        self.assertGreater(len(topology.boundary_tags['inlet']), 0)
        self.assertGreater(len(topology.boundary_tags['outlet']), 0)
        self.assertGreater(len(topology.boundary_tags['top']), 0)
        self.assertGreater(len(topology.boundary_tags['bottom']), 0)

    def test_build_blocks_creates_connected_circle_o_grid(self):
        blocks, vertices, connectivity, topology, outer_edges = (
            self._build_topology(
                self.sharp_contour,
                farfield_shape='circle',
            )
        )

        self._assert_connected_mesh(
            blocks,
            vertices,
            connectivity,
            topology,
            outer_edges,
        )
        self.assertGreater(len(outer_edges), 0)

    def test_wind_tunnel_outer_boundary_matches_standard_extent(self):
        _, vertices, _, _, outer_edges = self._build_topology(
            self.sharp_contour,
            farfield_shape='wind_tunnel',
            radius=3.5,
            wake_length=7.0,
        )

        outer_points = self._outer_boundary_points(vertices, outer_edges)
        self.assertAlmostEqual(np.max(outer_points[:, 0]), 8.0, places=6)
        self.assertAlmostEqual(np.max(outer_points[:, 1]), 3.5, places=6)
        self.assertAlmostEqual(np.min(outer_points[:, 1]), -3.5, places=6)
        self.assertLess(np.min(outer_points[:, 0]), -3.0)

    def test_circle_outer_boundary_uses_requested_radius(self):
        _, vertices, _, _, outer_edges = self._build_topology(
            self.sharp_contour,
            farfield_shape='circle',
            radius=3.5,
            wake_length=7.0,
        )

        outer_points = self._outer_boundary_points(vertices, outer_edges)
        radii = np.sqrt((outer_points[:, 0] - 0.5) ** 2 + outer_points[:, 1] ** 2)
        self.assertTrue(np.allclose(radii, 3.5, atol=1.0e-6))


if __name__ == '__main__':
    unittest.main()
