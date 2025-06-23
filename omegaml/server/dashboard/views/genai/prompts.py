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
        data.update({
            'name': meta.name,
            'model': meta.attributes.get('model', ''),
            'template': meta.attributes.get('template', ''),
            'systemPrompt': meta.attributes.get('systemPrompt', ''),
            'pipeline': meta.attributes.get('pipeline', 'default'),
            'tools': meta.attributes.get('tools', []),
            'documents': meta.attributes.get('documents', []),
        })
        return data

    def context_data(self, **kwargs):
        context = super().context_data()
        context.update({
            'availableModels': self.om.models.list(kind=['genai.text', 'genai.llm']),
            'availableDocuments': self.om.datasets.list(kind='pgvector.conx'),
            'availableTools': self.om.models.list('tools/*'),
        })
        context.update(kwargs)
        return context

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
        data = self._default_detail_data(name, meta=meta)
        data.update(self.detail_data(name, data=data, meta=meta))
        context = self.context_data(isNew=True)
        return render_template(f"dashboard/{template}",
                               segment=self.segment,
                               buckets=self.buckets,
                               context=context,
                               data=data, **data)

    @fv.route('/{self.segment}/<path:name>/save', methods=['POST'])
    def api_save_prompt(self, name):
        """Save a new or existing prompt"""
        om = self.om
        data = self.request.json
        meta = om.models.metadata(name)
        if meta is None:
            model_meta = om.models.metadata(data['model'], data_store=om.datasets)
            meta = om.models._make_metadata(name=name, kind=model_meta.kind,
                                            bucket=self.bucket,
                                            attributes=model_meta.attributes,
                                            kind_meta=model_meta.kind_meta)
        else:
            meta.attributes.update(data)
        meta.save()
        return {'message': 'Prompt saved successfully', 'name': name}, 200


def create_view(bp):
    view = AIPromptsView('prompts', store='models')
    view.create_routes(bp)
    return
