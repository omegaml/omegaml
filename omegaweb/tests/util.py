import json


def assertDictEqualJSON(self, d, filename):
    with open(filename, 'r') as fin:
        self.assertDictEqual(d, json.load(fin))
