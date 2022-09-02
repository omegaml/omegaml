import re
from importlib import import_module

from pathlib import Path

def migrate(om):
    for modfile in Path(__file__).parent.glob('*.py'):
        modname = modfile.name.replace('.py', '')
        if not re.match(r'^[0-9]{4}_.*', modname):
            continue
        print(f"running migration {modname}")
        migration = import_module('.' + modname, package=__package__)
        migration.forward(om)
    print(f"Migrations complete.")
