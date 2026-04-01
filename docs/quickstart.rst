.. _quickstart:

Quick Start Guide
=================

This chapter walks through the main path from a raw airfoil file to an exported mesh.

Start PyAero from the repository root:

.. code-block:: bash

   python src/PyAero.py

Main Workflow
=============

1. Load an airfoil contour.

   Use the airfoil library page, the regular file dialog, or drag and drop a ``.dat`` or ``.txt`` contour into the application.

2. Prepare the contour.

   Open :guilabel:`Geometry Prep`, choose ``CST`` or ``B-spline (legacy)``, and click :guilabel:`Prepare and Refine`.

3. Optionally add a finite-thickness trailing edge.

   If the downstream mesh should resolve a blunt trailing edge, configure the blending parameters and click :guilabel:`Add Trailing Edge`.

4. Generate the mesh.

   Open :guilabel:`Mesh`, adjust the block sizes if needed, and click :guilabel:`Create Mesh`.

5. Export the result.

   In the :guilabel:`Mesh Export` section, choose one or more formats, define boundary names if needed, and click :guilabel:`Export Mesh`.

That is the complete primary workflow.

Quick Demo
==========

The animation below still shows the overall sequence well even though the styling of the current interface has evolved.

.. figure:: images/quickstart.gif
   :align: center
   :target: _images/quickstart.gif

   The basic PyAero workflow from loaded contour to exported mesh.

Good Defaults
=============

For a first run, the shipped defaults are a good baseline:

- use the bundled default airfoil
- keep the CST method selected
- keep the default refinement settings
- skip trailing-edge thickening unless you specifically need it
- generate the mesh with the default block settings
- export ``SU2`` and ``VTU`` if you want one solver file and one visualization file

Next Steps
==========

After you are comfortable with the basic path, continue with:

- :ref:`user_interface` for the redesigned workflow shell
- :ref:`loading_airfoils` for library-based loading and importing
- :ref:`spline_refine` for contour preparation details
- :ref:`meshing` for block controls, smoothing, and export
