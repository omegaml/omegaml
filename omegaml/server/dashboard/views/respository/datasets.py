from omegaml.server.dashboard.views.repobase import RepositoryBaseView


class DatasetsRepositoryView(RepositoryBaseView):
    pass


def create_view(bp):
    view = DatasetsRepositoryView('datasets')
    view.create_routes(bp)
    return
