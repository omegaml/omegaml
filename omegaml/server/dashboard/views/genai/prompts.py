from flask import render_template

from omegaml.server import flaskview as fv
from omegaml.server.dashboard.views.repobase import RepositoryBaseView


class AIRepositoryView(RepositoryBaseView):
    list_template = 'genai/{self.segment}.html'
    detail_template = 'genai/{self.segment}_detail.html'


class AIPromptsView(AIRepositoryView):
    def detail_data(self, name, data=None, meta=None):
        # ensure we always have a tracking attribute
        data['meta']['attributes'].setdefault('tracking', {})
        data['meta']['attributes']['tracking'].setdefault('experiments', [])
        return data

    def members(self, excludes=None):
        excludes = (
            lambda m: m.name.startswith('_'),
            lambda m: m.name.startswith('experiments/')
        )
        kind = ['genai.text', 'genai.llm']
        items = [m for m in self.store.list(kind=kind, raw=True) if not any(e(m) for e in excludes)]
        return items

    @fv.route('/{self.segment}/new')
    def new(self):
        """Create a new prompt"""
        template = self.detail_template.format(self=self)
        name = 'prompts/_new_'
        meta = self.store._make_metadata(name=name, kind='genai.text')
        meta.attributes['docs'] = meta.attributes.get('docs', '').strip() or self._default_markdown(meta)
        summary = {}
        data = {
            'meta': meta.to_dict(),
            'summary': summary,
        }
        data.update(self.detail_data(name, data=data, meta=meta))
        return render_template(f"dashboard/{template}",
                               segment=self.segment,
                               buckets=self.buckets,
                               **data)


def create_view(bp):
    view = AIPromptsView('prompts', store='models')
    view.create_routes(bp)
    return
