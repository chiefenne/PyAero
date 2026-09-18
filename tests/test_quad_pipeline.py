import sys
import unittest
from pathlib import Path

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / 'src'
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import Connect
import MeshBuilders
import QuadLayout
import QuadPipeline


class HybridQuadPipelineTests(unittest.TestCase):
    def setUp(self):
        self.main_element = (
            np.array([1.0, 0.78, 0.42, 0.0, 0.40, 0.80, 1.0], dtype=float),
            np.array([0.0, 0.05, 0.08, 0.0, -0.08, -0.05, 0.0], dtype=float),
        )
        self.airfoil_settings = MeshBuilders.AirfoilBlockSettings(
            name='block_hybrid_airfoil',
            divisions=12,
            growth=1.05,
            thickness=0.004,
        )
        self.trailing_edge_settings = MeshBuilders.TrailingEdgeBlockSettings(
            trailing_edge_divisions=3,
            thickness=0.004,
            divisions=12,
            growth=1.05,
        )
        self.tunnel_settings = MeshBuilders.TunnelBlockSettings(
            tunnel_height=3.5,
            divisions_height=40,
            smoothing_iterations=4,
            smoothing_tolerance=1.0e-5,
            elliptic_relaxation=0.45,
            protected_guide_smoothing=2,
        )
        self.wake_settings = MeshBuilders.WakeBlockSettings(
            tunnel_wake=6.0,
            divisions=60,
            growth=1.0,
            spread=0.2,
        )

    def test_metric_c_grid_layout_uses_boundary_singularities(self):
        settings = QuadPipeline.HybridQuadPipelineSettings(
            layout_strategy='metric_c_grid',
            singularity_template='auto_boundary_c',
            stage2=QuadPipeline.HybridStage2Settings(enabled=False, sweeps=0),
            stage1=QuadPipeline.HybridStage1Settings(
                enabled=False,
                algorithm='none',
                iterations=0,
            ),
        )

        plan = QuadPipeline.HybridQuadPipeline.build_layout_plan(
            self.main_element,
            settings,
            airfoil_settings=self.airfoil_settings,
            tunnel_settings=self.tunnel_settings,
            wake_settings=self.wake_settings,
            trailing_edge_settings=self.trailing_edge_settings,
        )

        self.assertEqual(plan.metadata['strategy'], 'metric_c_grid')
        self.assertEqual(plan.metadata['farfield_shape'], 'legacy_wind_tunnel')
        self.assertEqual(plan.metadata['mesh_family'], 'c_grid')
        self.assertEqual(plan.metadata['te_geometry'], 'sharp')
        self.assertEqual(plan.metadata['singularity_template'], 'auto_boundary_c')
        self.assertEqual(len(plan.block_specs), 1)
        self.assertEqual(len(plan.singularities), 4)
        self.assertEqual(len(plan.separatrices), 2)
        self.assertTrue(all(s.kind == 'boundary' for s in plan.singularities))
        self.assertEqual(plan.block_specs[0].role, 'metric_c_grid')
        roles = [s.metadata['role'] for s in plan.singularities]
        self.assertEqual(
            roles,
            ['te_upper', 'te_lower', 'wake_upper', 'wake_lower'],
        )
        np.testing.assert_allclose(
            plan.singularities[0].position,
            plan.singularities[1].position,
        )
        np.testing.assert_allclose(
            plan.singularities[2].position,
            plan.singularities[3].position,
        )
        self.assertGreater(
            float(np.max(plan.outer_boundary[:, 0])),
            float(np.max(plan.boundary_loops[0][:-1, 0])) + 5.5,
        )
        self.assertLess(
            float(np.min(plan.outer_boundary[:, 0])),
            float(np.min(plan.boundary_loops[0][:-1, 0])) - 3.0,
        )

    def test_metric_c_grid_rejects_blunt_trailing_edge(self):
        blunt = (
            np.array([1.0, 0.7, 0.2, 0.0, 0.2, 0.7, 1.0], dtype=float),
            np.array([0.03, 0.08, 0.10, 0.0, -0.10, -0.08, -0.03], dtype=float),
        )

        with self.assertRaises(ValueError):
            QuadLayout.QuadLayoutGenerator.generate_metric_c_grid(
                blunt,
                tunnel_height=3.5,
                wake_length=6.0,
                surface_points=len(blunt[0]),
                normal_divisions=12,
                first_layer_thickness=0.004,
                connector_layers=40,
                trailing_edge_divisions=3,
            )

    def test_metric_pipeline_stage4_builds_c_grid_block(self):
        pipeline = QuadPipeline.HybridQuadPipeline()
        settings = QuadPipeline.HybridQuadPipelineSettings(
            layout_strategy='metric_c_grid',
            stage2=QuadPipeline.HybridStage2Settings(enabled=False, sweeps=0),
            stage1=QuadPipeline.HybridStage1Settings(
                enabled=False,
                algorithm='none',
                iterations=0,
            ),
        )

        result = pipeline.run_stage4(
            contour=self.main_element,
            settings=settings,
            airfoil_settings=self.airfoil_settings,
            tunnel_settings=self.tunnel_settings,
            wake_settings=self.wake_settings,
            trailing_edge_settings=self.trailing_edge_settings,
            engine='metric_based',
        )

        vertices, connectivity = Connect.Connect().connectAllBlocks(result.blocks)

        self.assertEqual(result.metadata['engine'], 'metric_based')
        self.assertEqual(result.metadata['layout_strategy'], 'metric_c_grid')
        self.assertEqual(result.metadata['stage4']['block_count'], 1)
        self.assertEqual(result.metadata['stage4']['singularity_count'], 4)
        self.assertFalse(result.metadata['stage2']['applied'])
        self.assertFalse(result.metadata['stage1']['applied'])
        self.assertEqual(len(result.blocks), 1)
        self.assertGreater(len(vertices), 0)
        self.assertGreater(len(connectivity), 0)


if __name__ == '__main__':
    unittest.main()
