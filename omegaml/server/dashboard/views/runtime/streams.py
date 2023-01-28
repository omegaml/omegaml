from omegaml.server.dashboard.views.repobase import RepositoryBaseView


class StreamRepositoryView(RepositoryBaseView):
    list_template = 'runtime/{self.segment}.html'
    detail_template = 'runtime/{self.segment}_detail.html'


def create_view(bp):
    view = StreamRepositoryView('streams')
    view.create_routes(bp)
    return

