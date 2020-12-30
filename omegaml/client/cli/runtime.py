import os
from pprint import pprint
from time import sleep

from omegaml.client.docoptparser import CommandBase
from omegaml.client.util import get_omega


class RuntimeCommandBase(CommandBase):
    """
    Usage:
      om runtime model <name> <model-action> [<X>] [<Y>] [--result=<output-name>] [--param=<kw=value>]... [--async] [options]
      om runtime script <name> [<script-action>] [<kw=value>...] [--async] [options]
      om runtime job <name> [<job-action>] [<args...>] [--async] [options]
      om runtime result <taskid> [options]
      om runtime ping [options]
      om runtime env <action> [<package>] [--file <requirements.txt>] [--every] [options]
      om runtime log [-f] [options]
      om runtime status [workers|labels|stats] [options]
      om runtime restart app <name> [options]
      om runtime celery [<celery-command>...] [--worker=<worker>] [--queue=<queue>] [--celery-help] [--flags <celery-flags>...] [options]

    Options:
      --async           don't wait for results, will print taskid
      -f                tail log
      --require=VALUE   worker label
      --flags=VALUE     celery flags, list as "--flag VALUE"
      --worker=VALUE    celery worker
      --queue=VALUE     celery queue
      --celery-help     show celery help
      --file=VALUE      path/to/requirements.txt
      --local           if specified the task will run locally. Use this for testing
      --every           if specified runs task on all workers

    Description:
      model, job and script commands
      ------------------------------

      <model-action> can be any valid model action like fit, predict, score,
      transform, decision_function etc.

      <script-action> defaults to run
      <job-action> defaults to run

      Examples:
        om runtime model <name> fit <X> <Y>
        om runtime model <name> predict <X>
        om runtime job <name>
        om runtime script <name>
        om runtime script <name> run myparam="value"

      running asynchronously
      ----------------------

      model, job, script commands accept the --async paramter. This will submit
      the a task and return the task id. To wait for and get the result run use
      the result command

      Examples:
            om runtime model <name> fit <X> <Y> --async
            => <task id>
            om runtime result <task id>
            => result of the task

      restart app
      -----------

      This will restart the app on omegaml apphub. Requires a login to omegaml cloud.


      status
      ------

      Prints workers, labels, list of active tasks per worker, count of tasks

      Examples:
        om runtime status             # defaults to workers
        om runtime status workers
        om runtime status labels
        om runtime status stats

      celery commands
      ---------------

      This is the same as calling celery -A omegaml.celeryapp <commands>. Command
      commands include:

      inspect active         show currently running tasks
      inspect active_queues  show active queues for each worker
      inspect stats          show stats of each worker, including pool size (processes)
      inspect ping           confirm that worker is connected

      control pool_shrink N  shrink worker pool by N, specify 99 to remove all
      control pool_grow N    grow worker poool by N

      Examples:
            om runtime celery inspect active
            om runtime celery control pool_grow N


      env commands
      ------------

      This talks to an omegaml worker's pip environment

      a) install a specific package

         env install <package>    install the specified package, use name==version pip syntax for specific versions
         env uninstall <package>  uninstall the specified package

      b) use a requirements file

         env install --file requirements.txt
         env uninstall --file requirements.txt

      c) list currently installed packages

         env freez

      d) install on all or a specific worker

         env install --require gpu package
         env install --every package

         By default the installation runs on the default worker only. If there are multiple nodes where you
         want to install the package(s) worker nodes, be sure to specify --every

      Examples:
            om runtime env install pandas
            om runtime env uninstall pandas
            om runtime env install --file requirements.txt
            om runtime env install --file gpu-requirements.txt --require gpu
            om runtime env install --file requirements.txt --every
    """
    command = 'runtime'

    def ping(self):
        om = get_omega(self.args)
        label = self.args.get('--require')
        self.logger.info(om.runtime.require(label).ping())

    def _ensure_valid_XY(self, value):
        if value is not None:
            if value.isnumeric():
                return [eval(value)]
            if value[0] == '[' and value[-1] == ']':
                return eval(value)
        return value

    def model(self):
        om = get_omega(self.args)
        name = self.args.get('<name>')
        action = self.args.get('<model-action>')
        is_async = self.args.get('--async')
        kwargs_lst = self.args.get('--param')
        output = self.args.get('--result')
        label = self.args.get('--require')
        X = self._ensure_valid_XY(self.args.get('<X>'))
        Y = self._ensure_valid_XY(self.args.get('<Y>'))
        # parse the list of kw=value values
        # e.g. key1=val1 key2=val2 => kwargs_lst = ['key1=val1', 'key2=val2']
        #   => kw_dct = { 'key1': eval('val1'), 'key2': eval('val2') }
        kv_dct = {}
        for kv in kwargs_lst:
            k, v = kv.split('=', 1)
            kv_dct[k] = eval(v)
        kwargs = {}
        if action in ('predict', 'predict_proba',
                      'decision_function', 'transform'):
            # actions that take rName, but no Y
            kwargs['rName'] = output
        else:
            # actions that take Y, but no rName
            kwargs['Yname'] = Y
        if action == 'gridsearch':
            kwargs['parameters'] = kv_dct
        rt_model = om.runtime.require(label).model(name)
        meth = getattr(rt_model, action, None)
        if meth is not None:
            result = meth(X, **kwargs)
            if not is_async:
                self.logger.info(result.get())
            else:
                self.logger.info(result)
            return
        raise ValueError('{action} is not applicable to {name}'.format(**locals()))

    def script(self):
        om = get_omega(self.args)
        name = self.args.get('<name>')
        is_async = self.args.get('--async')
        kwargs = self.parse_kwargs('<kw=value>')
        label = self.args.get('--require')
        result = om.runtime.require(label).script(name).run(**kwargs)
        if not is_async:
            self.logger.info(result.get())
        else:
            self.logger.info(result.task_id)

    def job(self):
        om = get_omega(self.args)
        name = self.args.get('<name>')
        is_async = self.args.get('--async')
        label = self.args.get('--require')
        result = om.runtime.require(label).job(name).run()
        if not is_async:
            self.logger.info(result.get())
        else:
            self.logger.info(result.task_id)

    def result(self):
        from celery.result import AsyncResult

        om = get_omega(self.args)
        task_id = self.args.get('<taskid>')
        result = AsyncResult(task_id, app=om.runtime.celeryapp).get()
        self.logger.info(result)

    def log(self):
        import pandas as pd
        tail = self.args.get('-f')
        om = get_omega(self.args)
        if not tail:
            df = om.logger.dataset.get()
            with pd.option_context('display.max_rows', None,
                                   'display.max_columns', None,
                                   'display.max_colwidth', -1):
                print(df[['text']])
        else:
            om.logger.dataset.tail()

    def celery(self):
        om = get_omega(self.args)
        celery_cmds = ['celery']
        # convert omega terms into celery terms
        celery_opts = (
            # omega term, celery term, value|flag
            ('--worker', '--destination', 'value'),
            ('--queue', '--queue', 'value'),
            ('--celery-help', '--help', 'flag'),
        )
        for opt, celery_opt, kind in celery_opts:
            if self.args.get(opt):
                celery_cmds += [celery_opt]
                if kind == 'value':
                    celery_cmds += [self.args.get(opt)]
        celery_cmds += self.args.get('<celery-command>')
        celery_cmds += self.args.get('--flags')
        om.runtime.celeryapp.start(celery_cmds)

    def env(self):
        om = get_omega(self.args)
        action = self.args.get('<action>')
        package = self.args.get('<package>')
        reqfile = self.args.get('--file')
        every = self.args.get('--every')
        require = self.args.get('--require') or ''
        if reqfile:
            with open(reqfile, 'rb') as fin:
                om.scripts.put(fin, '.system/requirements.txt')
        if not om.scripts.exists('.system/envinstall', hidden=True):
            import omegaml as om_module
            envinstall_path = os.path.join(os.path.dirname(om_module.__file__), 'runtimes', 'envinstall')
            om.scripts.put(f'pkg://{envinstall_path}', '.system/envinstall')
        if every:
            labels = om.runtime.enable_hostqueues()
        else:
            labels = require.split(',')
        results = []
        for label in labels:
            result = (om.runtime.require(label)
                      .script('.system/envinstall')
                      .run(action=action, package=package, file=reqfile,
                           __format='python'))
            results.append((label, result))
        all_results = om.runtime.celeryapp.ResultSet([r[1] for r in results])
        from tqdm import tqdm
        with tqdm() as progress:
            while all_results.waiting():
                progress.update(1)
                sleep(1)
            all_results.get()
        for label, result in results:
            if label:
                print(f'** result of worker require={label}:')
            data = result.get()  # resolve AsyncResult => dict
            print(str(data.get('result', data)))  # get actual result object, pip stdout

    def status(self):
        om = get_omega(self.args)
        labels = self.args.get('labels')
        stats = self.args.get('stats')
        workers = not (labels or stats)
        if workers:
            pprint(om.runtime.workers())
        elif labels:
            queues = om.runtime.queues()
            pprint({worker: [q.get('name') for q in details
                             if not q.get('name').startswith('amq')]
                    for worker, details in queues.items()})
        elif stats:
            stats = om.runtime.stats()
            pprint({worker: {
                'size': details['pool']['max-concurrency'],
                'tasks': {
                    task: count for task, count in details['total'].items()
                }
            } for worker, details in stats.items()})

    def restart(self):
        import requests
        om = get_omega(self.args, require_config=True)
        name = self.args.get('<name>')
        user = om.runtime.auth.userid
        auth = requests.auth.HTTPBasicAuth(user, om.runtime.auth.apikey)
        url = om.defaults.OMEGA_RESTAPI_URL
        stop = requests.get(f'{url}/apps/api/stop/{user}/{name}'.format(om.runtime.auth.userid),
                            auth=auth)
        start = requests.get(f'{url}/apps/api/start/{user}/{name}'.format(om.runtime.auth.userid),
                             auth=auth)
        self.logger.info(f'stop: {stop} start: {start}')
