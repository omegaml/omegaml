from __future__ import absolute_import

import datetime
import gridfs
import re
import six
import yaml
from croniter import croniter
from nbconvert.preprocessors import ClearOutputPreprocessor
from nbconvert.preprocessors.execute import ExecutePreprocessor
from nbformat import read as nbread, write as nbwrite, v4 as nbv4
from six import StringIO, BytesIO
from uuid import uuid4

from omegaml.backends.basecommon import BackendBaseCommon
from omegaml.documents import MDREGISTRY
from omegaml.notebook.jobschedule import JobSchedule
from omegaml.store import OmegaStore
from omegaml.util import settings as omega_settings


class OmegaJobs(BackendBaseCommon):
    """
    Omega Jobs API
    """

    # TODO this class should be a proper backend class with a mixin for ipynb

    _nb_config_magic = 'omega-ml', 'schedule', 'run-at', 'cron'
    _dir_placeholder = '_placeholder.ipynb'

    def __init__(self, bucket=None, prefix=None, store=None, defaults=None):
        self.defaults = defaults or omega_settings()
        self.prefix = prefix or (store.prefix if store else None) or 'jobs'
        self.store = store or OmegaStore(prefix=prefix, bucket=bucket, defaults=defaults)
        self.kind = MDREGISTRY.OMEGAML_JOBS
        self._include_dir_placeholder = True
        # convenience so you can do om.jobs.schedule(..., run_at=om.jobs.Schedule(....))
        self.Schedule = JobSchedule

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
        name = meta.name if meta is not None else name
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
            fileid = self._store_to_file(self.store, bbuf, filename)
            meta = self.store._make_metadata(name=name,
                                             prefix=self.store.prefix,
                                             bucket=self.store.bucket,
                                             kind=self.kind,
                                             attributes=attributes,
                                             gridfile=fileid)
            meta = meta.save()
        else:
            filename = uuid4().hex
            meta.gridfile = self._store_to_file(self.store, bbuf, filename)
            meta = meta.save()
        # set config
        nb_config = self.get_notebook_config(name)
        meta_config = meta.attributes.get('config', {})
        if nb_config:
            meta_config.update(dict(**nb_config))
            meta.attributes['config'] = meta_config
        meta = meta.save()
        if not name.startswith('results') and ('run-at' in meta_config):
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

    def list(self, pattern=None, regexp=None, raw=False, **kwargs):
        """
        list all jobs matching filter.
        filter is a regex on the name of the ipynb entry.
        The default is all, i.e. `.*`
        """
        job_list = self.store.list(pattern=pattern, regexp=regexp, raw=raw, **kwargs)
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
        config_magic = ['# {}'.format(kw) for kw in self._nb_config_magic]
        for cell in notebook.get('cells'):
            if any(cell.source.startswith(kw) for kw in config_magic):
                config_cell = cell
        if not config_cell:
            return {}
        yaml_conf = '\n'.join(
            [re.sub('#', '', x, 1) for x in str(
                config_cell.source).splitlines()])
        try:
            yaml_conf = yaml.safe_load(yaml_conf)
            config = yaml_conf.get(self._nb_config_magic[0], yaml_conf)
        except Exception:
            raise ValueError(
                'Notebook configuration cannot be parsed')
        # translate config to canonical form
        # TODO refactor to seperate method / mapped translation functions
        if 'schedule' in config:
            config['run-at'] = JobSchedule(text=config.get('schedule', '')).cron
        if 'cron' in config:
            config['run-at'] = JobSchedule.from_cron(config.get('cron')).cron
        if 'run-at' in config:
            config['run-at'] = JobSchedule.from_cron(config.get('run-at')).cron
        return config

    def run(self, name):
        """
        Run a job immediately

        The job is run and the results are stored in om.jobs('results/name <timestamp>') and
        the result's Metadata is returned.

        Metadata.attributes of the original job as given by name is updated:

        * attributes['job_runs'] (list) - list of status of each run. Status is
             a dict as below
        * attributes['job_results'] (list) - list of results job names in same
             index-order as job_runs

        The status of each job run is a dict with keys:

        * status (str): the status of the job run, OK or ERROR
        * ts (datetime): time of execution
        * message (str): error mesasge in case of ERROR, else blank
        * results (str): name of results in case of OK, else blank

        Usage:
            # directly (sync)
            meta = om.jobs.run('mynb')

            # via runtime (async)
            job = om.runtime.job('mynb')
            result = job.run()

        Args:
            name (str): the name of the jobfile

        Returns:
             Metadata of the results entry
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
        # execute kwargs
        # -- see ExecuteProcessor class
        # -- see https://nbconvert.readthedocs.io/en/latest/execute_api.html
        ep_kwargs = {
            # avoid timeouts to stop kernel
            'timeout': None,
            # avoid kernel at exit functions
            # -- this stops ipykernel AttributeError 'send_multipart'
            'shutdown_kernel': 'immediate',
            # set kernel name, blank is default
            # -- e.g. python3, ir
            # -- see https://stackoverflow.com/a/47053020/890242
            'kernel_name': '',
        }
        # other interesting options
        ep_kwargs.update(meta_job.kind_meta.get('ep_kwargs', {}))
        try:
            if not meta_job.kind_meta.get('keep_output', False):
                resources = {}  # https://nbconvert.readthedocs.io/en/latest/api/preprocessors.html
                cp = ClearOutputPreprocessor()
                cp.preprocess(notebook, resources)
            ep = ExecutePreprocessor(**ep_kwargs)
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
        meta_job.save()
        return meta_results

    def schedule(self, nb_file, run_at=None, last_run=None):
        """
        Schedule a processing of a notebook as per the interval
        specified on the job script
        """
        meta = self.metadata(nb_file)
        attrs = meta.attributes
        # get/set run-at spec
        config = attrs.get('config', {})
        # see what we have as a schedule
        # -- a dictionary of JobSchedule
        if isinstance(run_at, dict):
            run_at = self.Schedule(**run_at).cron
        if isinstance(run_at, str):
            run_at = self.Schedule(run_at).cron
        # -- a JobSchedule
        if isinstance(run_at, self.Schedule):
            run_at = run_at.cron
        # -- nothing, may we have it on the job's config already
        if not run_at:
            interval = config.get('run-at')
        else:
            # store the new schedule
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
                last_run = datetime.datetime.utcnow()
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
        # search for existing trigger, only add if not existing yet
        for cur in triggers:
            if cur.get('status') != 'PENDING':
                continue
            if scheduled_run['run-at'] == cur.get('run-at'):
                break
        else:
            triggers.append(scheduled_run)
        attrs['config'] = config
        return meta.save()

    def get_schedule(self, name, only_pending=False):
        """
        return the cron schedule and corresponding triggers

        Args:
            name (str): the name of the job

        Returns:
            tuple of (run_at, triggers)

            run_at (str): the cron spec, None if not scheduled
            triggers (list): the list of triggers
        """
        meta = self.metadata(name)
        attrs = meta.attributes
        config = attrs.get('config')
        triggers = attrs.get('triggers', [])
        if only_pending:
            triggers = [trigger for trigger in triggers
                        if trigger['status'] == 'PENDING']
        if config and 'run-at' in config:
            run_at = config.get('run-at')
        else:
            run_at = None
        return run_at, triggers

    def drop_schedule(self, name):
        """
        Drop an existing schedule, if any

        This will drop any existing schedule and any pending triggers of
        event-kind 'scheduled'.

        Args:
            name (str): the name of the job

        Returns:
            Metadata
        """
        meta = self.metadata(name)
        attrs = meta.attributes
        config = attrs.get('config')
        triggers = attrs.get('triggers')
        if 'run-at' in config:
            del config['run-at']
        for trigger in triggers:
            if trigger['event-kind'] == 'scheduled' and trigger['status'] == 'PENDING':
                trigger['status'] = 'CANCELLED'
        return meta.save()

    def export(self, name, localpath, format='html'):
        """
        Export a job or result file to HTML

        The job is exported in the given format.

        :param name: the name of the job, as in jobs.get
        :param localpath: the path of the local file to write. If you
           specify an empty path or 'memory' a tuple of (body, resource)
           is returned instead
        :param format: the output format. currently only :code:`'html'` is supported
        :return: the (data, resources) tuple as returned by nbconvert. For
           format html data is the HTML's body, for PDF it is the pdf file contents
        """
        from traitlets.config import Config
        from nbconvert import SlidesExporter
        from nbconvert.exporters.html import HTMLExporter
        from nbconvert.exporters.pdf import PDFExporter

        # https://nbconvert.readthedocs.io/en/latest/nbconvert_library.html
        # (exporter class, filemode, config-values
        EXPORTERS = {
            'html': (HTMLExporter, '', {}),
            'htmlbody': (HTMLExporter, '', {}),
            'pdf': (PDFExporter, 'b', {}),
            'slides': (SlidesExporter, '', {'RevealHelpPreprocessor.url_prefix':
                                                'https://cdnjs.cloudflare.com/ajax/libs/reveal.js/3.6.0/'}),
        }
        # get exporter according to format
        if format not in EXPORTERS:
            raise ValueError('format {} is invalid. Choose one of {}'.format(format, EXPORTERS.keys()))
        exporter_cls, fmode, configkw = EXPORTERS[format]
        # prepare config
        # http://nbconvert.readthedocs.io/en/latest/nbconvert_library.html#Using-different-preprocessors
        c = Config()
        for k, v in six.iteritems(configkw):
            context, key = k.split('.')
            setattr(c[context], key, v)
        # get configured exporter
        exporter = exporter_cls(config=c)
        # get notebook, convert and store in file if requested
        notebook = self.get(name)
        (data, resources) = exporter.from_notebook_node(notebook)
        if localpath and localpath != 'memory':
            with open(localpath, 'w' + fmode) as fout:
                fout.write(data)
        return data, resources
