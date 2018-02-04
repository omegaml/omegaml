# this will be executed on jupyter notebook / ipython startup
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import omegaml as om