
import os
import configparser


class Config:
    def __init__(self, mainwindow):
        self.mw = mainwindow
        self.load_config()
        self.set_attributes()

    def get(self, section, key):
        return self.config.get(section, key)

    def getint(self, section, key):
        return self.config.getint(section, key)

    def getfloat(self, section, key):
        return self.config.getfloat(section, key)

    def getboolean(self, section, key):
        return self.config.getboolean(section, key)

    def load_config(self):
        # Read the configuration file
        self.config_parser = configparser.ConfigParser(interpolation=configparser.ExtendedInterpolation())
        self.config_parser.read(os.path.join(os.getcwd(), 'config/config.ini'))

    def set_attributes(self):
        # Automatically derive attributes from the config file
        attributes = {section: self.config_parser.options(section) for section in self.config_parser.sections()}

        for section, keys in attributes.items():
            for key in keys:
                value = self.config_parser.get(section, key)
                try:
                    # Try to convert to int
                    value = int(value)
                except ValueError:
                    try:
                        # Try to convert to float
                        value = float(value)
                    except ValueError:
                        try:
                            # Try to convert to boolean
                            value = self.config_parser.getboolean(section, key)
                        except ValueError:
                            # Keep as string if all conversions fail
                            pass
                setattr(self.mw, key.upper(), value)
