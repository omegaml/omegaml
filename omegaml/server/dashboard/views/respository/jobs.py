from cron_descriptor import get_description

from omegaml.server import flaskview as fv
from omegaml.server.dashboard.views.repobase import RepositoryBaseView
from omegaml.server.util import datatables_ajax


class JobsRepositoryView(RepositoryBaseView):
    def detail_data(self, name, data=None, meta=None):
        return self.api_get_schedule(name)['data']

    @fv.route('/{self.segment}/runs/<path:name>')
    def api_list_runs(self, name):
        query = self.request.args.get('search[value]')
        draw = int(self.request.args.get('draw', 0))
        meta = self.store.metadata(name)
        runs = meta.attributes.get('job_runs', [])
        runs = [r for r in runs if query in r['results']] if query else runs
        return datatables_ajax(runs, draw=draw)

    @fv.route('/{self.segment}/schedule/<path:name>', methods=['GET'])
    def api_get_schedule(self, name):
        run_at, triggers = self.store.get_schedule(name)
        draw = int(self.request.args.get('draw', 0))
        schedule = {
            'triggers': triggers,
            'schedule': {
                'text': get_description(run_at) if run_at else 'not scheduled',
                'cron': run_at,
            }}
        return datatables_ajax(schedule, draw=draw)

    @fv.route('/{self.segment}/schedule/<path:name>', methods=['POST'])
    def api_set_schedule(self, name):
        data = self.request.json
        run_at = data.get('cron')
        if run_at == '':
            self.store.drop_schedule(name)
        else:
            self.store.schedule(name, run_at)
        return self.api_get_schedule(name)

    @fv.route('/{self.segment}/results/<path:name>')
    def api_get_results(self, name):
        if name.endswith('_empty_'):
            return {}
        if not name.startswith('results'):
            name = f'results/{name}'
        return self.om.jobs.export(name)

    def members(self, excludes=None):
        excludes = excludes or (
            lambda m: m.name.startswith('results'),
        )
        return super().members(excludes=excludes)


def create_view(bp):
    view = JobsRepositoryView('jobs')
    view.create_routes(bp)
    return
