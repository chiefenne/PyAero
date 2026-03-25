import os
import logging
import datetime
import configparser


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

        # Make the logger send data to this class
        self.logger_instance.addHandler(self)

    def emit(self, record):
        """ Overload of logging.Handler method """
        formatted_record = self.format(record)
        self.parent.slots.onMessage(formatted_record)


def log(main_window):
    useGUI = main_window != 'console'
    root_logger = logging.getLogger('')
    root_logger.setLevel(logging.INFO)

    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    log_format = 'PyAero_%Y-%m-%d____h%H-m%M-s%S.log'
    log_dir = _resolve_log_directory(main_window)
    os.makedirs(log_dir, mode=0o777, exist_ok=True)
    logfile = os.path.join(
        log_dir,
        datetime.datetime.now().strftime(log_format),
    )

    # create a file handler
    file_handler = logging.FileHandler(logfile)
    file_handler.setLevel(logging.DEBUG)

    # create a console handler (for error messages)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.ERROR)

    # create a gui handler (for writing to the message dock window)
    if useGUI:
        gui_handler = GuiHandler(parent=main_window)
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
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    if useGUI:
        root_logger.addHandler(gui_handler)

    # getLogger with __name__ retruns a logger for the current module (here Logger)
    # example log message of level INFO preceeded by module name
    # 2018-09-30 18:18:47,559 - Logger - INFO - Starting to log
    logger = logging.getLogger(__name__)
    logger.info('Starting to log')


def _resolve_log_directory(main_window):
    if main_window != 'console':
        return main_window.LOGS

    parser = configparser.ConfigParser(
        interpolation=configparser.ExtendedInterpolation()
    )
    parser.read(os.path.join(os.getcwd(), 'config/config.ini'))
    return parser.get('Paths', 'LOGS', fallback='data/LOGS')
