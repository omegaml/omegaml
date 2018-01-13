from __future__ import absolute_import
from six import StringIO
import os

class OmegaFSStorage(object):

    """
    Basic support for omegaml as a django-storage object
    """
    def __init__(self, *args, **kwargs):
        import omegaml as om
        self.datasets = om.datasets

    def listdir(self, path):
        if path.startswith('/'):
            path = path[1:]
        allfiles = self.datasets.list('%s' % path)
        dirs = [os.path.dirname(d) for d in allfiles if '/' in d]
        return dirs, allfiles

    def exists(self, name):
        return name in self.datasets.list()

    def save(self, name, content, max_length=None):
        import pandas as pd
        if not isinstance(content, pd.DataFrame):
            df = pd.read_json(content)
        else:
            df = content
        meta = self.datasets.put(df, name)
        return meta.name

    def delete(self, name):
        self.datasets.drop(name)

    def open(self, name, mode='r'):
        df = self.datasets.get(name)
        return DataFrameFile(df)
