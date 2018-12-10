import os
from logging import warning

from IPython.utils import tz
import nbformat
from notebook.services.contents.manager import ContentsManager
from tornado import web

from omegaml.notebook.checkpoints import NoOpCheckpoints


class OmegaStoreContentsManager(ContentsManager):
    """
    Jupyter notebook storage manager for omegaml

    This requires a properly configured omegaml instance.

    see http://jupyter-notebook.readthedocs.io/en/stable/extending/contents.html
    """

    def __init__(self, **kwargs):
        super(OmegaStoreContentsManager, self).__init__(**kwargs)
        self._omega = None

    def _checkpoints_class_default(self):
        return NoOpCheckpoints

    @property
    def omega(self):
        """
        return the omega instance used by the contents manager
        """
        if self._omega is None:
            import omegaml as om
            self._omega = om
        return self._omega

    @property
    def store(self):
        """
        return the OmageStore for jobs (notebooks)
        """
        return self.omega.jobs.store

    def get(self, path, content=True, type=None, format=None):
        """
        get an entry in the store

        this is called by the contents engine to get the contents of the jobs
        store.
        """
        path = path.strip('/')
        if not self.exists(path):
            raise web.HTTPError(404, u'No such file or directorys: %s' % path)

        if path == '':
            if type not in (None, 'directory'):
                raise web.HTTPError(400, u'%s is a directory, not a %s' % (
                    path, type), reason='bad type')
            model = self._dir_model(path, content=content)
        elif type == 'notebook' or (type is None and path.endswith('.ipynb')):
            model = self._notebook_model(path, content=content)
        else:
            raise web.HTTPError(400, u'%s is not a directory' % path,
                                reason='bad type')
        return model

    def save(self, model, path):
        """
        save an entry in the store

        this is called by the contents engine to store a notebook
        """
        path = path.strip('/')
        if 'type' not in model:
            raise web.HTTPError(400, u'No file type provided')
        if 'content' not in model and model['type'] != 'directory':
            raise web.HTTPError(400, u'No file content provided')

        self.run_pre_save_hook(model=model, path=path)
        om = self.omega

        try:
            if model['type'] == 'notebook':
                nb = nbformat.from_dict(model['content'])
                self.check_and_sign(nb, path)
                self.omega.jobs.put(nb, path)
            else:
                raise web.HTTPError(
                    400, "Unhandled contents type: %s" % model['type'])
        except web.HTTPError:
            raise
        except Exception as e:
            self.log.error(
                u'Error while saving file: %s %s', path, e, exc_info=True)
            raise web.HTTPError(
                500, u'Unexpected error while saving file: %s %s' % (path, e))

        validation_message = None
        if model['type'] == 'notebook':
            self.validate_notebook_model(model)
            validation_message = model.get('message', None)

        model = self.get(path, content=False)
        if validation_message:
            model['message'] = validation_message

        return model

    def delete_file(self, path):
        """
        delete an entry

        this is called by the contents engine to delete an entry
        """
        path = path.strip('/')
        self.omega.jobs.drop(path)

    def rename_file(self, old_path, new_path):
        """
        rename a file 

        this is called by the contents engine to rename an entry
        """
        old_path = old_path.strip('/')
        new_path = new_path.strip('/')
        if self.file_exists(new_path):
            raise web.HTTPError(409, u'Notebook already exists: %s' % new_path)
        # rename on metadata. Note the gridfile instance stays the same
        meta = self.omega.jobs.metadata(old_path)
        meta.name = new_path
        meta.save()

    def exists(self, path):
        """
        Does a file or dir exist at the given collection in gridFS?
        We do not have dir so dir_exists returns true.

        :param path: (str) The relative path to the file's directory 
          (with '/' as separator)
        :returns exists: (boo) The relative path to the file's directory (with '/' as separator)
        """
        path = path.strip('/')
        return self.file_exists(path) or self.dir_exists(path)

    def dir_exists(self, path=''):
        path = path.strip('/')
        if path == '':
            return True
        return len(self.omega.jobs.list('{path}.*'.format(path=path))) > 0

    def file_exists(self, path):
        path = path.strip('/')
        return path in self.omega.jobs.list(path)

    def is_hidden(self, path):
        return False

    def _read_notebook(self, path, as_version=None):
        path = path.strip('/')
        return self.omega.jobs.get(path)

    def _notebook_model(self, path, content=True):
        """
        Build a notebook model
        if content is requested, the notebook content will be populated
        as a JSON structure (not double-serialized)
        """
        path = path.strip('/')
        model = self._base_model(path)
        model['type'] = 'notebook'
        if content:
            nb = self._read_notebook(path, as_version=4)
            self.mark_trusted_cells(nb, path)
            model['content'] = nb
            model['format'] = 'json'
            self.validate_notebook_model(model)
        # if exists already fake last modified and created timestamps
        # otherwise jupyter notebook will claim a newer version "on disk"
        if self.exists(path):
            model['last_modified'] = tz.datetime(1970, 1, 1)
            model['created'] = tz.datetime(1970, 1, 1)
        return model

    def _base_model(self, path):
        """Build the common base of a contents model"""
        # http://jupyter-notebook.readthedocs.io/en/stable/extending/contents.html
        path = path.strip('/')
        last_modified = tz.utcnow()
        created = tz.utcnow()
        # Create the base model.
        model = {}
        model['name'] = path.rsplit('/', 1)[-1]
        model['path'] = path
        model['last_modified'] = last_modified
        model['created'] = created
        model['content'] = None
        model['format'] = None
        model['mimetype'] = None
        model['writable'] = True
        return model

    def _dir_model(self, path, content=True):
        """
        Build a model to return all of the files in gridfs
        if content is requested, will include a listing of the directory
        """
        path = path.strip('/')
        model = self._base_model(path)
        model['type'] = 'directory'
        model['content'] = contents = []
        entries = self.omega.jobs.list('{path}.*'.format(path=path), raw=True)
        for meta in entries:
            try:
                entry = self.get(meta.name, content=content)
            except:
                msg = ('_dir_model error, cannot get {}, '
                       'removing from list'.format(meta.name))
                self.log.warning(msg)
            else:
                contents.append(entry)
        model['format'] = 'json'
        return model
