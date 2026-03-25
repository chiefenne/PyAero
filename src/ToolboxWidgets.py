from PySide6 import QtCore, QtWidgets

from Utils import get_main_window


PAGE_BODY_WIDTH = 352


def configure_form_layout(form):
    form.setContentsMargins(0, 0, 0, 0)
    form.setHorizontalSpacing(12)
    form.setVerticalSpacing(10)
    form.setLabelAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
    form.setFormAlignment(QtCore.Qt.AlignTop)
    form.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
    form.setRowWrapPolicy(QtWidgets.QFormLayout.WrapLongRows)
    return form


def make_page_label(text, tooltip=None):
    label = QtWidgets.QLabel(text)
    label.setWordWrap(True)
    label.setProperty('pageFieldLabel', 'true')
    if tooltip:
        label.setToolTip(tooltip)
    return label


def make_page_option(text, tooltip=None):
    option = QtWidgets.QCheckBox(text)
    option.setProperty('pageOption', 'true')
    if tooltip:
        option.setToolTip(tooltip)
    return option


def make_page_radio(text, tooltip=None):
    option = QtWidgets.QRadioButton(text)
    option.setProperty('pageChoice', 'true')
    if tooltip:
        option.setToolTip(tooltip)
    return option


def right_aligned_row(*widgets):
    layout = QtWidgets.QHBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    layout.addStretch(1)
    for widget in widgets:
        layout.addWidget(widget)
    return layout


class WorkflowStepButton(QtWidgets.QPushButton):
    """Styled navigation button for one workflow step."""

    status_titles = {
        'ready': 'Ready',
        'done': 'Done',
        'disabled': 'Waiting',
        'info': 'Info',
    }

    def __init__(self, title, subtitle='', parent=None):
        super().__init__(parent)
        self.title = title
        self.subtitle = subtitle
        self.status = 'ready'

        self.setCheckable(True)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Fixed,
        )
        self.setMinimumHeight(62)
        self.setProperty('navRole', 'step')
        self._refreshText()

    def set_status(self, status, subtitle=None):
        self.status = status
        if subtitle is not None:
            self.subtitle = subtitle
        self.setProperty('workflowStatus', status)
        self._refreshText()
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def _refreshText(self):
        status_title = self.status_titles.get(self.status, '')
        if status_title and self.subtitle:
            detail = f'{status_title}: {self.subtitle}'
        else:
            detail = self.subtitle or status_title

        if detail:
            self.setText(f'{self.title}\n{detail}')
        else:
            self.setText(self.title)


class ListWidget(QtWidgets.QListWidget):
    """List widget that exposes airfoil activation/removal shortcuts."""

    def __init__(self, parent):
        super().__init__()
        self.mw = parent

        self.itemClicked.connect(self.listItemClicked)
        self.itemDoubleClicked.connect(self.listItemDoubleClicked)

        # get MainWindow instance (overcomes handling parents)
        self.mw = get_main_window()

    def keyPressEvent(self, event):
        key = event.key()

        if key == QtCore.Qt.Key_Delete:
            items = self.selectedItems()
            if items:
                self.mw.slots.removeAirfoil(name=items[0].text())

        super().keyPressEvent(event)

    def listItemClicked(self, item):
        """show information of airfoil in message window"""
        pass

    def listItemDoubleClicked(self, item):
        """make double clicked name in listwidget new active airfoil"""
        for airfoil in self.mw.airfoils:
            if airfoil.name == item.text():
                self.mw.slots.activateAirfoil(airfoil)
                break
