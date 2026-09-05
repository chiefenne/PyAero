import sys
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / 'src'
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import Connect
import StructuredCore as core
from StructuredEngine import StructuredEngine
from test_ortho_layers import _build_spline_data
from test_structured_topologies import (
    NACA0012, _blunt_contour, _load_dat, _sharp_contour,
)

DATA_DIR = Path(__file__).resolve().parent / 'data'
NACA2315 = DATA_DIR / 'naca2315.dat'
MW166 = DATA_DIR / 'MW-166-39-44-43.dat'


def _spline_data_for(contour):
    return _build_spline_data(np.asarray(contour, dtype=float))


def _minimum_cell_area(vertices, connectivity):
    points = np.asarray(vertices, dtype=float)
    areas = []
    for cell in np.asarray(connectivity, dtype=int):
        polygon = points[cell]
        x, y = polygon[:, 0], polygon[:, 1]
        areas.append(0.5 * abs(np.dot(x, np.roll(y, -1)) -
                               np.dot(y, np.roll(x, -1))))
    return min(areas) if areas else 0.0


class StructuredEngineMatrixTests(unittest.TestCase):
    def test_full_matrix_no_inverted_cells(self):
        engine = StructuredEngine()
        contours = {'sharp': _sharp_contour(), 'blunt': _blunt_contour()}
        for topology in ('c', 'o'):
            for shape in ('legacy', 'circular'):
                for te_name, contour in contours.items():
                    for ortho in (0, 6):
                        with self.subTest(topology=topology, shape=shape,
                                          te=te_name, ortho=ortho):
                            settings = core.StructuredMeshSettings(
                                topology=topology, tunnel_shape=shape,
                                tunnel_height=(3.5 if shape == 'legacy'
                                               else 10.0),
                                normal_divisions=40, wake_points=40,
                                ortho_layers=ortho,
                            )
                            spline_data = _spline_data_for(contour)
                            named = engine.build_blocks(
                                spline_data=spline_data, settings=settings)
                            blocks = [block for _, block in named]
                            connector = Connect.Connect()
                            vertices, connectivity = \
                                connector.connectAllBlocks(blocks)
                            self.assertGreater(
                                _minimum_cell_area(vertices, connectivity),
                                1.0e-12)

    def test_wall_row_is_contour_verbatim_every_airfoil(self):
        engine = StructuredEngine()
        for dat in (NACA0012, NACA2315, MW166):
            contour = _load_dat(dat)
            spline_data = _spline_data_for(contour)
            prepared = core.contour_array(spline_data)
            for topology in ('c', 'o'):
                with self.subTest(airfoil=dat.name, topology=topology):
                    settings = core.StructuredMeshSettings(
                        topology=topology, normal_divisions=30,
                        wake_points=30)
                    named = engine.build_blocks(
                        spline_data=spline_data, settings=settings)
                    wall = np.asarray(named[0][1].getULines()[0])
                    found = any(
                        np.allclose(wall[s:s + len(prepared)], prepared,
                                    atol=1e-12)
                        for s in range(len(wall) - len(prepared) + 1))
                    self.assertTrue(found,
                                    'contour not verbatim in wall row')

    def test_blunt_c_interface_node_match(self):
        engine = StructuredEngine()
        spline_data = _spline_data_for(_blunt_contour())
        settings = core.StructuredMeshSettings(topology='c',
                                               normal_divisions=30,
                                               wake_points=30)
        named = dict(engine.build_blocks(spline_data=spline_data,
                                         settings=settings))
        self.assertIn('block_structured_wake_strip', named)
        main = np.asarray(named['block_structured'].getULines()[0])
        strip = named['block_structured_wake_strip']
        strip_lower = np.asarray(strip.getULines()[0])
        strip_upper = np.asarray(strip.getULines()[-1])
        wake_points = settings.wake_points
        self.assertTrue(np.allclose(strip_lower, main[-wake_points:]))
        self.assertTrue(np.allclose(strip_upper,
                                    main[:wake_points][::-1]))


class StructuredEllipticEngineTests(unittest.TestCase):
    def test_elliptic_matrix_no_inverted_cells(self):
        engine = StructuredEngine()
        contours = {'sharp': _sharp_contour(), 'blunt': _blunt_contour(),
                    'mw166': _load_dat(MW166)}
        for topology in ('c', 'o'):
            for te_name, contour in contours.items():
                for ortho in (0, 6):
                    with self.subTest(topology=topology, te=te_name,
                                      ortho=ortho):
                        settings = core.StructuredMeshSettings(
                            topology=topology,
                            algorithm='elliptic',
                            elliptic_iterations=40,
                            normal_divisions=40, wake_points=40,
                            ortho_layers=ortho,
                        )
                        spline_data = _spline_data_for(contour)
                        named = engine.build_blocks(
                            spline_data=spline_data, settings=settings)
                        blocks = [block for _, block in named]
                        connector = Connect.Connect()
                        vertices, connectivity = \
                            connector.connectAllBlocks(blocks)
                        self.assertGreater(
                            _minimum_cell_area(vertices, connectivity),
                            1.0e-12)

    def test_elliptic_keeps_wall_verbatim(self):
        engine = StructuredEngine()
        contour = _load_dat(MW166)
        spline_data = _spline_data_for(contour)
        prepared = core.contour_array(spline_data)
        for topology in ('c', 'o'):
            with self.subTest(topology=topology):
                settings = core.StructuredMeshSettings(
                    topology=topology, algorithm='elliptic',
                    elliptic_iterations=30,
                    normal_divisions=30, wake_points=30)
                named = engine.build_blocks(
                    spline_data=spline_data, settings=settings)
                wall = np.asarray(named[0][1].getULines()[0])
                found = any(
                    np.allclose(wall[s:s + len(prepared)], prepared,
                                atol=1e-12)
                    for s in range(len(wall) - len(prepared) + 1))
                self.assertTrue(found)

    def test_unknown_algorithm_raises(self):
        engine = StructuredEngine()
        spline_data = _spline_data_for(_sharp_contour())
        settings = core.StructuredMeshSettings(
            algorithm='spectral', normal_divisions=20, wake_points=20)
        with self.assertRaises(ValueError):
            engine.build_blocks(spline_data=spline_data, settings=settings)


class StructuredHyperbolicEngineTests(unittest.TestCase):
    def test_hyperbolic_matrix_no_inverted_cells(self):
        engine = StructuredEngine()
        contours = {'sharp': _sharp_contour(), 'blunt': _blunt_contour(),
                    'mw166': _load_dat(MW166)}
        for topology in ('c', 'o'):
            for te_name, contour in contours.items():
                for ortho in (0, 6):
                    with self.subTest(topology=topology, te=te_name,
                                      ortho=ortho):
                        settings = core.StructuredMeshSettings(
                            topology=topology,
                            algorithm='hyperbolic',
                            normal_divisions=40, wake_points=40,
                            ortho_layers=ortho,
                        )
                        spline_data = _spline_data_for(contour)
                        named = engine.build_blocks(
                            spline_data=spline_data, settings=settings)
                        blocks = [block for _, block in named]
                        connector = Connect.Connect()
                        vertices, connectivity = \
                            connector.connectAllBlocks(blocks)
                        self.assertGreater(
                            _minimum_cell_area(vertices, connectivity),
                            1.0e-12)

    def test_hyperbolic_keeps_wall_verbatim(self):
        engine = StructuredEngine()
        contour = _load_dat(MW166)
        spline_data = _spline_data_for(contour)
        prepared = core.contour_array(spline_data)
        for topology in ('c', 'o'):
            with self.subTest(topology=topology):
                settings = core.StructuredMeshSettings(
                    topology=topology, algorithm='hyperbolic',
                    normal_divisions=30, wake_points=30)
                named = engine.build_blocks(
                    spline_data=spline_data, settings=settings)
                wall = np.asarray(named[0][1].getULines()[0])
                found = any(
                    np.allclose(wall[s:s + len(prepared)], prepared,
                                atol=1e-12)
                    for s in range(len(wall) - len(prepared) + 1))
                self.assertTrue(found)


class StructuredSmootherEngineTests(unittest.TestCase):
    def test_smoother_applied_with_correct_frozen_rows_main_frame(self):
        import GridSmoothers
        engine = StructuredEngine()
        settings = core.StructuredMeshSettings(
            topology='c', smoother='laplacian', smoother_iterations=3,
            ortho_layers=6, normal_divisions=40, wake_points=40)
        spline_data = _spline_data_for(_sharp_contour())
        with mock.patch.object(GridSmoothers, 'smooth',
                              wraps=GridSmoothers.smooth) as spy:
            engine.build_blocks(spline_data=spline_data, settings=settings)
        # first call is the main block; frozen_rows must protect the wall
        # plus every ortho layer
        _args, kwargs = spy.call_args_list[0]
        self.assertEqual(kwargs['frozen_rows'], 1 + settings.ortho_layers)
        self.assertEqual(kwargs['method'], 'laplacian')

    def test_smoother_applied_with_frozen_rows_one_on_wake_strip(self):
        import GridSmoothers
        engine = StructuredEngine()
        settings = core.StructuredMeshSettings(
            topology='c', smoother='laplacian', smoother_iterations=3,
            ortho_layers=6, normal_divisions=40, wake_points=40)
        spline_data = _spline_data_for(_blunt_contour())
        with mock.patch.object(GridSmoothers, 'smooth',
                              wraps=GridSmoothers.smooth) as spy:
            named = engine.build_blocks(spline_data=spline_data,
                                        settings=settings)
        names = [name for name, _block in named]
        self.assertIn('block_structured_wake_strip', names)
        strip_index = names.index('block_structured_wake_strip')
        _args, kwargs = spy.call_args_list[strip_index]
        self.assertEqual(kwargs['frozen_rows'], 1)

    def test_smoother_none_skips_call(self):
        import GridSmoothers
        engine = StructuredEngine()
        settings = core.StructuredMeshSettings(
            topology='c', smoother='none', normal_divisions=30,
            wake_points=30)
        spline_data = _spline_data_for(_sharp_contour())
        with mock.patch.object(GridSmoothers, 'smooth') as spy:
            engine.build_blocks(spline_data=spline_data, settings=settings)
        spy.assert_not_called()

    def test_wall_verbatim_end_to_end_with_smoothing_on(self):
        engine = StructuredEngine()
        contour = _load_dat(MW166)
        spline_data = _spline_data_for(contour)
        prepared = core.contour_array(spline_data)
        for method in ('laplacian', 'elliptic', 'angle_based'):
            for topology in ('c', 'o'):
                with self.subTest(method=method, topology=topology):
                    settings = core.StructuredMeshSettings(
                        topology=topology, smoother=method,
                        smoother_iterations=8, normal_divisions=30,
                        wake_points=30)
                    named = engine.build_blocks(
                        spline_data=spline_data, settings=settings)
                    wall = np.asarray(named[0][1].getULines()[0])
                    found = any(
                        np.allclose(wall[s:s + len(prepared)], prepared,
                                    atol=1e-12)
                        for s in range(len(wall) - len(prepared) + 1))
                    self.assertTrue(found)


class StructuredDispatchTests(unittest.TestCase):
    def test_makemesh_dispatches_structured(self):
        import Meshing
        with mock.patch.object(Meshing, 'get_main_window',
                               return_value=None):
            tunnel = Meshing.Windtunnel()
        spline_data = _spline_data_for(_sharp_contour())
        airfoil = mock.Mock()
        airfoil.spline_data = spline_data
        airfoil.has_spline = True
        airfoil.name = 'naca0012'
        airfoil.mesh_blocks = None
        settings = mock.Mock(spec=Meshing.WindtunnelMeshSettings)
        settings.engine = 'structured'
        settings.structured = core.StructuredMeshSettings(
            normal_divisions=25, wake_points=25)
        with mock.patch.object(tunnel, '_finalizeMeshGeneration',
                               return_value=True) as finalize, \
                mock.patch.object(tunnel, 'MeshQuality') as quality:
            result = tunnel.makeMesh(settings, airfoil=airfoil)
        self.assertTrue(result)
        finalize.assert_called_once()
        quality.assert_called_once_with(crit='k2inf')
        self.assertTrue(tunnel.blocks)
        self.assertEqual(tunnel.tunnel_height,
                         settings.structured.tunnel_height)


if __name__ == '__main__':
    unittest.main()
