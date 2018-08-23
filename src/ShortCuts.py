
from PySide2 import QtGui, QtCore, QtWidgets

class ShortCuts:
    """docstring for ClassName """
    def __init__(self, parent):
        if not isinstance(parent, QtWidgets.QMainWindow):
            raise TypeError('parent must be a MainWindow')

        self.parent = parent

    def addShortcut(self, shortcut, slot):
        """Add a shortcut to a slot (event handler)

        Args:
            shortcut (STRING): Something like 'ALT+m'
            slot (STRING): Method of PGuiSlots

        Returns:
            object: QShortcut object
        """
        guislot = getattr(self.parent.slots, slot)
        sc = QtWidgets.QShortcut(QtGui.QKeySequence(shortcut), self.parent,
                        guislot)
        return sc

    def enableShortcut(self, enable=True):
        self.setEnabled(self, enable)

    def changeKey(self, key):
        self.setKey(key)
