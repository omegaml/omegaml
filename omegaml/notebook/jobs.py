from __future__ import absolute_import

import datetime
import re
from uuid import uuid4

import gridfs
import yaml
from croniter import croniter
from mongoengine.fields import GridFSProxy
from nbconvert.preprocessors.execute import ExecutePreprocessor
from nbformat import read as nbread, write as nbwrite, v4 as nbv4
from six import StringIO, BytesIO

from omegaml.documents import Metadata
from omegaml.notebook.tasks import run_omegaml_job
from omegaml.store import OmegaStore
from omegaml.util import settings as omega_settings


class OmegaJobs(object):
    """
    Omega Jobs API
    """

    # TODO this class should be a proper backend class with a mixin for ipynb

    _nb_config_magic = 'omega-ml'
    _dir_placeholder = '_placeholder.ipynb'

    def __init__(self, prefix=None, store=None, defaults=None):
        self.defaults = defaults or omega_settings()
        prefix = prefix or 'jobs'
        self.store = store or OmegaStore(prefix=prefix)
        self.kind = Metadata.OMEGAML_JOBS
        self._include_dir_placeholder = True

    def __repr__(self):
        return 'OmegaJobs(store={})'.format(self.store.__repr__())

    @property
    def _db(self):
        return self.store.mongodb

    @property
    def _fs(self):
        return self.store.fs

    def collection(self, name):
        if not name.endswith('.ipynb'):
            name += '.ipynb'
        return self.store.collection(name)

    def drop(self, name, force=False):
        meta = self.metadata(name)
        name = meta.name # ensure we get the actual name
        return self.store.drop(name, force=force)

    def metadata(self, name):
        meta = self.store.metadata(name)
        if meta is None and not name.endswith('.ipynb'):
            name += '.ipynb'
            meta = self.store.metadata(name)
        return meta

    def exists(self, name):
        return len(self.store.list(name)) + len(self.store.list(name + '.ipynb')) > 0

    def put(self, obj, name, attributes=None):
        """
        Store a NotebookNode

        :param obj: the NotebookNode to store
        :param name: the name of the notebook
        """
        if not name.endswith('.ipynb'):
            name += '.ipynb'
        sbuf = StringIO()
        bbuf = BytesIO()
        # nbwrite expects string, fs.put expects bytes
        nbwrite(obj, sbuf, version=4)
        sbuf.seek(0)
        bbuf.write(sbuf.getvalue().encode('utf8'))
        bbuf.seek(0)
        # see if we have a file already, if so replace the gridfile
        meta = self.store.metadata(name)
        if not meta:
            filename = uuid4().hex
            fileid = self._fs.put(bbuf, filename=filename)
            meta = self.store._make_metadata(name=name,
                                             prefix=self.store.prefix,
                                             bucket=self.store.bucket,
                                             kind=self.kind,
                                             attributes=attributes,
                                             gridfile=GridFSProxy(grid_id=fileid))
            meta = meta.save()
        else:
            filename = uuid4().hex
            meta.gridfile.delete()
            fileid = self._fs.put(bbuf, filename=filename)
            meta.gridfile = GridFSProxy(grid_id=fileid)
            meta = meta.save()
        # set config
        nb_config = self.get_notebook_config(name)
        meta_config = meta.attributes.get('config', {})
        if nb_config:
            meta_config.update(dict(**nb_config))
            meta.attributes['config'] = meta_config
        meta = meta.save()
        if 'run-at' in meta_config:
            meta = self.schedule(name)
        return meta

    def get(self, name):
        """
        Retrieve a notebook and return a NotebookNode
        """
        if not name.endswith('.ipynb'):
            name += '.ipynb'
        meta = self.store.metadata(name)
        if meta:
            try:
                outf = meta.gridfile
            except gridfs.errors.NoFile as e:
                raise e
            # nbwrite wants a string, outf is bytes
            sbuf = StringIO()
            data = outf.read()
            if data is None:
                msg = 'Expected content in {name}, got None'.format(**locals())
                raise ValueError(msg)
            sbuf.write(data.decode('utf8'))
            sbuf.seek(0)
            nb = nbread(sbuf, as_version=4)
            return nb
        else:
            raise gridfs.errors.NoFile(
                ">{0}< does not exist in jobs bucket '{1}'".format(
                    name, self.store.bucket))

    def create(self, code, name):
        """
        create a notebook from code

        :param code: the code as a string
        :param name: the name of the job to create
        :return: the metadata object created
        """
        cells = []
        cells.append(nbv4.new_code_cell(source=code))
        notebook = nbv4.new_notebook(cells=cells)
        # put the notebook
        meta = self.put(notebook, name)
        return meta

    def get_fs(self, collection=None):
        # legacy support
        return self._fs

    def get_collection(self, collection):
        """
        returns the collection object
        """
        # FIXME this should use store.collection
        return getattr(self.store.mongodb, collection)

    def list(self, jobfilter='.*', raw=False):
        """
        list all jobs matching filter.
        filter is a regex on the name of the ipynb entry.
        The default is all, i.e. `.*`
        """
        job_list = self.store.list(regexp=jobfilter, raw=raw)
        name = lambda v: v.name if raw else v
        if not self._include_dir_placeholder:
            job_list = [v for v in job_list if not name(v).endswith(self._dir_placeholder)]
        return job_list

    def get_notebook_config(self, nb_filename):
        """
        returns the omegaml script config on
        the notebook's first cell

        If there is no config cell or the config cell is invalid raises
        a ValueError
        """
        notebook = self.get(nb_filename)
        config_cell = None
        config_magic = '# {}'.format(self._nb_config_magic)
        for cell in notebook.get('cells'):
            if cell.source.startswith(config_magic):
                config_cell = cell
        if not config_cell:
            return {}
        yaml_conf = '\n'.join(
            [re.sub('#', '', x, 1) for x in str(
                config_cell.source).splitlines()])
        try:
            yaml_conf = yaml.safe_load(yaml_conf)
            config = yaml_conf[self._nb_config_magic] # assert the key is in
        except Exception:
            raise ValueError(
                'Notebook configuration cannot be parsed')
        return config

    def run(self, name):
        """
        Run a job immediately

        The job is run and the results are stored in the given filename

        :param name: the name of the jobfile
        :return: the metadata of the job
        """
        return self.run_notebook(name)

    def run_notebook(self, name, event=None):
        """
        run a given notebook immediately.
        the job parameter is the name of the job script as in ipynb.
        Inserts and returns the Metadata document for the job.
        """
        notebook = self.get(name)
        meta_job = self.metadata(name)
        ts = datetime.datetime.now()
        # execute
        try:
            ep = ExecutePreprocessor()
            ep.preprocess(notebook, {'metadata': {'path': '/'}})
        except Exception as e:
            status = 'ERROR'
            message = str(e)
        else:
            status = 'OK'
            message = ''
            # record results
            meta_results = self.put(
                notebook, 'results/{name}_{ts}'.format(**locals()))
            meta_results.attributes['source_job'] = name
            meta_results.save()
            job_results = meta_job.attributes.get('job_results', [])
            job_results.append(meta_results.name)
            meta_job.attributes['job_results'] = job_results
        # record final job status
        job_runs = meta_job.attributes.get('job_runs', [])
        runstate = {
            'status': status,
            'ts': ts,
            'message': message,
            'results': meta_results.name if status == 'OK' else None
        }
        job_runs.append(runstate)
        meta_job.attributes['job_runs'] = job_runs
        # set event run state if event was specified
        if event:
            attrs = meta_job.attributes
            triggers = attrs['triggers'] = attrs.get('triggers', [])
            scheduled = (trigger for trigger in triggers
                         if trigger['event-kind'] == 'scheduled')
            for trigger in scheduled:
                if event == trigger['event']:
                    trigger['status'] = status
                    trigger['ts'] = ts
        return meta_job.save()

    def schedule(self, nb_file, run_at=None, last_run=None):
        """
        Schedule a processing of a notebook as per the interval
        specified on the job script
        """
        meta = self.metadata(nb_file)
        attrs = meta.attributes
        # get/set run-at spec
        config = attrs.get('config')
        # if we don't have any run-spec, stop
        if not run_at:
            interval = config.get('run-at')
        else:
            config['run-at'] = run_at
            interval = run_at
        if not interval:
            # if we don't have a run-spec, return without scheduling
            raise ValueError('no run-at specification provided, cannot schedule')
        # get last time the job was run
        if last_run is None:
            job_runs = attrs.get('job_runs')
            if job_runs:
                last_run = job_runs[-1]['ts']
            else:
                last_run = datetime.datetime.now()
        # calculate next run time
        iter_next = croniter(interval, last_run)
        run_at = iter_next.get_next(datetime.datetime)
        # store next scheduled run
        triggers = attrs['triggers'] = attrs.get('triggers', [])
        # set up a schedule event
        scheduled_run = {
            'event-kind': 'scheduled',
            'event': run_at.isoformat(),
            'run-at': run_at,
            'status': 'PENDING'
        }
        triggers.append(scheduled_run)
        return meta.save()
