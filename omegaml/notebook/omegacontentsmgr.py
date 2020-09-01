import mimetypes
from base64 import encodebytes, decodebytes

import json
import nbformat
import os
from datetime import datetime
from io import BytesIO
from notebook.base.handlers import HTTPError
from notebook.services.contents.manager import ContentsManager
from tornado import web
from urllib.parse import unquote

from omegaml.notebook.checkpoints import NoOpCheckpoints


class OmegaStoreContentsManager(ContentsManager):
    """
    Jupyter notebook storage manager for omegaml

    Adopted from notebook/services/contents/filemanager.py

    This requires a properly configured omegaml instance.
    see http://jupyter-notebook.readthedocs.io/en/stable/extending/contents.html
    """

    def __init__(self, **kwargs):
        # pass omega= for testing purpose
        self._omega = kwargs.pop('omega', None)
        super(OmegaStoreContentsManager, self).__init__(**kwargs)

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
        self._omega.jobs._include_dir_placeholder = True
        return self._omega

    @property
    def store(self):
        """
        return the OmageStore for jobs (notebooks)
        """
        return self.omega.jobs.store

    @property
    def _dir_placeholder(self):
        return self.omega.jobs._dir_placeholder

    def get(self, path, content=True, type=None, format=None):
        """
        get an entry in the store

        this is called by the contents engine to get the contents of the jobs
        store.
        """
        path = unquote(path).strip('/')
        if type == 'notebook' or (type is None and path.endswith('.ipynb')):
            model = self._notebook_model(path, content=content)
        elif type == 'file':
            model = self._file_model(path, content=content)
        elif type in (None, 'directory'):
            # jupyterlab passes None to get directory
            # we never return content with a directory listing to save time
            # the frontend will request the specific contents
            model = self._dir_model(path, content=False)
        else:
            raise web.HTTPError(404, u'Type {} at {} is not supported'.format(type, path))
        return model

    def save(self, model, path):
        """
        save an entry in the store

        this is called by the contents engine to store a notebook
        """
        om = self.omega
        path = unquote(path).strip('/')
        type = model.get('type')
        name = model.get('name')
        self.run_pre_save_hook(model=model, path=path)
        if type is None:
            raise web.HTTPError(400, u'No file type provided')
        try:
            if type == 'notebook' or (type == 'file' and path.endswith('.ipynb')):
                content = model.get('content')
                # parse input
                if model.get('format') == 'text' and isinstance(content, bytes):
                    content = content.decode('utf8')
                elif model.get('format') == 'base64':
                    if isinstance(content, str):
                        content = content.encode('ascii')
                    content = decodebytes(content).decode('utf8')
                while isinstance(content, str):
                    content = json.loads(content)
                    model['content'] = content
                    model['format'] = None
                if content is None or not isinstance(content, dict):
                    raise web.HTTPError(400, u'No file content provided or wrong format')
                # create notebook
                nb = nbformat.from_dict(content)
                self.check_and_sign(nb, path)
                self.omega.jobs.put(nb, path)
                self.validate_notebook_model(model)
                validation_message = model.get('message', None)
                model = self.get(path, content=False, type=type)
                if validation_message:
                    model['message'] = validation_message
            elif type == 'directory':
                ph_name = '{path}/{self._dir_placeholder}'.format(**locals()).strip('/')
                self.omega.jobs.create("#placeholder", ph_name)
                model = self.get(path, content=False, type=type)
                model['content'] = None
                model['format'] = None
                validation_message = None
            elif type == 'file':
                content = model.get('content')
                fmt = model.get('format')
                self._save_file(path, content, fmt)
                model = self.get(path, content=False, type=type)
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
        return model

    def delete_file(self, path):
        """
        delete an entry

        this is called by the contents engine to delete an entry
        """
        path = unquote(path).strip('/')
        try:
            self.omega.jobs.drop(path)
        except Exception as e:
            self.omega.jobs.drop(path + '/' + self._dir_placeholder)

    def rename_file(self, old_path, new_path):
        """
        rename a file

        this is called by the contents engine to rename an entry
        """
        old_path = unquote(old_path).strip('/')
        new_path = unquote(new_path).strip('/')
        # check file or directory
        if self.file_exists(new_path):
            raise web.HTTPError(409, u'Notebook already exists: %s' % new_path)
        elif self.dir_exists(new_path):
            raise web.HTTPError(409, u'Directory already exists: %s' % new_path)
        # do the renaming
        if self.dir_exists(old_path):
            old_dirname = old_path + '/' + self._dir_placeholder
            new_dirname = new_path + '/' + self._dir_placeholder
            meta = self.omega.jobs.metadata(old_dirname)
            meta.name = new_dirname
        elif self.file_exists(old_path):
            meta = self.omega.jobs.metadata(old_path)
            meta.name = new_path
        # rename on metadata. Note the gridfile instance stays the same
        meta.save()

    def exists(self, path):
        """
        Does a file or dir exist at the given collection in gridFS?
        We do not have dir so dir_exists returns true.

        :param path: (str) The relative path to the file's directory
          (with '/' as separator)
        :returns exists: (boo) The relative path to the file's directory (with '/' as separator)
        """
        path = unquote(path).strip('/')
        return self.file_exists(path) or self.dir_exists(path)

    def dir_exists(self, path=''):
        """check if directory exists

        Args:
            path: name of directory

        Returns:
            True if directory exists
        """
        path = unquote(path).strip('/')
        if path == '':
            return True
        pattern = r'^{path}.*/({placeholder}|.+)'.format(path=path, placeholder=self._dir_placeholder)
        return len(self.omega.jobs.list(regexp=pattern)) > 0

    def file_exists(self, path):
        """check if file exists

        Args:
            path: name of file

        Returns:
            True if file exists
        """
        path = unquote(path).strip('/')
        if not path:
            return False
        # always check for an actual file, not some sub path
        pattern = r'^{}$'.format(path)
        does_exist = len(self.omega.jobs.list(regexp=pattern)) > 0
        does_exist |= len(self.omega.datasets.list(regexp=pattern)) > 0
        return does_exist

    def is_hidden(self, path):
        """check if path or file is hidden

        Args:
            path: name of file or path

        Returns:
            False, currently always returns false
        """
        return False

    def _read_notebook(self, path, as_version=None):
        path = unquote(path).strip('/')
        return self.omega.jobs.get(path)

    def _notebook_model(self, path, content=True, meta=None):
        """
        Build a notebook model
        if content is requested, the notebook content will be populated
        as a JSON structure (not double-serialized)
        """
        path = unquote(path).strip('/')
        model = self._base_model(path)
        model['type'] = 'notebook'
        # always add accurate created and modified
        meta = meta or self.omega.jobs.metadata(path)
        if meta is not None:
            model['created'] = meta.created
            model['last_modified'] = meta.modified
        if content:
            nb = self._read_notebook(path, as_version=4)
            if nb is None:
                raise HTTPError(400, "Cannot read non-file {}".format(path))
            self.mark_trusted_cells(nb, path)
            model['content'] = nb
            model['format'] = 'json'
            self.validate_notebook_model(model)
        return model

    def _base_model(self, path, kind=None):
        """Build the common base of a contents model"""
        # http://jupyter-notebook.readthedocs.io/en/stable/extending/contents.html
        path = unquote(path).strip('/')
        last_modified = datetime.utcnow()
        created = last_modified
        # Create the base model.
        model = {}
        model['name'] = os.path.basename(path)
        model['path'] = path
        model['last_modified'] = last_modified
        model['created'] = created
        model['content'] = None
        model['format'] = None
        model['mimetype'] = None
        model['writable'] = True
        if kind:
            model['type'] = kind
            model['content'] = [] if kind == 'directory' else None
        return model

    def _dir_model(self, path, content=True):
        """
        Build a model to return all of the files in gridfs
        if content is requested, will include a listing of the directory
        """
        # this looks like a seemingly simple task, it's carefully crafted
        path = unquote(path).strip('/')
        model = self._base_model(path, kind='directory')
        model['format'] = 'json'
        contents = model['content']
        # get existing entries from a pattern that matches either
        #    top-level files: ([\w -]+\.[\w -]*)
        #    directories (files in): ([\w ]+/([\w ]+\.[\w]*))
        # does not work:
        #    pattern = r'([\w ]+/_placeholder\.[\w]*)|([\w ]+\.[\w]*)$'
        #    it is too restrictive as entries can be generated without a placeholder
        # so we get all, which may include sub/sub/file
        # and we need to include them because we need to find sub/sub directories
        # note \w is any word character (letter, digit, underscore)
        #      \s is any white space
        #      \d is any digit
        #      :_  match literally
        #      [^\/]  matches any character except /
        #pattern = r'([\w\s\-.\d:()+]+\/)?([\w\s\-.\d:()+]+\.[\w]*)$'
        pattern = r'([^\/]+\/)?([^\/]+\.[^\/]*)$'
        # if we're looking in an existing directory, prepend that
        if path:
            pattern = r'{path}/{pattern}'.format(path=path, pattern=pattern)
        pattern = r'^{}'.format(pattern)
        entries = self.omega.jobs.list(regexp=pattern, raw=True)
        if path and not entries:
            raise HTTPError(400, "Directory not found {}".format(path))
        # by default assume the current path is listed already
        directories = [path]
        for meta in entries:
            # get path of entry, e.g. sub/foo.ipynb => sub
            entry_path = os.path.dirname(meta.name)
            # if not part of listed directories yet, include
            if entry_path not in directories:
                entry = self._base_model(entry_path, kind='directory')
                contents.append(entry)
                directories.append(entry_path)
            # ignore placeholder files
            if meta.name.endswith(self._dir_placeholder):
                continue
            # only include files that are in the path we're listing
            if entry_path != path:
                continue
            # include the actual file
            try:
                entry = self._notebook_model(meta.name, content=content, meta=meta)
            except Exception as e:
                msg = ('_dir_model error, cannot get {}, '
                       'removing from list, exception {}'.format(meta.name, str(e)))
                self.log.warning(msg)
            else:
                contents.append(entry)
        return model

    def _file_model(self, path, content=True, format=None):
        model = self._base_model(path)
        model['type'] = 'file'

        model['mimetype'] = mimetypes.guess_type(path)[0]

        if content:
            content, format = self._read_file(path, format)
            if model['mimetype'] is None:
                default_mime = {
                    'text': 'text/plain',
                    'base64': 'application/octet-stream'
                }[format]
                model['mimetype'] = default_mime

            model.update(
                content=content,
                format=format,
            )

        return model

    def _read_file(self, os_path, format):
        """Read a non-notebook file.

        os_path: The path to be read.
        format:
          If 'text', the contents will be decoded as UTF-8.
          If 'base64', the raw bytes contents will be encoded as base64.
          If not specified, try to decode as UTF-8, and fall back to base64
        """
        if os_path.endswith('.ipynb'):
            meta = self.omega.jobs.metadata(os_path)
        else:
            meta = self.omega.datasets.metadata(os_path)
        if meta is None or meta.gridfile is None:
            raise HTTPError(400, "Cannot read non-file %s" % os_path)

        if meta.gridfile:
            bcontent = meta.gridfile.read()
            meta.gridfile.close()

        if format is None or format == 'text':
            # Try to interpret as unicode if format is unknown or if unicode
            # was explicitly requested.
            try:
                return bcontent.decode('utf8'), 'text'
            except UnicodeError:
                if format == 'text':
                    raise HTTPError(
                        400,
                        "%s is not UTF-8 encoded" % os_path,
                        reason='bad format',
                    )
        return encodebytes(bcontent).decode('ascii'), 'base64'

    def _save_file(self, os_path, content, format):
        """Save content of a generic file."""
        if format not in {'text', 'base64'}:
            raise HTTPError(
                400,
                "Must specify format of file contents as 'text' or 'base64'",
            )
        try:
            if format == 'text':
                bcontent = content.encode('utf8')
            else:
                b64_bytes = content.encode('ascii')
                bcontent = decodebytes(b64_bytes)
        except Exception as e:
            raise HTTPError(
                400, u'Encoding error saving %s: %s' % (os_path, e)
            )

        self.omega.datasets.put(BytesIO(bcontent), os_path)
