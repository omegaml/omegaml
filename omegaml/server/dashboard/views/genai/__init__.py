from flask import render_template

from omegaml.server import flaskview as fv
from omegaml.server.dashboard.views.base import BaseView


class GenAIView(BaseView):
    @fv.route('/{self.segment}')
    def index(self):
        om = self.om
        return render_template('dashboard/genai/chat.html', segment=self.segment)


def create_view(bp):
    view = GenAIView('ai')
    view.create_routes(bp)
    return
