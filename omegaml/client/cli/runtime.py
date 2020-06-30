from omegaml.client.docoptparser import CommandBase
from omegaml.client.util import get_omega


class RuntimeCommandBase(CommandBase):
    """
    Usage:
      om runtime model <name> <model-action> [<X>] [<Y>] [--result=<output-name>] [--param=<kw=value>]... [options]
      om runtime script <name> [<script-action>] [<kw=value>...] [--async] [options]
      om runtime job <name> [<job-action>] [<args...>] [--async] [options]
      om runtime result <taskid> [options]
      om runtime ping [options]
      om runtime log [-f]

    Options:
      --async          don't wait for results, will print taskid
      -f               tail log
      --require=VALUE  worker label

    Description:
      <model-action> can be any valid model action like fit, predict, score,
      transform, decision_function etc.

      <script-action> defaults to run
      <job-action> defaults to run

      Examples:
        om runtime model <name> fit <X> <Y>
        om runtime model <name> predict <X>
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
        tail  = self.args.get('-f')
        om = get_omega(self.args)
        if not tail:
            df = om.logger.dataset.get()
            with pd.option_context('display.max_rows', None,
                                   'display.max_columns', None,
                                   'display.max_colwidth', -1):
                print(df[['text']])
        else:
            om.logger.dataset.tail()
