import os
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / 'src'
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import Mesh


class MeshExportCleanupTests(unittest.TestCase):
    def setUp(self):
        mesh_data = Mesh.MeshData(
            vertices=[
                (0.0, 0.0),
                (1.0, 0.0),
                (1.0, 1.0),
                (0.0, 1.0),
            ],
            connectivity=[(0, 1, 2, 3)],
            boundary_tags={
                'airfoil': [(0, 1)],
                'outlet': [(1, 2)],
                'top': [(2, 3)],
                'inlet': [(3, 0)],
                'bottom': [],
            },
        )
        self.mesh_model = Mesh.BlockStructuredMesh(
            name='demo',
            blocks=[],
            data=mesh_data,
            boundary_conditions={
                'airfoil': 'wall',
                'inlet': 'inlet',
                'outlet': 'outlet',
                'top': 'top',
                'bottom': 'bottom',
            },
        )

    def test_export_format_normalization_uses_canonical_names(self):
        self.assertEqual(
            Mesh.MeshExportRegistry.normalize_format('VTK'),
            'vtu',
        )
        self.assertEqual(
            Mesh.MeshExportRegistry.normalize_format('.msh'),
            'gmsh',
        )
        self.assertEqual(
            Mesh.MeshExportRegistry.normalize_format('AVL FIRE'),
            'flma',
        )

    def test_extension_lookup_uses_canonical_export_extension(self):
        self.assertEqual(
            Mesh.MeshExportRegistry.extension_for('vtk'),
            '.vtu',
        )
        self.assertEqual(
            Mesh.MeshExportRegistry.extension_for('gmsh'),
            '.msh',
        )

    def test_boundary_definitions_reject_empty_names(self):
        with self.assertRaisesRegex(ValueError, 'cannot be empty'):
            Mesh.BoundaryDefinitions.from_mapping({'airfoil': '   '})

    def test_boundary_definitions_reject_duplicate_names(self):
        with self.assertRaisesRegex(ValueError, 'must be unique'):
            Mesh.BoundaryDefinitions.from_mapping(
                {'airfoil': 'wall', 'inlet': 'wall'}
            )

    def test_export_registry_writes_all_supported_mesh_formats(self):
        expected_headers = {
            'flma': '8',
            'su2': '%',
            'gmsh': '$MeshFormat',
            'vtu': '<?xml version="1.0"?>',
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            for mesh_format, expected_header in expected_headers.items():
                output_name = os.path.join(
                    temp_dir,
                    'demo' + Mesh.MeshExportRegistry.extension_for(mesh_format),
                )
                Mesh.MeshExportRegistry.export(
                    self.mesh_model,
                    mesh_format,
                    output_name,
                )

                self.assertTrue(os.path.exists(output_name))
                with open(output_name, 'r', encoding='utf-8') as handle:
                    self.assertEqual(handle.readline().rstrip(), expected_header)


if __name__ == '__main__':
    unittest.main()
