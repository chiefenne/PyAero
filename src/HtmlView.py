from PySide6 import QtGui, QtCore


class HtmlView(QtGui.QWebView):
    """docstring for HtmLvIEW"""
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
