from os.path import dirname, basename

import os

from omegaml.backends.basedata import BaseDataBackend

try:
    from smart_open import open
except:
    pass


class PythonRawFileBackend(BaseDataBackend):
    """
    OmegaStore backend to support arbitrary files
    """
    KIND = 'python.file'

    @classmethod
    def supports(self, obj, name, open_kwargs=None, **kwargs):
        is_filelike = hasattr(obj, 'read')
        open_kwargs = dict(open_kwargs or {})
        if kwargs.get('kind') == self.KIND:
            is_filelike = self._is_openable(obj, **open_kwargs)
        return is_filelike or self._is_path(self, obj)

    def _is_openable(self, obj, **kwargs):
        if 'mode' not in 'kwargs':
            kwargs['mode'] = 'rb'
        try:
            with open(obj, **kwargs) as fin:
                fin.read(1)
        except:
            return False
        return True

    def get(self, name, local=None, mode='wb', open_kwargs=None, **kwargs):
        """
        get a stored file as a file-like object with binary contents or a local file

        Args:
            name (str): the name of the file
            local (str): if set the local path will be created and the file
               stored there. If local does not have an extension it is assumed
               to be a directory name, in which case the file is stored as the
               same name.
            mode (str): the mode to use on .open() for the local file
            open_kwargs (dict): the kwargs to use .open() for the local file
            **kwargs: any kwargs passed to datasets.metadata()

        Returns:
            the file-like output handler (local is None)
            the path to the local file (local is given)

        See also:
            https://docs.python.org/3/glossary.html#term-file-object
            https://docs.python.org/3/glossary.html#term-binary-file
        """
        outf = self.data_store.metadata(name, **kwargs).gridfile
        if local:
            is_filename = '.' in basename(local)
            target_dir = dirname(local) if is_filename else local
            local = local if is_filename else '{local}/{name}'.format(**locals())
            os.makedirs(target_dir, exist_ok=True)
            with open(local, mode=mode, **open_kwargs) as flocal:
                flocal.write(outf.read())
            return local
        return filelike(outf)

    def put(self, obj, name, attributes=None, encoding=None, **kwargs):
        self.data_store.drop(name, force=True)
        storekey = self.data_store.object_store_key(name, 'file', hashed=True)
        gridfile = self._store_to_file(self.data_store, obj, storekey, encoding=encoding)
        return self.data_store._make_metadata(
            name=name,
            prefix=self.data_store.prefix,
            bucket=self.data_store.bucket,
            kind=self.KIND,
            attributes=attributes,
            gridfile=gridfile).save()


def filelike(obj):
    actual = obj.get()
    __doc__ = actual.__doc__
    return actual
