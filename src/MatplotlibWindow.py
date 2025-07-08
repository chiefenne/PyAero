import sys
import threading
import random
import time

import pandas as pd

from PySide6.QtCore import Qt, QCoreApplication
from PySide6.QtGui import QWheelEvent

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.lines import Line2D


class MplCanvas(FigureCanvas):
    """
    Provides an embeddable matplotlib canvas that can be live-updated
    Preserves scrolling ability in GUI
    """
    def __init__(self):
        self.fig = Figure()
        self.ax = self.fig.add_subplot(111)
        self.clear()
        super().__init__(self.fig)

    def clear(self):
        self.ax.clear()
        self.ax.grid()
        self.ax.set_xlabel("Time iteration")
        self.ax.set_ylabel("Value")
        self.lines = {}

    def update_plot(self, label: str, data: pd.Series, **kwargs):
        if shift_max := kwargs.get(f"{label}_trend", 50):
            trend = pd.DataFrame({"_dat": data.values}, index=data.index)["_dat"].ewm(halflife=shift_max).mean()
        if not label in self.lines:
            line_kwargs = kwargs.get(label, {})
            if "label" in line_kwargs:
                print("ERROR: passing label not allowed.")
            self.lines[label] = self.ax.plot(list(data.index), list(data.values), **line_kwargs, alpha=0.5, label=label)[0]
            # ax.plot returns a list of Line2D objects (hence the [0])
            if shift_max:
                line_kwargs["color"] = self.lines[label].get_color()
                self.lines[f"{label}_trend"] = self.ax.plot(list(trend.index), list(trend.values), **line_kwargs, label=f"{label}_trend")[0]
            self.ax.legend()
        else:
            self.lines[label].set_data(list(data.index), list(data.values))
            if shift_max:
                self.lines[f"{label}_trend"].set_data(list(trend.index), list(trend.values))

    def wheelEvent(self, event: QWheelEvent):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            super().wheelEvent(event)  # Let Matplotlib zoom
        else:
            QCoreApplication.sendEvent(self.parent(), event)
