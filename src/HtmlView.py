from PySide2 import QtGui, QtCore


class HtmlView(QtGui.QWebView):
    """docstring for PHtmLvIEW"""
    def __init__(self, parent):
        super(HtmlView, self).__init__(parent)
        self.parent = parent


    localfile = '.'
    webview.fromLocalFile(localfile)
