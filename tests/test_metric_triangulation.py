import sys
import unittest
from pathlib import Path

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / 'src'
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import MetricTriangulation
import Settings


class MetricTriangulationTests(unittest.TestCase):
    def _generate(self, example):
        settings = MetricTriangulation.MetricTriangulationSettings(
            example=example,
            width=4.0,
            height=2.0,
            hole_radius=0.35,
            hole_spacing=1.40,
            outer_resolution=72,
            hole_resolution=44,
            interior_x=22,
            interior_y=12,
        )
        return MetricTriangulation.MetricTriangulator.generate(settings)

    def _triangle_centroids(self, result):
        mesh_data = result.mesh_data
        vertices = mesh_data.vertices
        return np.asarray([
            np.mean(vertices[cell], axis=0)
            for cell in mesh_data.connectivity
        ], dtype=float)

    def test_rectangle_example_builds_triangular_mesh(self):
        result = self._generate('rectangle')

        self.assertEqual(len(result.loops), 1)
        self.assertGreater(result.mesh_data.vertex_count, 0)
        self.assertGreater(result.mesh_data.cell_count, 0)
        self.assertIn('outer', result.mesh_data.boundary_tags)
        self.assertFalse(result.warnings)
        outer_points = {
            (round(float(point[0]), 12), round(float(point[1]), 12))
            for point in result.loops[0].points[:-1]
        }
        self.assertTrue({
            (-2.0, -1.0),
            (2.0, -1.0),
            (2.0, 1.0),
            (-2.0, 1.0),
        }.issubset(outer_points))

        outer = result.loops[0].points
        for centroid in self._triangle_centroids(result):
            self.assertTrue(
                MetricTriangulation.MetricTriangulator._point_in_polygon(
                    (float(centroid[0]), float(centroid[1])),
                    outer,
                )
            )

    def test_rectangle_circle_excludes_hole(self):
        result = self._generate('rectangle_circle')

        self.assertEqual(len(result.loops), 2)
        self.assertIn('hole_1', result.mesh_data.boundary_tags)
        self.assertGreater(len(result.mesh_data.boundary_tags['hole_1']), 0)
        self.assertFalse(result.warnings)

        hole = result.loops[1].points
        for centroid in self._triangle_centroids(result):
            self.assertFalse(
                MetricTriangulation.MetricTriangulator._point_in_polygon(
                    (float(centroid[0]), float(centroid[1])),
                    hole,
                )
            )

    def test_rectangle_two_circles_tracks_both_holes(self):
        result = self._generate('rectangle_two_circles')

        self.assertEqual(len(result.loops), 3)
        self.assertIn('hole_1', result.mesh_data.boundary_tags)
        self.assertIn('hole_2', result.mesh_data.boundary_tags)
        self.assertGreater(len(result.mesh_data.boundary_tags['hole_1']), 0)
        self.assertGreater(len(result.mesh_data.boundary_tags['hole_2']), 0)
        self.assertFalse(result.warnings)

        unique_edges = set(result.mesh_data.unique_edges())
        for tag in ('outer', 'hole_1', 'hole_2'):
            for edge in result.mesh_data.boundary_tags[tag]:
                sorted_edge = tuple(sorted((int(edge[0]), int(edge[1]))))
                self.assertIn(sorted_edge, unique_edges)

    def test_default_airfoil_tunnel_uses_configured_airfoil_hole(self):
        airfoil_path = Settings.ROOT / 'data' / 'Airfoils' / 'F1K' / 'hn1033a.dat'
        settings = MetricTriangulation.MetricTriangulationSettings(
            example='default_airfoil_tunnel',
            width=4.0,
            height=2.0,
            outer_resolution=72,
            hole_resolution=44,
            interior_x=32,
            interior_y=16,
            airfoil_path=str(airfoil_path),
        )

        result = MetricTriangulation.MetricTriangulator.generate(settings)

        self.assertEqual(len(result.loops), 2)
        self.assertIn('outer', result.mesh_data.boundary_tags)
        self.assertIn('hole_1', result.mesh_data.boundary_tags)
        source_count = len(
            MetricTriangulation.MetricExampleFactory._read_airfoil_coordinates(
                airfoil_path
            )
        )
        self.assertEqual(len(result.mesh_data.boundary_tags['hole_1']), source_count)
        self.assertFalse(result.warnings)

        outer = result.loops[0].points
        hole = result.loops[1].points
        self.assertLess(np.min(outer[:, 0]), -0.49)
        self.assertAlmostEqual(np.max(outer[:, 0]), 3.5, places=6)
        self.assertGreater(np.count_nonzero(outer[:-1, 0] < 0.49), 10)
        self.assertGreater(np.max(hole[:, 0]), 0.9)
        self.assertLess(np.min(hole[:, 0]), 0.1)
        self.assertTrue(np.max(hole[:, 0]) < np.max(outer[:, 0]))


if __name__ == '__main__':
    unittest.main()
