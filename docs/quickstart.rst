.. make a label for this file
.. _quickstart:

Quickstart
==========

The general steps for mesh generation in `PyAero <index.html>`_ can be explained as follows:

1. Load an airfoil contour file
   This is to get the raw data decribing the airfoil contour.

2. Spline and refine the airfoil contour
   This is to update/improve the contour and prepare the mesh resolution along the airfoil.

3. Make a trailing edge with finite thickness
   This adds a so called blunt trailing edge to the contour. 
   Skip this step if the trailing edge should be sharp.

4. Mesh the refined airfoil contour
   Start the meshing process.

5. Export the mesh in the required format
   Save the mesh in the specified format to the harddrive.

This is it.

Check the animation below, on how this looks in the graphical user interface (version 2.1.5).

.. _figure_quickstart_steps:
.. figure::  images/quickstart.gif
   :align:   center
   :target:  _images/quickstart.gif
   :name: quickstart_steps

   Step by step mesh generation with predefined airfoil contour
