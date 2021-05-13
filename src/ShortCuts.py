
from PySide6 import QtGui, QtWidgets

class ShortCuts:
    """docstring for ClassName """
    def __init__(self, parent):
        if not isinstance(parent, QtWidgets.QMainWindow):
            raise TypeError('parent must be a MainWindow instance')

        self.parent = parent

    def addShortcut(self, shortcut, slotMethod, *args):
        """Add a shortcut to a slot (event handler)

        Args:
            shortcut (STRING): Something like 'ALT+m'
            slotMethod (STRING): Method of GuiSlots 'Slot' class

        Returns:
            object: QShortcut object
        """
        
        # guislot converts to:
        # self.parent.slots.slotMethod()
        guislot = getattr(self.parent.slots, slotMethod)
        
        sc = QtGui.QShortcut(QtGui.QKeySequence(shortcut), self.parent)
        
        # connect shortcut to self.parent.slots(*args)
        sc.activated.connect(lambda: guislot(*args))

        return

    def enableShortcut(self, enable=True):
        self.setEnabled(self, enable)

    def changeKey(self, key):
        self.setKey(key)
