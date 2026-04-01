.. _tutorial_settings:

Settings
========

PyAero keeps its runtime behavior in a small set of plain-text configuration files. The most important locations are:

- :file:`config/config.ini`
- :file:`resources/Shortcuts/shortcuts.json`
- :file:`config/shortcuts_user.json`

Main Runtime Settings
=====================

Most application settings live in :file:`config/config.ini`.

Important sections include:

``[Paths]``
   Controls the data directory, airfoil library root, output folder, and log folder.

``[Application]``
   Controls the predefined airfoil, decimal separator, and exit behavior.

``[Graphics]``
   Controls marker size, zoom anchoring, zoom limits, rubber-band threshold, and view style.

``[Magnifier]``
   Controls the built-in magnifier size and magnification.

``[Dialogs]``
   Defines the default file filters used by dialogs.

``[Logging]``
   Controls message coloring and related behavior.

Airfoil Paths
=============

Two settings matter most for everyday use:

- ``AIRFOILS`` defines the root of the airfoil library
- ``DEFAULT_AIRFOIL`` defines what is loaded by the predefined-airfoil action

The local airfoil library is managed automatically below the configured airfoil root.

Keyboard Shortcuts
==================

PyAero's shortcut system is registry-driven.

- Built-in defaults live in :file:`resources/Shortcuts/shortcuts.json`
- User overrides are stored in :file:`config/shortcuts_user.json`

The shortcut editor in the GUI reads and writes these same definitions, so manual edits and GUI edits stay aligned.

Menus and Toolbar
=================

Menus and toolbar content are assembled from layout data under :file:`resources/Menus/` while actions themselves are defined centrally in :file:`src/ActionRegistry.py`.

This split keeps three things clean:

- the UI layout
- the action definitions
- the shortcut bindings

Launch Location
===============

PyAero should be started from the repository root. The application expects bundled resources such as menus, icons, and airfoil data to resolve relative to that location.
