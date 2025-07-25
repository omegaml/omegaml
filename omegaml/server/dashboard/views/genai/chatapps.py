from flask import render_template

from omegaml.server import flaskview as fv
from omegaml.server.dashboard.views.base import BaseView


class ChatAppsView(BaseView):

    @fv.route('/{self.segment}/chat/<path:name>')
    def chat(self, name):
        """Render the chat applications page."""
        prompts = self.om.models.list('prompts/*', kind=['genai.text', 'genai.llm'], raw=True)
        return render_template('dashboard/genai/chatapp.html',
                               name=name,
                               assistants=prompts,
                               segment=self.segment)


def create_view(bp):
    view = ChatAppsView('app')
    view.create_routes(bp)
    return
