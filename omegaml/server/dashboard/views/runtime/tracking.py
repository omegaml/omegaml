from omegaml.server import flaskview as fv
from omegaml.server.dashboard.views.repobase import RepositoryBaseView

from omegaml.server.util import datatables_ajax


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
        start = int(self.request.args.get('start', 0))
        nrows = int(self.request.args.get('length', 10))
        data, totalRows = self._experiment_data(name, start=start, nrows=nrows,
                                                run='all')
        return datatables_ajax(data, n_total=totalRows)

    @fv.route('/{self.segment}/experiment/plot/<name>')
    def api_plot_metrics(self, name):
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


def create_view(bp):
    view = TrackingView('tracking')
    view.create_routes(bp)
    return
