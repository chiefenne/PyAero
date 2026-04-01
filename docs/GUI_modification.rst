Customizing the GUI
===================

PyAero's interface is intentionally assembled from small, structured building blocks rather than hard-coded menu and toolbar definitions scattered throughout the codebase.

Main Customization Points
=========================

The key files are:

- :file:`src/ActionRegistry.py`
- :file:`resources/Menus/menu_layout.json`
- :file:`resources/Menus/toolbar_layout.json`
- :file:`resources/Shortcuts/shortcuts.json`

Action Registry
===============

The action registry defines:

- action ids
- labels
- tooltips
- icons
- default shortcuts
- callback targets

When you add a new command, the usual flow is:

1. define the action in :file:`src/ActionRegistry.py`
2. place the action id in the menu or toolbar layout
3. optionally document or override its shortcut

Why This Matters
================

This structure keeps the interface maintainable:

- the same action can appear in both menu and toolbar without duplicate logic
- shortcut editing works against one shared source of truth
- UI polish can evolve without rewriting every callback path

Workflow Pages
==============

The workflow sidebar itself is built from page-builder modules such as:

- :file:`src/ToolboxPagesAirfoil.py`
- :file:`src/ToolboxPagesMeshing.py`
- :file:`src/ToolboxPagesAnalysis.py`
- :file:`src/ToolboxPagesCfd.py`

This makes it practical to evolve one page at a time without destabilizing the whole interface.
