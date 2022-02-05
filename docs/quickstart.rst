.. make a label for this file
.. _quickstart:

.. |br| raw:: html

   <br />



Quickstart
==========

The general steps for mesh generation in `PyAero <index.html>`_ can be explained as follows:

1. Load an airfoil contour file

   This is to get the raw data decribing the airfoil contour.|br||br|

2. Spline and refine the airfoil contour

   This is to update/improve the contour and prepare the mesh resolution along the airfoil.|br||br|

3. Make a trailing edge with finite thickness

   This adds a so called blunt trailing edge to the contour. 
   Skip this step if the trailing edge should be sharp. |br||br|

4. Mesh the refined airfoil contour

   Start the meshing process.|br||br|

5. Export the mesh in the required format

   Save the mesh in the specified format to the harddrive.|br||br|

This is it.

Check the animation below, on how this looks in the graphical user interface.

.. _figure_quickstart_steps:
.. figure::  images/quickstart_steps.gif
   :align:   center
   :target:  _images/quickstart_steps.gif
   :name: quickstart_steps

   Step by step mesh generation with predefined airfoil contour
