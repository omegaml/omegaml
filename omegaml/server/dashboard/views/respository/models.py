from omegaml.server.dashboard.views.repobase import RepositoryBaseView


class ModelsRepositoryView(RepositoryBaseView):
    def detail_data(self, name, data=None, meta=None):
        # ensure we always have a tracking attribute
        data['meta']['attributes'].setdefault('tracking', {})
        data['meta']['attributes']['tracking'].setdefault('experiments', [])
        return data

    def members(self):
        excludes = (
            lambda m: m.name.startswith('_'),
            lambda m: m.name.startswith('experiments/')
        )
        items = [m for m in self.store.list(raw=True) if not any(e(m) for e in excludes)]
        return items


def create_view(bp):
    view = ModelsRepositoryView('models')
    view.create_routes(bp)
    return
