import json


class Batch:

    def __init__(self) -> None:
        self.load_batch_control()
        self.run()

    def run(self):
        pass

    def load_batch_control(self):
        with open('batch_commands.json', 'r') as f:
            self.batch_control = json.load(f)