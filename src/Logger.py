import sys
import os
import io
import logging

from PySide2 import QtCore

from Settings import LOGDATA


'''
class GuiHandler(logging.Handler):
    """ Class to redistribute python logging data
    from https://stackoverflow.com/a/36017801/2264936
    """

    def __init__(self, *args, **kwargs):
         # Initialize the Handler
         logging.Handler.__init__(self, *args)

         # optional take format
         # setFormatter function is derived from logging.Handler 
         for key, value in kwargs.items():
             if "{}".format(key) == "format":
                 self.setFormatter(value)

         # make the logger send data to this class
         logger.addHandler(self)
         
         # get MainWindow instance (overcomes handling parents)
         self.mainwindow = QtCore.QCoreApplication.instance().mainwindow

    def emit(self, record):
        """ Overload of logging.Handler method """

        record = self.format(record)

        # ---------------------------------------
        # Now you can send it to a GUI or similar
        # "Do work" starts here.
        # ---------------------------------------
        self.mainwindow.slots.onMessage(record)

'''        

def log():
    
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger('PyAero')

    # create a file handler
    logfile = os.path.join(LOGDATA, 'PyAero.log')
    # remove any existing logfile
    if os.path.exists(logfile):
        os.remove(logfile)
    file_handler = logging.FileHandler(logfile)
    file_handler.setLevel(logging.DEBUG)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(logging.ERROR)

    # create a logging format
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    stream_handler.setFormatter(formatter)

    # add the handlers to the root logger
    logging.getLogger('').addHandler(file_handler)
    logging.getLogger('').addHandler(stream_handler)

    logger.info('Start logging.')
