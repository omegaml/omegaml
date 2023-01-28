from omegaml.server.dashboard.views.repobase import RepositoryBaseView
from omegaml.server import flaskview as fv


class JobsRepositoryView(RepositoryBaseView):
    def detail_data(self, name, data=None, meta=None):
        run_at, triggers = self.store.get_schedule(name, only_pending=True)
        return {'run_at': run_at, 'triggers': triggers}

    @fv.route('/{self.segment}/runs/<path:name>')
    def api_list_runs(self, name):
        query = self.request.args.get('search[value]')
        meta = self.store.metadata(name)
        runs = meta.attributes.get('job_runs', [])
        runs = [r for r in runs if query in r['results']] if query else runs
        totalRows = len(runs)
        return {
            'data': runs,
            'recordsTotal': totalRows,
            'recordsFiltered': totalRows,
        }

    @fv.route('/{self.segment}/results/<path:name>')
    def api_get_results(self, name):
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
