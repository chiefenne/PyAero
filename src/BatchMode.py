import os
import json

from Settings import DATAPATH


class Batch:

    def __init__(self) -> None:
        self.load_batch_control()
        self.run()

    def run(self):
        pass

    def load_batch_control(self):
        batch_controlfile = os.path.join(DATAPATH, 'Batch', 'batch_control.json')
        with open(batch_controlfile, 'r') as f:
            self.batch_control = json.load(f)

        print(self.batch_control)