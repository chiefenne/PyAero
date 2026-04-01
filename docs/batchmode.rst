.. _batchmode:

Batch Mode
==========

PyAero can run the same contour-preparation, mesh-generation, and mesh-export pipeline without opening the GUI. This is useful when you need to process several airfoils with one shared setup.

Starting Batch Mode
===================

Run the application from the repository root:

.. code-block:: bash

   python src/PyAero.py -no-gui data/Batch/batch_control.json

The batch control file can live anywhere. The shipped example in :file:`data/Batch/batch_control.json` is the best starting point.

What the Control File Defines
=============================

The batch configuration contains:

- the source directory for airfoils
- the list of airfoil filenames to process
- whether each airfoil should receive a finite-thickness trailing edge
- the output directory
- the requested export formats
- the geometry-preparation settings
- the mesh-block settings

The GUI and batch mode share the same workflow service underneath, so the settings map closely to what you see in the application.

Export Formats
==============

The canonical export formats are:

- ``flma``
- ``su2``
- ``gmsh``
- ``vtu``

Batch mode also accepts common aliases such as ``VTK`` for ``VTU`` and ``MSH`` for ``Gmsh``. Output filenames are created from the requested basename plus the appropriate extension.

Example Structure
=================

The shipped example contains sections like:

- ``Airfoils``
- ``Output formats``
- ``Airfoil contour refinement``
- ``Airfoil trailing edge``
- ``Airfoil contour mesh``
- ``Airfoil trailing edge mesh``
- ``Windtunnel mesh airfoil``
- ``Windtunnel mesh wake``

Each airfoil in the list is loaded, prepared, meshed, and exported in sequence.

When to Use Batch Mode
======================

Batch mode is useful when:

- you want consistent settings across many airfoils
- you are comparing several sections quickly
- you already know your preferred refinement and mesh parameters
- you want to export the same mesh set in several formats without manual clicking

Practical Notes
===============

- Start PyAero from the repository root so resource paths resolve correctly.
- The batch pipeline assumes the same contour preparation order as the GUI.
- Export failures are handled per airfoil, so one failing case does not necessarily stop the whole run.
