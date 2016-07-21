from StringIO import StringIO


class DataFrameFile(object):
    """
    Simple file-like object for a dataframe. Read-only
    """
    def __init__(self, df):
        self.df = df
    def __enter__(self):
        self.open()
        return self
    def __exit__(self, type, value, traceback):
        self.close()
        return True
    def open(self):
        pass
    def close(self):
        pass
    def read(self):
        return self.df.to_json()


class OmegaFSStorage(object):
    """
    Basic support for omegaml as a django-storage object
    """
    def __init__(self):
        import omegaml as om
        self.datasets = om.datasets

    def listdir(self, path):
        if path.startswith('/'):
            path = path[1:]
        return self.datasets.list('%s' % path)

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
