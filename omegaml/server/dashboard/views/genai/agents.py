from omegaml.server.dashboard.views.genai.prompts import AIPromptsView
from omegaml.server.dashboard.views.repobase import RepositoryBaseView


class AIRepositoryView(RepositoryBaseView):
    list_template = 'genai/{self.segment}.html'
    detail_template = 'genai/{self.segment}_detail.html'


class AIAgentsView(AIPromptsView):
    list_prefix = 'agents'


def create_view(bp):
    view = AIAgentsView('agents', store='models')
    view.create_routes(bp)
    return
