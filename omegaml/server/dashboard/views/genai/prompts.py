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
            'prompt': meta.attributes.get('prompt', ''),
            'pipeline': meta.attributes.get('pipeline', ''),
            'tools': meta.attributes.get('tools', []),
            'documents': meta.attributes.get('documents', []),
        })
        return data

    def context_data(self, **kwargs):
        context = super().context_data()
        context.update({
            'availableModels': self.om.models.list('llms/*', kind=['genai.text', 'genai.llm']),
            'availableDocuments': self.om.datasets.list(kind='pgvector.conx'),
            'availableTools': self.om.models.list('tools/*'),
            'availablePipelines': self.om.models.list('pipelines/*'),
        })
        context.update(kwargs)
        return context

    def members(self, excludes=None):
        excludes = (
            lambda m: m.name.startswith('_'),
            lambda m: m.name.startswith('experiments/')
        )
        kind = ['genai.text', 'genai.llm']
        items = [m for m in self.store.list('prompts/*',
                                            kind=kind, raw=True) if not any(e(m) for e in excludes)]
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
        model = data['model']
        name = f'prompts/{name}' if not name.startswith('prompts/') else name
        meta = om.models.metadata(name)
        if meta is None:
            # create a new instance
            from omegaml.backends.genai.textmodel import TextModelBackend
            model_meta = om.models.metadata(model, data_store=om.datasets)
            model_meta.kind_meta['base_url'] = TextModelBackend.STORED_MODEL_URL
            meta = om.models._make_metadata(name=name, kind=model_meta.kind,
                                            bucket=self.bucket,
                                            attributes=model_meta.attributes,
                                            kind_meta=model_meta.kind_meta)
            meta.save()
            meta = om.models.link_experiment(name, name, label=om.runtime._default_label)
        meta.attributes.update(data)
        # set default permissions
        # -- groups matches the /ai/app/chat/<group> endpoint
        # -- by default it is included in the 'sibyl' group
        meta.attributes.setdefault('permissions', {
            'groups': data.get('permissions', {}).get('groups', ['sibyl']),
        })
        meta.save()
        return {'message': 'Prompt saved successfully', 'name': name}, 200


def create_view(bp):
    view = AIPromptsView('prompts', store='models')
    view.create_routes(bp)
    return
