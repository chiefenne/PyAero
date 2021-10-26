import json


class Batch:

    def __init__(self) -> None:
        self.batch_commands()
        self.run()

    def run(self):
        pass

    def batch_commands(self):
        with open('batch_commands.json', 'r') as f:
            self.commands = json.load(f)