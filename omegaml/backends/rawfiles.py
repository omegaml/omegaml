from os.path import dirname
from pathlib import Path

import io
import logging
import os
import smart_open
import zipfile

from omegaml.backends.basedata import BaseDataBackend

try:
    from smart_open import open
except:
    pass

logger = logging.getLogger(__name__)


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
            is_filelike |= self._is_openable(self, obj, **open_kwargs)
        return is_filelike or self._is_path(self, obj)

    def _is_openable(self, obj, **kwargs):
        if 'mode' not in 'kwargs':
            kwargs['mode'] = 'rb'
        # already opened file
        if isinstance(obj, io.IOBase):
            return not obj.closed
        try:
            with open(obj, **kwargs) as fin:
                fin.read(1)
        except:
            return False
        return True

    def get(self, name, local=None, mode='wb', open_kwargs=None, chunksize=None, uri=None, extract=None, replace=False,
            **kwargs):
        """
        get a stored file as a file-like object with binary contents or a local file

        Args:
            name (str): the name of the file
            local (str): if set the local path will be created and the file
               stored there. If local does not have an extension it is assumed
               to be a directory name, where the file will stored with /path/to/local/name.
               If the directory does not exist, the directory is created.
            mode (str): the mode to use on .open() for the local file
            chunksize (int): optional, the size of chunks to be read, as in
            open_kwargs (dict): optional, the kwargs to use .open() for the local file
            uri (str): optional, a uri passed to smart_open for the source location of the file.
              If not specified, defaults to metadata.uri, which defaults to metadata.gridfile
            extract (bool): optional, defaults to False. If True and the file is a zipfile, the file will be
              extracted to the local= path. Defaults to True if local is a directory or if
              uri exists as a local path; in this case uri is the local path.
            replace (bool): if True, an existing local file will be overwritten
            **kwargs: any kwargs passed to datasets.metadata()

        Returns:
            the file-like output handler (local is None)
            the path to the local file (local is given)

        See also:
            https://docs.python.org/3/glossary.html#term-file-object
            https://docs.python.org/3/glossary.html#term-binary-file
        """
        meta = self.data_store.metadata(name, **kwargs)
        chunksize = chunksize or 1024 * 1024 * 4
        if uri and Path(uri).parent.exists():
            local = local or uri
            extract = True if extract is None else extract
        else:
            uri = meta.uri
        if uri:
            outf = open(uri, mode='rb')
        else:
            outf = self.data_store.metadata(name, **kwargs).gridfile
        if local:
            is_filename = not Path(local).is_dir() and (Path(local).is_file() or Path(local).suffix != '')
            target_dir = dirname(local) if is_filename and not extract else local
            extract = extract if extract is not None else not is_filename
            as_file_local = '{local}/{name}'.format(**locals()) if not extract else local
            local = local if is_filename else as_file_local
            open_kwargs = open_kwargs or {}
            is_zipfile = zipfile.is_zipfile(outf)
            outf.seek(0)  # ensure we're back to 0 offset after zipfile.is_zipfile()
            if extract and is_zipfile:
                if Path(target_dir).is_file():
                    target_dir = Path(target_dir).with_suffix('.unzipped')
                    local = target_dir
                os.makedirs(target_dir, exist_ok=True)
                with zipfile.ZipFile(outf) as zip:
                    zip.extractall(path=target_dir)
            elif replace or not Path(local).exists():
                with smart_open.open(local, mode=mode, **open_kwargs) as flocal:
                    while data := outf.read(chunksize):
                        flocal.write(data)
            else:
                logger.warning(f'{local} exists already, no data written')
            return Path(local)
        return filelike(outf)

    def put(self, obj, name, attributes=None, encoding=None, uri=None, **kwargs):
        """
        store the binary contents of a file-like object

        Args:
            obj (str|Path|filelike): the object to be stored
            name (str): the name for the object's metadata
            attributes (dict): optional, metadata attributes
            encoding (str): optional, a valid encoding, such as utf8
            uri (str): optional, the local or remote file url compatible with smart_open
            **kwargs:

        Returns:
            Metadata
        """
        self.data_store.drop(name, force=True)
        storekey = self.data_store.object_store_key(name, 'file', hashed=True)
        gridfile = self._store_to_file(self.data_store, obj, storekey, encoding=encoding, uri=uri,
                                       **kwargs)
        return self.data_store._make_metadata(
            name=name,
            prefix=self.data_store.prefix,
            bucket=self.data_store.bucket,
            kind=self.KIND,
            attributes=attributes,
            uri=str(uri or ''),
            gridfile=gridfile).save()


def filelike(obj):
    # convert GridFsProxy to GridOut, a filelike object
    # -- for actual files, returns just the actual file
    actual = obj.get() if hasattr(obj, 'get') else obj
    __doc__ = actual.__doc__
    return actual
