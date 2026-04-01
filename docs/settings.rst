.. make a label for this file
.. _tutorial_settings:

Settings
========

`PyAero <index.html>`_ supports customizing its behaviour through configuration files.

Most application settings are stored in :file:`config/config.ini`. The values from that file are
loaded by :file:`src/Settings.py` and made available throughout the application.

Typical examples are:

- default airfoil and data paths in the :code:`[Paths]` and :code:`[Application]` sections
- graphics settings such as :code:`MIN_ZOOM`, :code:`MAX_ZOOM` and :code:`RUBBERBAND_MIN` in the :code:`[Graphics]` section
- dialog and logging related options in the :code:`[Dialogs]` and :code:`[Logging]` sections

Keyboard shortcuts are defined centrally in :file:`src/ActionRegistry.py`. Built-in defaults are stored in
:file:`resources/Shortcuts/shortcuts.json`, while optional user overrides can be stored in
:file:`config/shortcuts_user.json`.

