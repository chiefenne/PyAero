.. |br| raw:: html

   <br />

.. make a label for this file
.. _quickstart:

Quick start guide
=================

The general steps for mesh generation in `PyAero <index.html>`_ can be explained as follows:

1. Load an airfoil contour file |br|
   This is to get the raw data decribing the airfoil contour.

2. Spline and refine the airfoil contour |br|
   This is to update/improve the contour and prepare the mesh resolution along the airfoil.

3. Make a trailing edge with finite thickness |br|
   This adds a so called blunt trailing edge to the contour. |br|
   Skip this step if the trailing edge should be sharp.

4. Mesh the refined airfoil contour |br|
   Start the meshing process.

5. Export the mesh in the required format |br|
   Save the mesh in the specified format to the harddrive.

This is it.

Check the animation below, on how this looks in the graphical user interface (version 2.1.5).

.. _figure_quickstart_steps:
.. figure::  images/quickstart.gif
   :align:   center
   :target:  _images/quickstart.gif
   :name: quickstart_steps

   Step by step mesh generation with predefined airfoil contour
