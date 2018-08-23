import sys
import os
import io
import logging

from PySide2 import QtCore

from Settings import LOGDATA

# have a class member to store the existing logger
logger = logging.getLogger(__name__)


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
    
    # f = io.StringIO()
    # sys.stdout = f

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    # logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
    
    # create file handler which logs even debug messages
    fh = logging.FileHandler(os.path.join(LOGDATA, 'PyAero.log'))
    fh.setLevel(logging.DEBUG)

    # create console handler with a higher log level
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.ERROR)


    # create GUI handler that reports to message window
    # gh = GuiHandler()
    # gh.setLevel(logging.DEBUG)

    # create formatter and add it to the handlers
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    fh.setFormatter(formatter)
    ch.setFormatter(formatter)

    # add the handlers to logger
    logger.addHandler(ch)
    logger.addHandler(fh)
    # logger.addHandler(gh)


"""

# application code

logger.debug('debug message')
logger.info('info message')
logger.warn('warn message')
logger.error('error message')
logger.critical('critical message')

"""