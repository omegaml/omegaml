# this will be executed on jupyter notebook / ipython startup
import sys
import os
base_dir = os.environ.get('OMEGA_ROOT')
if not base_dir:
    base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, base_dir)
import omegaml as om
print("omegaml initializing from {}".format(__file__))
print(om.defaults.OMEGA_CONFIG_FILE)
