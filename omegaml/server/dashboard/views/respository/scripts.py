from omegaml.server.dashboard.views.repobase import RepositoryBaseView


def create_view(bp):
    class ScriptsRepositoryView(RepositoryBaseView):
        pass

    view = ScriptsRepositoryView('scripts')
    view.create_routes(bp)
    return

