import sys
import unittest
from pathlib import Path

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / 'src'
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import BlockMesh
import Connect
import Domain
import Mesh
import MeshBuilders
import QuadLayout
import QuadPipeline


class HybridQuadPipelineTests(unittest.TestCase):
    def setUp(self):
        self.main_element = (
            np.array([1.0, 0.78, 0.42, 0.0, 0.40, 0.80, 1.0], dtype=float),
            np.array([0.0, 0.05, 0.08, 0.0, -0.08, -0.05, 0.0], dtype=float),
        )
        self.flap_element = (
            np.array([1.55, 1.38, 1.08, 0.92, 1.10, 1.40, 1.55], dtype=float),
            np.array([-0.08, -0.02, 0.00, -0.04, -0.12, -0.11, -0.08], dtype=float),
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

    @staticmethod
    def _make_demo_block():
        block = BlockMesh.BlockMesh('demo')
        block.addLine([
            (0.0, 0.0),
            (0.20, 0.00),
            (0.45, 0.00),
            (0.75, 0.00),
            (1.0, 0.0),
        ])
        block.addLine([
            (0.0, 0.35),
            (0.18, 0.42),
            (0.43, 0.46),
            (0.76, 0.41),
            (1.0, 0.35),
        ])
        block.addLine([
            (0.0, 0.70),
            (0.16, 0.84),
            (0.40, 0.92),
            (0.77, 0.81),
            (1.0, 0.70),
        ])
        block.addLine([
            (0.0, 1.0),
            (0.12, 1.0),
            (0.38, 1.0),
            (0.72, 1.0),
            (1.0, 1.0),
        ])
        return block

    def test_stage2_redistributes_interior_lines_but_preserves_boundaries(self):
        block = self._make_demo_block()
        before_bottom = np.asarray(block.getULines()[0], dtype=float)
        before_top = np.asarray(block.getULines()[-1], dtype=float)
        before_interior = np.asarray(block.getULines()[1], dtype=float)

        pipeline = QuadPipeline.HybridQuadPipeline()
        stage2 = QuadPipeline.HybridStage2Settings(
            enabled=True,
            sweeps=1,
            redistribute_u=True,
            redistribute_v=False,
        )
        changed = pipeline._redistribute_block(block, stage2)

        after_bottom = np.asarray(block.getULines()[0], dtype=float)
        after_top = np.asarray(block.getULines()[-1], dtype=float)
        after_interior = np.asarray(block.getULines()[1], dtype=float)

        self.assertTrue(changed)
        np.testing.assert_allclose(after_bottom, before_bottom)
        np.testing.assert_allclose(after_top, before_top)
        self.assertFalse(np.allclose(after_interior, before_interior))

    def test_layout_plan_builds_multi_element_block_specs(self):
        settings = QuadPipeline.HybridQuadPipelineSettings(
            layout_strategy='multi_element_oc',
        )

        layout_plan = QuadPipeline.HybridQuadPipeline.build_layout_plan(
            self.main_element,
            settings,
            airfoil_settings=self.airfoil_settings,
            tunnel_settings=self.tunnel_settings,
            wake_settings=self.wake_settings,
            trailing_edge_settings=self.trailing_edge_settings,
            boundary_loops=[self.main_element, self.flap_element],
        )

        self.assertEqual(layout_plan.metadata['element_count'], 2)
        self.assertEqual(len(layout_plan.boundary_loops), 2)
        self.assertEqual(len(layout_plan.near_wall_loops), 2)
        self.assertGreaterEqual(len(layout_plan.block_specs), 13)
        protected = [spec for spec in layout_plan.block_specs if spec.protected]
        self.assertEqual(len(protected), 8)

    def test_pipeline_run_builds_connected_multi_element_mesh(self):
        pipeline = QuadPipeline.HybridQuadPipeline()
        settings = QuadPipeline.HybridQuadPipelineSettings(
            layout_strategy='multi_element_oc',
            protect_near_wall=True,
            stage2=QuadPipeline.HybridStage2Settings(enabled=True, sweeps=1),
            stage1=QuadPipeline.HybridStage1Settings(
                enabled=True,
                algorithm='elliptic',
                iterations=2,
                tolerance=1.0e-4,
                relaxation=0.4,
            ),
        )

        result = pipeline.run(
            contour=self.main_element,
            settings=settings,
            airfoil_settings=self.airfoil_settings,
            tunnel_settings=self.tunnel_settings,
            wake_settings=self.wake_settings,
            trailing_edge_settings=self.trailing_edge_settings,
            boundary_loops=[self.main_element, self.flap_element],
        )

        vertices, connectivity = Connect.Connect().connectAllBlocks(result.blocks)
        topology = Mesh.MeshTopology.from_mesh(vertices, connectivity)

        self.assertEqual(result.metadata['engine'], 'hybrid')
        self.assertEqual(result.metadata['layout_strategy'], 'multi_element_oc')
        self.assertTrue(result.metadata['stage4']['implemented'])
        self.assertTrue(result.metadata['protect_near_wall'])
        self.assertGreater(result.metadata['stage2']['blocks_skipped'], 0)
        self.assertGreater(result.metadata['stage1']['blocks_skipped'], 0)
        self.assertGreater(len(vertices), 0)
        self.assertGreater(len(connectivity), 0)
        self.assertGreater(len(topology.boundary_tags['airfoil']), 0)
        self.assertGreater(len(topology.boundary_tags['inlet']), 0)
        self.assertGreater(len(topology.boundary_tags['outlet']), 0)
        self.assertGreater(len(topology.boundary_tags['top']), 0)
        self.assertGreater(len(topology.boundary_tags['bottom']), 0)

        mesh_data = Mesh.MeshData(
            vertices=vertices,
            connectivity=connectivity,
            boundary_tags=topology.boundary_tags,
        )
        mesh = Mesh.BlockStructuredMesh(name='hybrid_multi', data=mesh_data)
        domain = Domain.DomainBuilder.from_mesh(mesh, airfoil=None)
        self.assertGreater(len(domain.outer_boundary.to_polygon()), 0)

    def test_run_stage4_keeps_stage2_and_stage1_unapplied(self):
        pipeline = QuadPipeline.HybridQuadPipeline()
        settings = QuadPipeline.HybridQuadPipelineSettings(
            layout_strategy='multi_element_oc',
            protect_near_wall=True,
        )

        result = pipeline.run_stage4(
            contour=self.main_element,
            settings=settings,
            airfoil_settings=self.airfoil_settings,
            tunnel_settings=self.tunnel_settings,
            wake_settings=self.wake_settings,
            trailing_edge_settings=self.trailing_edge_settings,
            boundary_loops=[self.main_element, self.flap_element],
            engine='hybrid_staged',
        )

        self.assertEqual(result.metadata['engine'], 'hybrid_staged')
        self.assertTrue(result.metadata['stages']['stage4_ready'])
        self.assertFalse(result.metadata['stages']['stage2_applied'])
        self.assertFalse(result.metadata['stages']['stage1_applied'])
        self.assertTrue(result.metadata['stage4']['applied'])
        self.assertFalse(result.metadata['stage2']['applied'])
        self.assertFalse(result.metadata['stage1']['applied'])

    def test_staged_metadata_tracks_stage2_then_stage1(self):
        pipeline = QuadPipeline.HybridQuadPipeline()
        settings = QuadPipeline.HybridQuadPipelineSettings(
            layout_strategy='multi_element_oc',
            protect_near_wall=True,
            stage2=QuadPipeline.HybridStage2Settings(
                enabled=True,
                sweeps=1,
            ),
            stage1=QuadPipeline.HybridStage1Settings(
                enabled=True,
                algorithm='simple',
                iterations=2,
            ),
        )

        stage4_result = pipeline.run_stage4(
            contour=self.main_element,
            settings=settings,
            airfoil_settings=self.airfoil_settings,
            tunnel_settings=self.tunnel_settings,
            wake_settings=self.wake_settings,
            trailing_edge_settings=self.trailing_edge_settings,
            boundary_loops=[self.main_element, self.flap_element],
            engine='hybrid_staged',
        )

        stage2_metadata = pipeline.apply_stage2(
            stage4_result.blocks,
            settings.stage2,
            protect_near_wall=settings.protect_near_wall,
        )
        stage2_pipeline_metadata = pipeline.build_metadata(
            stage4_result.layout_plan,
            settings,
            engine='hybrid_staged',
            stage2_metadata=stage2_metadata,
            stage1_metadata=pipeline.default_stage1_metadata(
                settings.stage1,
                protect_near_wall=settings.protect_near_wall,
            ),
        )

        self.assertTrue(stage2_pipeline_metadata['stages']['stage2_applied'])
        self.assertFalse(stage2_pipeline_metadata['stages']['stage1_applied'])

        stage1_metadata = pipeline.apply_stage1(
            stage4_result.blocks,
            settings.stage1,
            protect_near_wall=settings.protect_near_wall,
        )
        stage1_pipeline_metadata = pipeline.build_metadata(
            stage4_result.layout_plan,
            settings,
            engine='hybrid_staged',
            stage2_metadata=stage2_metadata,
            stage1_metadata=stage1_metadata,
        )

        self.assertTrue(stage1_pipeline_metadata['stages']['stage2_applied'])
        self.assertTrue(stage1_pipeline_metadata['stages']['stage1_applied'])
        self.assertTrue(stage1_pipeline_metadata['stage1']['applied'])

    def test_layout_generator_auto_closes_near_closed_and_blunt_inputs(self):
        near_closed = (
            np.array([1.0, 0.78, 0.42, 0.0, 0.40, 0.80, 1.0 + 1.0e-8], dtype=float),
            np.array([0.0, 0.05, 0.08, 0.0, -0.08, -0.05, 2.0e-8], dtype=float),
        )
        blunt = (
            np.array([1.0, 0.7, 0.2, 0.0, 0.2, 0.7, 1.0], dtype=float),
            np.array([0.03, 0.08, 0.10, 0.0, -0.10, -0.08, -0.03], dtype=float),
        )

        for contour in (near_closed, blunt):
            plan = QuadLayout.QuadLayoutGenerator.generate(
                contour,
                tunnel_height=3.5,
                wake_length=6.0,
                surface_points=len(contour[0]),
                normal_divisions=12,
                first_layer_thickness=0.004,
                layer_growth=1.05,
                connector_layers=40,
                trailing_edge_divisions=3,
            )
            loop = plan.boundary_loops[0]
            np.testing.assert_allclose(loop[0], loop[-1])

    def test_explicit_boundary_loops_keep_per_loop_resolution(self):
        theta_a = np.linspace(0.0, 2.0 * np.pi, 17)
        theta_b = np.linspace(0.0, 2.0 * np.pi, 25)
        loop_a = np.column_stack((
            0.50 + 0.45 * np.cos(theta_a),
            0.00 + 0.08 * np.sin(theta_a),
        ))
        loop_b = np.column_stack((
            1.65 + 0.25 * np.cos(theta_b),
            -0.05 + 0.06 * np.sin(theta_b),
        ))

        plan = QuadPipeline.HybridQuadPipeline.build_layout_plan(
            self.main_element,
            QuadPipeline.HybridQuadPipelineSettings(
                layout_strategy='multi_element_oc',
            ),
            airfoil_settings=self.airfoil_settings,
            tunnel_settings=self.tunnel_settings,
            wake_settings=self.wake_settings,
            trailing_edge_settings=self.trailing_edge_settings,
            boundary_loops=[loop_a, loop_b],
        )

        self.assertEqual([len(loop) for loop in plan.boundary_loops], [17, 25])

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

    def test_layout_connectors_use_matching_vertical_point_counts(self):
        plan = QuadPipeline.HybridQuadPipeline.build_layout_plan(
            self.main_element,
            QuadPipeline.HybridQuadPipelineSettings(
                layout_strategy='multi_element_oc',
            ),
            airfoil_settings=self.airfoil_settings,
            tunnel_settings=self.tunnel_settings,
            wake_settings=self.wake_settings,
            trailing_edge_settings=self.trailing_edge_settings,
        )

        specs_by_name = {spec.name: spec for spec in plan.block_specs}
        for name in ('block_hybrid_top', 'block_hybrid_bottom'):
            spec = specs_by_name[name]
            self.assertEqual(len(spec.left_boundary), len(spec.right_boundary))

        for name in ('block_hybrid_inlet', 'block_hybrid_outlet'):
            spec = specs_by_name[name]
            self.assertEqual(len(spec.lower_boundary), len(spec.upper_boundary))

    def test_stage1_none_skips_cleanup(self):
        metadata = QuadPipeline.HybridQuadPipeline.apply_stage1(
            [self._make_demo_block()],
            QuadPipeline.HybridStage1Settings(
                enabled=True,
                algorithm='none',
                iterations=10,
            ),
        )

        self.assertEqual(metadata['blocks_processed'], 0)
        self.assertEqual(metadata['algorithm'], 'none')


if __name__ == '__main__':
    unittest.main()
