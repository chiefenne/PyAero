import os
import logging
import datetime

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

    useGUI = True

    if mainwindow == 'file_only':
        useGUI = False

    logging.basicConfig(level=logging.INFO)
    # logging.getLogger('') gets the 'root' logger
    # stdout is the only handler initially
    # see https://stackoverflow.com/a/6459613/2264936
    stdout_handler = logging.getLogger('').handlers[0]

    format = 'PyAero_%Y-%m-%d____h%H-m%M-s%S.log'
    logfile = os.path.join(LOGDATA, datetime.datetime.now().strftime(format))

    # create a file handler
    file_handler = logging.FileHandler(logfile)
    file_handler.setLevel(logging.DEBUG)

    # create a console handler (for error messages)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.ERROR)

    # create a gui handler (for writing to the message dock window)
    if useGUI:
        gui_handler = GuiHandler(parent=mainwindow)
        gui_handler.setLevel(logging.INFO)

    # create specific logging formats
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
    if useGUI:
        gui_formatter = logging.Formatter('%(levelname)s - %(message)s')

    # apply formats to handlers
    file_handler.setFormatter(file_formatter)
    console_handler.setFormatter(console_formatter)
    if useGUI:
        gui_handler.setFormatter(gui_formatter)

    # add the handlers to the root logger
    logging.getLogger('').addHandler(file_handler)
    logging.getLogger('').addHandler(console_handler)
    if useGUI:
        logging.getLogger('').addHandler(gui_handler)

    # remove the standard handler from the root logger
    # it would log everything to the console automatically
    # see https://stackoverflow.com/a/6459613/2264936
    logging.getLogger('').removeHandler(stdout_handler)

    # getLogger with __name__ retruns a logger for the current module (here Logger)
    # example log message of level INFO preceeded by module name
    # 2018-09-30 18:18:47,559 - Logger - INFO - Starting to log
    logger = logging.getLogger(__name__)
    logger.info('Starting to log')
