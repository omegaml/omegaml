import numpy as np
from flask import render_template, request

from omegaml.server import flaskview as fv
from omegaml.server.dashboard.views.base import BaseView


class RuntimeView(BaseView):
    @fv.route('/runtime')
    def summary(self):
        workers = [
            {'name': 'worker-1', 'status': 'running', 'activity': '10% / 10'},
            {'name': 'worker-2', 'status': 'running', 'activity': '10% / 10'},
        ]
        return render_template('dashboard/runtime/summary.html',
                               segment='runtime',
                               items=workers,
                               attributes={},
                               buckets=['default'])

    @fv.route('/runtime/worker/<name>')
    def worker(self, name):
        return render_template('dashboard/runtime/worker_detail.html',
                               attributes={})

    @fv.route('/runtime/log')
    def api_get_log(self):
        logdata = [
            {'datetime': '2020-01-01 00:00:00',
             'level': 'info',
             'name': 'worker-1',
             'hostname': 'worker-1',
             'userid': 'user-1',
             'text': 'this is a log message',
             }
        ]
        mdf = self.om.logger.dataset.get(lazy=True)
        # parse datatable serverside params
        start = int(request.args.get('start', 0))
        nrows = int(request.args.get('length', 10))
        query = request.args.get('search[value]', None)
        sortby_idx = request.args.get('order[0][column]', 0)
        sortby = request.args.get(f'columns[{sortby_idx}][data]', 'created')
        sortascending = 'desc' != request.args.get('order[0][dir]', 'desc')
        # filter and prepare log data
        logdata = (mdf
                   .skip(start)
                   .head(nrows)
                   .query(text__contains=query)
                   .value)
        if len(logdata) > 0:
            logdata = (logdata
                       .reset_index()
                       .sort_values(sortby, ascending=sortascending)
                       .to_dict(orient='records'))
        else:
            logdata = []
        return {
            'data': logdata,
            'recordsTotal': len(mdf),
            'recordsFiltered': len(logdata) if query else len(mdf),
        }

    @fv.route('/runtime/status/plot/health')
    def api_status_plot_health(self):
        import plotly.express as px
        from plotly.io import json
        import pandas as pd
        by_status = pd.DataFrame({
            'status': ['failed', 'healthy', 'pending'],
            'count': [2, 9, 0],
        })
        fig = px.pie(data_frame=by_status,
                     values='count',
                     names='status')  # explicitley mark each data point
        return json.to_json(fig)

    @fv.route('/runtime/status/plot/uptime')
    def api_status_plot_uptime(self):
        import plotly.express as px
        from plotly.io import json
        import pandas as pd
        from random import sample

        long_df = pd.DataFrame({
            'date': pd.date_range('1.1.2024', '31.1.2024'),
            'status': [sample(['failed', 'healthy'], 1, counts=(2, 29))[0] for i in range(0, 31)],
            'count': [1] * 31,
        })
        fig = px.bar(long_df, x="date", y="count", color="status",
                     color_discrete_map={'failed': 'red', 'healthy': 'green'})
        return json.to_json(fig)

    @fv.route('/runtime/worker/plot/load')
    def api_worker_plot_load(self):
        import pandas as pd
        import plotly.express as px
        from plotly.io import json

        df = pd.DataFrame({
            'date': pd.date_range('1.1.2024', '31.1.2024'),
            'load_pct': np.random.rand(31),
        })

        fig = px.line(df, x='date', y='load_pct')
        return json.to_json(fig)

    @fv.route('/runtime/database/dbstats/plot')
    def api_runtime_dbstats_plot(self):
        import plotly.express as px
        from plotly.io import json
        om = self.om
        dbstats = om.datasets.dbstats(scale='gb')
        dfx = dbstats.loc[['fsAvailableSize', 'fsUsedSize']]
        fig = px.pie(dbstats, names=dfx.index, values=dfx['db'])
        return json.to_json(fig)

    @fv.route('/runtime/database/repostats/plot')
    def api_runtime_repostats_plot(self):
        import plotly.express as px
        from plotly.io import json
        om = self.om
        stats = om.stats()
        fig = px.pie(stats, names=stats.index, values=stats['totalSize%'])
        return json.to_json(fig)


def create_view(bp):
    view = RuntimeView('runtime')
    view.create_routes(bp)
