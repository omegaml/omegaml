import base64
from cachetools import TTLCache, cached
from flask import jsonify
from io import BytesIO
from matplotlib import pyplot as plt

from omegaml.server import flaskview as fv
from omegaml.server.dashboard.views.repobase import RepositoryBaseView
from omegaml.server.util import datatables_ajax, json_abort
from omegaml.util import ensure_json_serializable

validOrNone = lambda v, astype=None: ((astype(v) if astype else v)
                                      if v and str(v).strip() not in ('undefined', 'null', None)
                                      else None)

truefalse = lambda v: str(v) in ('true', 'True', '1')


class TrackingView(RepositoryBaseView):
    list_template = 'runtime/{self.segment}.html'
    detail_template = 'runtime/{self.segment}_detail.html'

    @property
    def store(self):
        return self.om.models

    def members(self, excludes=None):
        excludes = (
            lambda m: not m.name.startswith('experiments/'),
            lambda m: m.name.endswith('.notrack'),
        )
        return super().members(excludes=excludes)

    def _experiment_data(self, name, start=None, nrows=None, event=None, run=None, summary=False, as_dataframe=False,
                         **kwargs):
        """ return the experiment data for a given experiment

        Args:
            name:
            start:
            nrows:
            event:
            run:
            summary:
            as_dataframe (bool): if True, return as pandas DataFrame, else as list of dicts
            **kwargs:

        Returns:
            (data, totalRows), where data is the data and totalRows is the total number of rows
                * data (list|pd.DataFrame): the data
                * totalRows (int): the total number of rows
        """
        # TODO figure out how to select the event to display
        run = run or 'all'
        om = self.om
        exp = om.runtime.experiment(name)
        # query data lazily
        # -- this way we always query for only the data we need
        start = start or 0
        rows_range = None if nrows is None else slice(start, start + nrows)
        if summary:
            # -- step 1, query for runs
            probe = exp.data(event='start', run=run, slice=rows_range, **kwargs)
            total_runs = exp._latest_run
            actual_runs = probe['run'].unique() if hasdata(probe) else []
            # -- step 2, query for actual data
            data = exp.data(event=event, run=actual_runs, **kwargs)

            def byrun(df):
                metrics = (df.where(df['event'] == 'metric')
                           .groupby(["run", "key"])["value"]
                           .mean()
                           .unstack())
                df = (df.where(df['event'] == 'start')
                      .set_index("run")
                      .merge(metrics, on="run")
                      .reset_index())
                return df[['run', 'dt'] + list(metrics.columns) + ['node', 'userid']]

            data = byrun(data) if hasdata(data) else []
            total_rows = total_runs
        else:
            # detail data
            data = exp.data(event=event, run=run, slice=rows_range, **kwargs)
            total_rows = exp._latest_run if hasdata(data) else 0
        if hasdata(data):
            totalRows = total_rows
            data = (data
                    .reset_index()
                    .fillna(''))
            if not as_dataframe:
                data = data.to_dict(orient='records')
        else:
            data = []
            totalRows = 0
        return data, totalRows

    @fv.route('/{self.segment}/experiment/data/<path:name>')
    def api_experiment_data(self, name):
        """ return the experiment data for a given experiment (datatables.js)

        Args:
            name (str): the experiment name

        Query Args:
            start (int): the start index for the data
            nrows (int): the maximum number of rows to return
            length (int): the maximum number of rows to return
            summary (int): whether to return summary data (defaults to 0)
            draw (int): the draw index for datatables (defaults to 0)
            run (str): the run to return data for (defaults to 'all')
            since (str): the date to return data since (defaults to None)
            end (str): the date to return data until (defaults to None)

        Returns:
            dict: a dict with keys 'data' and 'totalRows' containing the data and total rows
        """
        summary = truefalse(self.request.args.get('summary', 0))
        initialize = int(self.request.args.get('initialize', 0))
        draw = int(self.request.args.get('draw', 0))
        start = int(self.request.args.get('start', 0))
        length = int(self.request.args.get('length', 0))
        nrows = length or int(self.request.args.get('nrows', 10)) if not initialize else 1
        run = [int(v) for v in self.request.args.get('run', '').split(',') if v and v.isnumeric()] or 'all'
        since = validOrNone(self.request.args.get('since', None))
        end = validOrNone(self.request.args.get('end', None))
        events = ['start', 'metric', 'stop'] if summary else None
        data, totalRows = self._experiment_data(name, start=start, nrows=nrows, summary=summary,
                                                run=run, since=since, end=end, event=events)

        return datatables_ajax(data, n_total=totalRows, n_filtered=totalRows, draw=draw, ignore='index')

    @fv.route('/{self.segment}/experiment/plot/<path:name>')
    def api_plot_metrics(self, name):
        """ plot the metrics for a given experiment

        Args:
            name (str): the experiment name

        Query Args:
            multicharts (int): whether to plot multiple charts, one for each metric
              (defaults to 0)
            since (str): the date to plot since (defaults to None)
            end (str): the date to plot until (defaults to None)
        """
        import plotly.express as px
        from plotly.io import json
        multicharts = int(self.request.args.get('multicharts', 0))
        since = validOrNone(self.request.args.get('since', None))
        end = validOrNone(self.request.args.get('end', None))
        runs = self.request.args.get('runs', 0) or 'all'
        runs = [validOrNone(v, astype=int) for v in runs.split(',')] if runs not in ('all', '*') else 'all'
        metrics, totalRows = self._experiment_data(name, run=runs, event='metric', since=since, end=end,
                                                   as_dataframe=True)
        cols = 'key' if multicharts else None
        pltkwargs = dict(facet_col=cols,
                         facet_col_wrap=4,
                         color='key')
        if not hasdata(metrics):
            json_abort(400, "no data to plot")
        single_run = len(metrics['run'].unique()) == 1
        multi_steps = len(metrics['step'].unique()) > 1
        if single_run and not multi_steps:
            # one bar for reach metric
            pltfn = px.bar
            pltkwargs.update(x='key',
                             y='value')
        elif single_run and multi_steps:
            # one line for each metric
            pltfn = px.line
            pltkwargs.update(
                x='step',
                y='value',
                markers='*',  # explicitley mark each data point
            )
        elif multi_steps:
            # one plot for each metric
            pltfn = px.line
            pltkwargs.update(
                x='step',
                y='value',
                color='run',
                facet_col='key',
                markers='*',  # explicitley mark each data point
            )
        else:
            pltfn = px.line
            pltkwargs.update(
                x='run',
                y='value',
                markers='*',  # explicitley mark each data point
            )
        fig = pltfn(data_frame=metrics, **pltkwargs)
        fig.update_xaxes(type='category')
        graphJSON = json.to_json(fig)
        return graphJSON

    @fv.route('/{self.segment}/monitor/plot/<path:model>')
    def api_plot_monitor(self, model):
        """ plot the monitor data for a given model

        Args:
            model (str): the model name

        Query Args:
            column (str): the column to plot (defaults to None)
            experiment (str): the experiment to plot (defaults to None)
            since (str): the date to plot since (defaults to None)
            kind (str): the kind of plot to create (defaults to None),
              one of 'time', 'dist' referring to a line plot by snapshot,
                or a distribution plot, respectively

        Returns:
            dict: a dict with the plot image, base64 encoded
                { image: 'base64 encoded image' }
        """
        om = self.om
        column = validOrNone(self.request.args.get('column'))
        experiment = validOrNone(self.request.args.get('experiment'))
        since = validOrNone(self.request.args.get('since'))
        end = validOrNone(self.request.args.get('end'))  # not supported by compare
        kind = validOrNone(self.request.args.get('kind')) or 'dist'
        rstats = validOrNone(self.request.args.get('stats'))
        exp = om.runtime.model(model).experiment(experiment=experiment)
        if exp._has_monitor(model):
            mon = exp.as_monitor(model)
            try:
                stats = mon.compare(seq='series', since=since)
                fig = plt.figure()
                stats.plot(column=column, statistic=rstats, kind=kind)
                img = BytesIO()
                plt.savefig(img)
                plt.close(fig)
                img.seek(0)
            except Exception as e:
                json_abort(400, f'error plotting statistics due to {e}')
            # https://stackoverflow.com/a/63923399/890242
            return jsonify(image=base64.b64encode(img.getvalue()).decode())
        json_abort(400, "no monitor defined")

    @fv.route('/{self.segment}/monitor/compare/<path:model>')
    def api_compare_monitor(self, model):
        om = self.om
        experiment = validOrNone(self.request.args.get('experiment'))
        exp = om.runtime.model(model).experiment(experiment=experiment)
        # Function to categorize the values based on the specified ranges
        categories = {
            'alert': (.55, 1.0),
            'warning': (.25, .55),
            'stable': (0.0, 0.25),
        }

        def categorize(value, categories):
            for status, (min_val, max_val) in categories.items():
                if min_val <= value <= max_val:
                    return status
            return 'check'  # Default case

        def compare_stats(stats):
            snapshots = stats.df.groupby(['seq_from', 'seq_to']).agg(
                {'drift': 'max', 'score': 'max', 'dt_from': 'min', 'dt_to': 'min'}).reset_index()
            mask = stats.df.groupby(['seq_from', 'seq_to'])['score'].idxmax()
            snapshots = stats.df.iloc[mask][
                ['column', 'drift', 'score', 'metric', 'stats', 'kind', 'dt_from', 'dt_to', 'seq_from', 'seq_to']]
            snapshots['status'] = snapshots['score'].apply(lambda x: categorize(x, categories))
            result = {
                'summary': stats.summary(raw=True),
                'stats': stats.df['statistic'].unique(),
                'snapshots': snapshots.to_dict('records'),
            }
            return result

        if exp._has_monitor(model):
            try:
                mon = exp.as_monitor(model)
                stats = mon.compare(seq='series')
                result = compare_stats(stats)
            except:
                result = {
                    'summary': None,
                    'stats': None,
                    'snapshots': None,
                }
            return ensure_json_serializable(result)
        json_abort(400, "no monitor defined")

    @cached(cache=TTLCache(maxsize=1, ttl=60))
    @fv.route('/{self.segment}/monitor/alerts')
    def api_list_alerts(self):
        om = self.om
        all_alerts = []
        if om.datasets.exists('.system/alerts', hidden=True):
            # if we have a scheduled alert dataset, use it
            alerts = dict(alerts=om.datasets.get('.system/alerts'))
            return jsonify(alerts)
        for exp in om.models.list('experiments/*'):
            exp = exp.replace('experiments/', '')
            alerts = om.runtime.experiment(exp).data(event='alert', run='*', since='-10d')
            if alerts is None or alerts.empty:
                continue
            alerts = alerts.drop_duplicates(['event', 'key'])
            resource = lambda doc: 'models/' + doc['key'].replace('drift:', '')
            all_alerts.extend([
                {
                    'event': doc['event'],
                    'resource': resource(doc),
                    'message': f'Drift on {resource(doc)}',
                    'dt': doc['dt'],
                } for doc in alerts.to_dict('records')])
        result = {
            'alerts': all_alerts
        }
        return jsonify(result)

    @cached(cache=TTLCache(maxsize=10, ttl=60))
    @fv.route('/{self.segment}/monitor/alerts/<path:model>')
    def api_get_model_alerts(self, model):
        om = self.om
        experiment = validOrNone(self.request.args.get('experiment'))
        exp = om.runtime.model(model).experiment(experiment=experiment)
        if exp._has_monitor(model):
            mon = exp.as_monitor(model)
            alerts = mon.alerts()
            return jsonify(alerts)
        json_abort(400, "no monitor defined")


def create_view(bp):
    view = TrackingView('tracking')
    view.create_routes(bp)
    return


hasdata = lambda d: d is not None and len(d) > 0
