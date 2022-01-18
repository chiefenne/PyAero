import os
import json
from FoilApi import FoilApi
import MeshingApi
import numpy as np
from Settings import DATAPATH
import matplotlib.pyplot as plt
import logging
logger = logging.getLogger(__name__)
from PyAero import __version__


class Batch:

    def __init__(self, batch_controlfile):
        # self.app = app
        # self.app.mainwindow = self
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
        trailing_edges = self.batch_control['Airfoils']['trailing_edges']

        message = 'Airfoils to mesh:'
        print(message)
        logger.info(message)
        for airfoil in airfoils:
            message = f'     --> {airfoil}'
            print(message)
            logger.info(message)

        print('\n')

        for i, foilname in enumerate(airfoils):

            message = f'Starting batch meshing for airfoil {foilname}'
            print(message)
            logger.info(message)

            # load airfoil
            basename = os.path.splitext(foilname)[0]
            airfoil = FoilApi(basename)
            airfoil.readContour(os.path.join(airfoil_path, foilname), '#')

            # spline and refine
            airfoil.refine_parameters['"Airfoil contour refinement"'] = self.batch_control[
                'Airfoil contour refinement']
            
            airfoil.doSplineRefine()

            f = airfoil.spline_data[0]
            print(f[0].shape, f[1].shape)
            plt.figure()
            plt.plot(f[0], f[1],label='before_add_tail')

            # add trailing edge
            if trailing_edges[i] == 'yes':
                airfoil.has_TE = True
                airfoil.refine_parameters['Airfoil trailing edge'] = self.batch_control[
                    'Airfoil trailing edge']
                airfoil.addTrailingEdge()
                f = airfoil.spline_data[0]
                plt.plot(f[0], f[1],label='after_add_tail')
            plt.legend()
            plt.show()

            # make mesh
            wind_tunnel = MeshingApi.Windtunnel(airfoil)
            # refresh mesh parameters
            wind_tunnel.mesh_parameters['Airfoil contour mesh'] = self.batch_control[
                'Airfoil contour mesh']
            wind_tunnel.mesh_parameters['Airfoil trailing edge mesh'] = self.batch_control[
                'Airfoil trailing edge mesh']
            wind_tunnel.mesh_parameters['Windtunnel mesh airfoil'] = self.batch_control[
                'Windtunnel mesh airfoil']
            wind_tunnel.mesh_parameters['Windtunnel mesh wake'] = self.batch_control[
                'Windtunnel mesh wake']
            wind_tunnel.makeMesh()            
            # wind_tunnel.drawMesh()
            message = f'Finished batch meshing for airfoil {foilname}'
            print(message)
            logger.info(message)

            # export mesh
            message = f'Starting mesh export for airfoil {foilname}'
            print(message)
            logger.info(message)
            # print(wind_tunnel.cells)

            for output_format in output_formats:
                extension = {'FLMA': '.flma',
                             'SU2': '.su2',
                             'GMSH': '.msh',
                             'VTK': '.vtk',
                             'CGNS': '.cgns',
                             'ABAQUS': '.inp',
                             'FLUENT': '.msh'}
                mesh_name = os.path.join(mesh_path, basename + extension[output_format])
                getattr(MeshingApi.BlockMesh, 'write'+output_format)(wind_tunnel, name=mesh_name)

                message = f'Finished mesh export for airfoil {foilname} to {mesh_name}'
                print(message)
                logger.info(message)


if __name__ == '__main__':
    batchmode = Batch('./data/Batch/batch_control.json')
    batchmode.run_batch()
