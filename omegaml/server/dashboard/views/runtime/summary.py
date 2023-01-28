import cachetools
import numpy as np
from datetime import datetime
from flask import render_template, request

from omegaml.server import flaskview as fv
from omegaml.server.dashboard.views.base import BaseView


class RuntimeView(BaseView):
    @fv.route('/runtime')
    def summary(self):
        workers = self._worker_status()
        return render_template('dashboard/runtime/summary.html',
                               segment='runtime',
                               items=workers,
                               attributes={},
                               buckets=self.buckets)

    @fv.route('/runtime/worker/<name>')
    def worker(self, name):
        status = self._worker_status(name, detail=True)
        return render_template('dashboard/runtime/worker_detail.html',
                               status=status,
                               attributes={})

    @cachetools.cached(cache=cachetools.TTLCache(maxsize=10, ttl=5))
    def _worker_status(self, name=None, detail=False):
        om = self.om
        status = om.status(data=True)
        if not detail:
            # using monitoring data -- this should always return fast
            data = status['runtime']['data']
            data = data if isinstance(data, list) else []
        elif status['broker']['status'] == 'ok':
            # getting live data -- this may take a while or fail
            data = om.runtime.status()
            data = data.get(name, {}) if name else data
        else:
            data = {}
        return data

    @fv.route('/runtime/log')
    def api_get_log(self):
        # parse datatable serverside params
        start = int(request.args.get('start', 0))
        nrows = int(request.args.get('length', 10))
        query = request.args.get('search[value]', '').strip()
        sortby_idx = request.args.get('order[0][column]', 0)
        sortby = request.args.get(f'columns[{sortby_idx}][data]', 'created')
        sortascending = 'desc' != request.args.get('order[0][dir]', 'desc')
        # filter and prepare log data
        mdf = self.om.logger.dataset.get(lazy=True)
        sortprefix = '-' if sortascending else ''
        logdata = (mdf
                   .skip(start)
                   .head(nrows)
                   .sort(f'{sortprefix}{sortby}')
                   .query(text__contains=query)
                   .value)
        if len(logdata) > 0:
            logdata = (logdata
                       .reset_index()
                       .to_dict(orient='records'))
        else:
            logdata = []
        return {
            'data': logdata,
            'recordsTotal': len(mdf),
            'recordsFiltered': len(logdata) if query else len(mdf),
        }

    @fv.route('/runtime/status')
    def status(self):
        om = self.om
        status = om.status(data=True)
        return render_template('dashboard/runtime/status.html',
                               data=status)

    @fv.route('/runtime/status/plot/health')
    def api_status_plot_health(self):
        # FIXME replace dummy data with monitoring data (.system experiment)
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
        import pandas as pd
        om = self.om
        sysexp = om.runtime.experiment('.system')
        logdf = sysexp.data(event='monitor')
        # group by day and determine health status
        if len(logdf) > 0:
            grouped = logdf.groupby(logdf['dt'].dt.date).agg(
                status=(
                    'value', lambda x: 'healthy' if sum(d['status'] == 'ok' for d in x) / len(x) > 0.01 else 'failed'),
                count=('value', 'size')  # count of events
            ).reset_index()
            # rename columns for plotting
            dailydf = grouped.rename(columns={'dt': 'date'})
        else:
            dailydf = pd.DataFrame(columns=['date', 'status', 'count'])
        # create full range
        end_date = datetime.utcnow()
        date_range = pd.date_range(end=end_date,
                                   periods=90,
                                   freq='D',
                                   normalize=True)
        full_df = pd.DataFrame({'date': date_range})
        full_df['date'] = full_df['date'].dt.date
        dailydf = dailydf.merge(full_df, on='date', how='right')
        dailydf['count'] = 1
        dailydf['status'] = dailydf['status'].fillna('unknown')
        fig = px.bar(dailydf, x="date", y="count", color="status",
                     color_discrete_map={'failed': 'red', 'healthy': 'green', 'unknown': 'gray'})
        fig.update_layout(showlegend=False, margin={'l': 0, 'r': 0, 't': 0, 'b': 0, 'autoexpand': True})
        fig.update_yaxes(visible=False)
        return fig.to_json()

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
        fig = px.pie(stats, names=stats.index, values=stats['count'])
        return json.to_json(fig)


def create_view(bp):
    view = RuntimeView('runtime')
    view.create_routes(bp)
