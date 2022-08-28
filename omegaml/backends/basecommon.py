import os
from mongoengine import GridFSProxy
from warnings import warn


class BackendBaseCommon:
    """
    common base for storage backends
    """
    def _tmp_packagefn(self, store, name):
        """
        use this to to get a temporary local filename for serialization/deserialization

        This uses the store's .tmppath to generate a valid fully qualified path, ensuring
        the directory exists. Note that you must clean up files yourself after use, i.e.
        call os.remove()

        Args:
            store (OmegaStore): the store to get the temporary path
            name (str): the name of the file

        Returns:
            filename (str)

        TODO: register all files to remove temp files on process exit
        """
        filename = os.path.join(store.tmppath, name)
        dirname = os.path.dirname(filename)
        os.makedirs(dirname, exist_ok=True)
        return filename

    def _is_path(self, obj):
        return isinstance(obj, str) and os.path.exists(obj)

    def _store_to_file(self, store, obj, filename, encoding=None, replace=False):
        """
        Use this method to store file-like objects to the store's gridfs

        Args:
            store (OmegaStore): the store whose .fs filesystem access will be used
            obj (file-like): a file-like object or path, if path will be opened with mode=rb,
               otherwise its obj.read() method is called to get the data as a byte stream
            filename (path): the path in the store (key)
            encoding (str): a valid encoding such as utf8, optional
            replace (bool): if True the existing file(s) of the same name are deleted to avoid automated versioning
               by gridfs. defaults to False

        Returns:
            gridfile (GridFSProxy), assignable to Metadata.gridfile
        """
        if replace:
            for fileobj in store.fs.find({'filename': filename}):
                try:
                    store.fs.delete(fileobj._id)
                except Exception as e:
                    warn('deleting {filename} resulted in {e}'.format(**locals()))
                    pass
        if self._is_path(obj):
            with open(obj, 'rb') as fin:
                fileid = store.fs.put(fin, filename=filename, encoding=encoding)
        else:
            fileid = store.fs.put(obj, filename=filename, encoding=encoding)
        gridfile = GridFSProxy(grid_id=fileid,
                               db_alias=store._dbalias,
                               key=filename,
                               collection_name=store._fs_collection)
        return gridfile

    def perform(self, method, *args, **kwargs):
        """ perform a model action, wrapped by pre-action/post-action calls

        This is a helper method for the OmegaRuntime tasks to call model
        actions that require pre/post processing. The pre/post action methods
        are looked up on Backend.model_store, enabling mixins to the model store
        to handle such calls.

        Notes:

            - see the ModelSignatureMixin for pre/post action methods on fit()
              and predict()
        """
        pre_nop = lambda *args, **kwargs: (args, kwargs)
        post_nop = lambda v, *args, **kwargs: v
        do_call = getattr(self, method, None)
        pre_call = getattr(self._call_handler, f'_pre_{method}', pre_nop)
        post_call = getattr(self._call_handler, f'_post_{method}', post_nop)
        common_kwargs = dict(data_store=getattr(self, 'data_store'),
                             model_store=getattr(self, 'model_store'))
        args, kwargs = pre_call(*args, **kwargs)
        result = do_call(*args, **kwargs)
        return post_call(result, *args, **kwargs, **common_kwargs)

    @property
    def _call_handler(self):
        # by default the data store handles _pre and _post methods in self.perform()
        return self.data_store


