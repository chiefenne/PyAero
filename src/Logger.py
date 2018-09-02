import sys
import os
import io
import logging

from PySide2 import QtCore

from Settings import LOGDATA


class GuiHandler(logging.Handler):
    """ Class to redistribute python logging data
    from https://stackoverflow.com/a/36017801/2264936
    """

    # have a class member to store the existing logger
    logger_instance = logging.getLogger('')

    def __init__(self, parent=None, *args):
         # Initialize the Handler
         super().__init__(*args)
         
         self.parent = parent

         # make the logger send data to this class
         self.logger_instance.addHandler(self)

    def emit(self, record):
        """ Overload of logging.Handler method """

        record = self.format(record)

        self.parent.slots.onMessage(record)


def log(mainwindow):
    
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    logfile = os.path.join(LOGDATA, 'PyAero.log')
    # remove any existing logfile
    if os.path.exists(logfile):
        os.remove(logfile)

    # create a file handler
    file_handler = logging.FileHandler(logfile)
    file_handler.setLevel(logging.DEBUG)

    # create a console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.ERROR)

    # create a gui handler (for writing to the message dock window)
    gui_handler = GuiHandler(parent=mainwindow)
    gui_handler.setLevel(logging.INFO)

    # create specific  logging formats
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
    gui_formatter = logging.Formatter('%(levelname)s - %(message)s')
    
    # apply formats to handlers
    file_handler.setFormatter(file_formatter)
    console_handler.setFormatter(console_formatter)
    gui_handler.setFormatter(gui_formatter)

    # add the handlers to the root logger
    logging.getLogger('').addHandler(file_handler)
    # logging.getLogger('').addHandler(console_handler)
    logging.getLogger('').addHandler(gui_handler)

    logger.info('Starting to log')
