import os
import json

import Airfoil
import SplineRefine
import TrailingEdge
import Meshing
import Connect
from Settings import DATAPATH

import logging
logger = logging.getLogger(__name__)


class Batch:

    def __init__(self, app, batch_controlfile, __version__):
        self.app = app
        self.app.mainwindow = self
        self.load_batch_control(batch_controlfile)

        stars = 50
        message_stars = stars*'*'
        print('\n' + message_stars)
        message = '{:*^{stars}}'.format(' PYAERO batch meshing ', stars=stars)
        print(message)
        message = '{:*^{stars}}'.format('  v' + __version__ + '  ', stars=stars)
        print(message)
        logger.info(message)
        print(message_stars + '\n')


    def load_batch_control(self, batch_controlfile):
        with open(batch_controlfile, 'r') as f:
            self.batch_control = json.load(f)

    def run_batch(self):
        
        # loop all airfoils
        airfoil_path = self.batch_control['Airfoils']['path']
        mesh_path = self.batch_control['Output formats']['path']
        output_formats = self.batch_control['Output formats']['formats']

        print('Airfoil path is', airfoil_path)
        print('Mesh output path is', mesh_path, '\n')

        airfoils = self.batch_control['Airfoils']['names']
        message = 'Airfoils to mesh:'
        print(message)
        logger.info(message)
        for airfoil in airfoils:
            message = f'     --> {airfoil}'
            print(message)
            logger.info(message)
        
        print('\n')

        for airfoil in airfoils:

            message = f'Starting batch meshing for airfoil {airfoil}'
            print(message)
            logger.info(message)

            # load airfoil
            basename = os.path.splitext(airfoil)[0]
            self.airfoil = Airfoil.Airfoil(basename)
            self.airfoil.readContour(os.path.join(airfoil_path, airfoil), '#')

            # spline and refine
            refinement = self.batch_control['Airfoil contour refinement']
            refine = SplineRefine.SplineRefine()
            refine.doSplineRefine(tolerance=refinement['Refinement tolerance'],
                                  points=refinement['Number of points on spline'],
                                  ref_te=refinement['Refine trailing edge old'],
                                  ref_te_n=refinement['Refine trailing edge new'],
                                  ref_te_ratio=refinement['Refine trailing edge ratio'])

            # trailing edge
            te = self.batch_control['Airfoil trailing edge']
            trailing = TrailingEdge.TrailingEdge()
            trailing.trailingEdge(blend=te['Upper side blending length'] / 100.0,
                                  ex=te['Upper blending polynomial exponent'],
                                  thickness=te['Trailing edge thickness relative to chord'],
                                  side='upper')
            trailing.trailingEdge(blend=te['Lower side blending length'] / 100.0,
                                  ex=te['Upper blending polynomial exponent'],
                                  thickness=te['Trailing edge thickness relative to chord'],
                                  side='lower')
            
            # make mesh
            wind_tunnel = Meshing.Windtunnel()
            contour = self.app.mainwindow.airfoil.spline_data[0]

            # mesh around airfoil
            acm = self.batch_control['Airfoil contour mesh']
            wind_tunnel.AirfoilMesh(name='block_airfoil',
                                    contour=contour,
                                    divisions=acm['Divisions normal to airfoil'],
                                    ratio=acm['Cell growth rate'],
                                    thickness=acm['1st cell layer thickness'])

            # mesh at trailing edge
            tem = self.batch_control['Airfoil trailing edge mesh']
            wind_tunnel.TrailingEdgeMesh(name='block_TE',
                                         te_divisions=tem['Divisions at trailing edge'],
                                         thickness=tem['1st cell layer thickness'],
                                         divisions=tem['Divisions downstream'],
                                         ratio=tem['Cell growth rate'])

            # mesh tunnel airfoil
            tam = self.batch_control['Windtunnel mesh airfoil']
            wind_tunnel.TunnelMesh(name='block_tunnel',
                                   tunnel_height=tam['Windtunnel height'],
                                   divisions_height=tam['Divisions of tunnel height'],
                                   ratio_height=tam['Cell thickness ratio'],
                                   dist=tam['Distribution biasing'])

            # mesh tunnel wake
            twm = self.batch_control['Windtunnel mesh wake']
            wind_tunnel.TunnelMeshWake(name='block_tunnel_wake',
                                       tunnel_wake=twm['Windtunnel wake'],
                                       divisions=twm['Divisions in the wake'],
                                       ratio=twm['Cell thickness ratio'],
                                       spread=twm['Equalize vertical wake line at'] / 100.0)
            
            # connect mesh blocks
            connect = Connect.Connect(None)
            vertices, connectivity, _ = \
                connect.connectAllBlocks(wind_tunnel.blocks)

            # add mesh to Wind-tunnel instance
            wind_tunnel.mesh = vertices, connectivity

            # generate cell to edge connectivity from mesh
            wind_tunnel.makeLCE()

            # generate cell to edge connectivity from mesh
            wind_tunnel.makeLCE()

            # generate boundaries from mesh connectivity
            wind_tunnel.makeBoundaries()

            message = f'Finished batch meshing for airfoil {airfoil}'
            print(message)
            logger.info(message)

            # export mesh
            message = f'Starting mesh export for airfoil {airfoil}'
            print(message)
            logger.info(message)

            for output_format in output_formats:
                extension = {'FLMA': '.flma',
                             'SU2': '.su2',
                             'GMSH': '.msh',
                             'VTK': '.vtk',
                             'CGNS': '.cgns',
                             'ABAQUS': '.inp'}
                mesh_name = os.path.join(mesh_path, basename + extension[output_format])
                getattr(Meshing.BlockMesh, 'write'+output_format)(wind_tunnel, name=mesh_name)

                message = f'Finished mesh export for airfoil {airfoil} to {mesh_name}'
                print(message)
                logger.info(message)
