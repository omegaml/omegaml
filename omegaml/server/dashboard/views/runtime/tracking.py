import base64
from flask import jsonify
from io import BytesIO
from matplotlib import pyplot as plt

from omegaml.server import flaskview as fv
from omegaml.server.dashboard.views.repobase import RepositoryBaseView
from omegaml.server.util import datatables_ajax, json_abort
from omegaml.util import ensure_json_serializable

validOrNone = lambda v: v if v and v not in ('undefined', 'null', None) else None


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

    def _experiment_data(self, name, start=None, nrows=None, event=None, run=None):
        # TODO figure out how to select the event to display
        run = run or 'all'
        om = self.om
        exp = om.runtime.experiment(name)
        # TODO: query lazy for large datasets (use batchsize=)
        data = exp.data(event=event,
                        run=run)
        start = start or 0
        subset = slice(start, start + nrows) if nrows else slice(start, None)
        if data is not None and len(data) > 0:
            totalRows = len(data)
            data = (data
                    .iloc[subset]
                    .reset_index()
                    .fillna('')
                    .to_dict(orient='records'))
        else:
            data = []
            totalRows = 0
        return data, totalRows

    @fv.route('/{self.segment}/experiment/data/<name>')
    def api_experiment_data(self, name):
        """ return the experiment data for a given experiment

        Args:
            name (str): the experiment name

        Query Args:
            start (int): the start index for the data
            length (int): the maximum number of rows to return

        Returns:
            dict: a dict with keys 'data' and 'totalRows' containing the data and total rows
        """
        start = int(self.request.args.get('start', 0))
        nrows = int(self.request.args.get('length', 10))
        data, totalRows = self._experiment_data(name, start=start, nrows=nrows,
                                                run='all')
        return datatables_ajax(data, n_total=totalRows)

    @fv.route('/{self.segment}/experiment/plot/<name>')
    def api_plot_metrics(self, name):
        """ plot the metrics for a given experiment

        Args:
            name (str): the experiment name

        Query Args:
            multicharts (int): whether to plot multiple charts, one for each metric
              (defaults to 0)
        """
        import plotly.express as px
        from plotly.io import json
        multicharts = int(self.request.args.get('multicharts', 0))
        metrics, totalRows = self._experiment_data(name,
                                                   run='all', event='metric')
        cols = 'key' if multicharts else None
        fig = px.line(data_frame=metrics,
                      x='run',
                      y='value',
                      facet_col=cols,
                      color='key',  # one line for each metric
                      markers='*')  # explicitley mark each data point
        graphJSON = json.to_json(fig)
        return graphJSON

    @fv.route('/{self.segment}/monitor/plot/<model>')
    def api_plot_monitor(self, model):
        """ plot the monitor data for a given model

        Args:
            model (str): the model name

        Query Args:
            column (str): the column to plot (defaults to None)
            experiment (str): the experiment to plot (defaults to None)
            since (str): the date to plot since (defaults to None)

        Returns:
            dict: a dict with the plot image, base64 encoded
                { image: 'base64 encoded image' }
        """
        om = self.om
        column = validOrNone(self.request.args.get('column'))
        experiment = validOrNone(self.request.args.get('experiment'))
        since = validOrNone(self.request.args.get('since'))
        exp = om.runtime.model(model).experiment(experiment=experiment)
        if exp._has_monitor(model):
            mon = exp.as_monitor(model)
            try:
                stats = mon.compare(seq='series', since=since)
                plt.figure()
                stats.plot(column=column)
                img = BytesIO()
                plt.savefig(img)
                img.seek(0)
            except Exception as e:
                json_abort(400, f'error plotting statistics due to {e}')
            # https://stackoverflow.com/a/63923399/890242
            return jsonify(image=base64.b64encode(img.getvalue()).decode())
        return {}

    @fv.route('/{self.segment}/monitor/compare/<model>')
    def api_compare_monitor(self, model):
        om = self.om
        experiment = validOrNone(self.request.args.get('experiment'))
        exp = om.runtime.model(model).experiment(experiment=experiment)
        if exp._has_monitor(model):
            mon = exp.as_monitor(model)
            stats = mon.compare(seq='series')
            return ensure_json_serializable(stats.summary(raw=True))
        return {}


def create_view(bp):
    view = TrackingView('tracking')
    view.create_routes(bp)
    return
