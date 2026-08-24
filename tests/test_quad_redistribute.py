import sys
import unittest
from pathlib import Path

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / 'src'
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import BlockMesh
import QuadLayout
import QuadMonitor
import QuadRedistribute


class QuadRedistributionTests(unittest.TestCase):
    def test_metric_density_matches_isotropic_size_field(self):
        metric = QuadMonitor.LineMetricField.from_isotropic_sizes(
            [2.0, 1.0, 0.5]
        )
        density = metric.density_values()

        np.testing.assert_allclose(density, np.array([0.25, 1.0, 4.0]))

    def test_monitor_weighted_redistribution_clusters_points(self):
        line = np.column_stack((
            np.linspace(0.0, 1.0, 5),
            np.zeros(5, dtype=float),
        ))
        redistributed = QuadRedistribute.redistribute_polyline(
            line,
            monitor=[4.0, 4.0, 1.0, 1.0, 1.0],
        )

        x_values = redistributed[:, 0]
        self.assertAlmostEqual(x_values[0], 0.0)
        self.assertAlmostEqual(x_values[-1], 1.0)
        self.assertLess(x_values[1] - x_values[0], x_values[-1] - x_values[-2])

    def test_metric_weighted_redistribution_clusters_points(self):
        line = np.column_stack((
            np.linspace(0.0, 1.0, 5),
            np.zeros(5, dtype=float),
        ))
        metric = QuadMonitor.LineMetricField.from_isotropic_sizes(
            [0.5, 0.5, 1.0, 1.0, 1.0]
        )
        redistributed = QuadRedistribute.redistribute_polyline(
            line,
            metric=metric,
        )

        x_values = redistributed[:, 0]
        self.assertLess(x_values[1] - x_values[0], x_values[-1] - x_values[-2])

    def test_block_mesh_can_redistribute_u_line_with_monitor(self):
        block = BlockMesh.BlockMesh('demo')
        block.addLine([(0.0, 0.0), (0.25, 0.0), (0.5, 0.0), (0.75, 0.0), (1.0, 0.0)])
        block.addLine([(0.0, 1.0), (0.25, 1.0), (0.5, 1.0), (0.75, 1.0), (1.0, 1.0)])

        redistributed = block.redistributeLine(
            direction='u',
            number=0,
            monitor=[4.0, 4.0, 1.0, 1.0, 1.0],
        )

        x_values = np.asarray([point[0] for point in redistributed], dtype=float)
        self.assertAlmostEqual(x_values[0], 0.0)
        self.assertAlmostEqual(x_values[-1], 1.0)
        self.assertLess(x_values[1] - x_values[0], x_values[-1] - x_values[-2])

    def test_layout_stub_can_create_plan_with_singularity_metadata(self):
        singularity = QuadLayout.QuadSingularity(
            position=(0.5, 0.5),
            charge=1,
            kind='valence_3',
            metadata={'source': 'manual'},
        )
        plan = QuadLayout.QuadLayoutGenerator.create_plan(
            boundary_points=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
            singularities=[singularity],
            metadata={'layout': 'stub'},
        )

        self.assertEqual(len(plan.singularities), 1)
        self.assertEqual(plan.singularities[0].charge, 1)
        self.assertEqual(plan.metadata['layout'], 'stub')


if __name__ == '__main__':
    unittest.main()
