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

NACA2315 = PROJECT_ROOT / 'lib_AE' / 'Construct2D_2.1.4' / \
    'sample_airfoils' / 'naca2315.dat'
MW166 = PROJECT_ROOT / 'boundary_layer_code' / 'Airfoils' / \
    'MW-166-39-44-43.dat'


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
