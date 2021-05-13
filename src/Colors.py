"""
Functions for color customizing of all PyAero items.
"""

from PySide6 import QtCore


def torgb(color):
    """Convert HTML string to (r, g, b, a) tuple"""

    # pylint: disable=E1103
    red, green, blue, alpha = QtCore.QColor.getRgb(color)
    # pylint: enable=E1103

    return (red, green, blue, alpha)


def tohtml():
    """Convert (r, g, b) tuple to HTML string"""
    html_string = '#2784CB'
    return html_string
