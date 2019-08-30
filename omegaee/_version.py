import os

base_path = os.path.join(os.path.dirname(__file__), 'VERSION')
with open(base_path) as rin:
    version = rin.read().split('\n')[0]

base_path = os.path.join(os.path.dirname(__file__), 'RELEASE')
with open(base_path) as rin:
    release = rin.read().split('\n')[0]

