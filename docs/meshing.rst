.. make a label for this file
.. _meshing:

Making Meshes
=============

After :ref:`spline_refine` and optionally making a blunt :ref:`trailing_edge`, the airfoil contour can be meshed which is the primary purpose of `PyAero <index.html>`_.

The default settings for the mesh generation process should be good enough to generate a mesh that can be used to do CFD RANS simulations or similar.

The mesh is constructed from four individual blocks, each of which has its own configuration options.
The mesh blocks are (listed below with the same name as in the GUI):
  - Airfoil contour mesh
  - Airfoil trailing edge mesh
  - Windtunnel mesh (around airfoil)
  - Windtunnel mesh (wake)

The main mesh block is the one directly attached to the airfoil contour. It is constructed by grid lines perpendicular to the airfoil, starting at the points from the splined contour, thus taking exactly that point distribution (see :ref:`spline_refine`).

The default settings there implement a streching away from the airfoil, so that the thinnest mesh layer is attached at the airfoil and mesh layers are gradually thickened outwards.

