from flask import render_template

from omegaml.server import flaskview as fv
from omegaml.server.dashboard.views.base import BaseView


class ChatAppsView(BaseView):

    @fv.route('/{self.segment}/chat/<path:name>')
    def chat(self, name):
        """Render the chat applications page."""
        # TODO consider listing only prompts under /<name> (e.g. prompts/<name>/*)
        prompts = self.om.models.list('prompts/*', kind=['genai.text', 'genai.llm'], raw=True)
        assistants = [{
            'name': prompt.name,
            'title': (prompt.attributes.get('title') or
                      prompt.attributes.get('docs', '').split('\n')[0].replace('#', '').strip()),
            'attributes': prompt.attributes,
        } for prompt in prompts
            if (not prompt.name.startswith('_')
                and name in prompt.attributes.get('permissions', {}).get('groups', ['sibyl']))]
        return render_template('dashboard/genai/chatapp.html',
                               name=name,
                               assistants=assistants,
                               segment=self.segment)


def create_view(bp):
    view = ChatAppsView('app')
    view.create_routes(bp)
    return
