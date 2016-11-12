# Configuration file for ipython-notebook.
from __future__ import absolute_import
import os
c = get_config()
# Notebook config
c.NotebookApp.open_browser = False
# It is a good idea to put it on a known, fixed port
c.NotebookApp.port = 8888
c.NotebookApp.contents_manager_class='ipynbstore_gridfs.GridFSContentsManager'
c.NotebookApp.GridFSContentsManager.mongo_uri=os.environ.get('OMEGA_MONGO_URL', 'mongodb://localhost:27017/omega')