from flask import render_template

from omegaml.backends.genai.assistant import Assistant
from omegaml.backends.genai.models import ConversationModelBackend
from omegaml.server import flaskview as fv
from omegaml.server.dashboard.views.repobase import RepositoryBaseView


class AIRepositoryView(RepositoryBaseView):
    list_template = 'genai/{self.segment}.html'
    detail_template = 'genai/{self.segment}_detail.html'


class AIPromptsView(AIRepositoryView):
    item_filter = 'assistant/*'
    item_prefix = 'assistant/'
    item_class = Assistant

    def detail_data(self, name, data=None, meta=None):
        # ensure we always have a tracking attribute
        data['meta']['attributes'].setdefault('tracking', {})
        data['meta']['attributes']['tracking'].setdefault('experiments', [])
        # promptedit.js
        # -- fieldMap links selection field to list
        data.update({
            'name': meta.name,
            'model': meta.attributes.get('model') or '',
            'template': meta.attributes.get('template') or '',
            'prompt': meta.attributes.get('prompt') or '',
            'pipeline': meta.attributes.get('pipeline') or '',
            'tools': meta.attributes.get('tools') or [],
            'guardrails': meta.attributes.get('guardrails') or [],
            'documents': meta.attributes.get('documents') or [],
        })
        return data

    def context_data(self, **kwargs):
        context = super().context_data()
        context.update({
            'availableModels': self.om.models.list('llms/*'),
            'availableDocuments': self.om.datasets.list(kind='pgvector.conx'),
            'availableTools': self.om.models.list('tools/*'),
            'availableGuardrails': [name for name in self.om.models.list('policy/*') if 'scanners/' not in name],
            'availablePipelines': self.om.models.list('pipelines/*'),
        })
        context.update(kwargs)
        return context

    def members(self, excludes=None):
        excludes = (
            lambda m: m.name.startswith('_'),
            lambda m: m.name.startswith('experiments/'),
        )
        items = [m for m in self.store.list(self.item_filter, raw=True) if not any(e(m) for e in excludes)]
        return items

    @fv.route('/{self.segment}/new')
    def new(self):
        """Create a new prompt"""
        template = self.detail_template.format(self=self)
        name = self.item_prefix + self._make_name()
        obj = self.item_class()
        meta = self.store.put(obj, name=name)
        meta.attributes['docs'] = meta.attributes.get('docs', '').strip() or self._default_markdown(meta)
        data = self._default_detail_data(name, meta=meta)
        data.update(self.detail_data(name, data=data, meta=meta))
        context = self.context_data(isNew=True)
        return render_template(
            f"dashboard/{template}",
            segment=self.segment,
            buckets=self.buckets,
            context=context,
            data=data,
            **data,
        )

    @fv.route('/{self.segment}/<path:name>/save', methods=['POST'])
    def api_save_prompt(self, name):
        """Save a new or existing prompt"""
        om = self.om
        data = self.request.json
        model = data['model']
        name = f'{self.item_prefix}{name}' if not name.startswith(self.item_prefix) else name
        meta = om.models.metadata(name)
        if meta is None:
            # create a new instance
            model_meta = om.models.metadata(model, data_store=om.datasets)
            model_meta.kind_meta['base_url'] = ConversationModelBackend.STORED_MODEL_URL
            meta = om.models._make_metadata(
                name=name,
                kind=model_meta.kind,
                bucket=self.bucket,
                attributes=model_meta.attributes,
                kind_meta=model_meta.kind_meta,
            )
            meta.save()
            meta = om.models.link_experiment(name, name, label=om.runtime._default_label)
        meta.attributes.update(data)
        # set default permissions
        # -- groups matches the /ai/app/chat/<group> endpoint
        # -- by default it is included in the 'sibyl' group
        meta.attributes.setdefault(
            'permissions',
            {'groups': data.get('permissions', {}).get('groups', ['sibyl'])},
        )
        meta.save(version=True)
        return {'message': 'Prompt saved successfully', 'name': name}, 200

    def _make_name(self):
        import random

        def generate_magical_name(category=None):
            """
            Generate names inspired by magic, planets, and chemical elements.

            Args:
                category: 'magical', 'planet', 'element', or None for random

            Returns:
                A thematic name string
            """

            categories = {
                'magical': {
                    'prefixes': ['Astr', 'Lum', 'Cryp', 'Mysti', 'Arcane', 'Syl', 'Ether', 'Celes', 'Phos', 'Nyx'],
                    'roots': ['wick', 'mancy', 'dor', 'vel', 'mor', 'cal', 'ton', 'stra', 'gen', 'flux'],
                    'suffixes': ['ia', 'us', 'on', 'ix', 'ara', 'eth', 'ys', 'ium', 'or', 'ax'],
                },
                'planet': {
                    'prefixes': ['Zer', 'Kep', 'Prox', 'Sig', 'Tau', 'Vor', 'Glit', 'Sol', 'Ter', 'Neb'],
                    'roots': ['mar', 'vel', 'ion', 'sus', 'ton', 'dros', 'plex', 'tus', 'mus', 'ris'],
                    'suffixes': ['a', 'e', 'is', 'us', 'or', 'ix', 'ar', 'on', 'yx', 'ia'],
                },
                'element': {
                    'prefixes': ['Chrom', 'Hydr', 'Ferr', 'Aur', 'Arg', 'Sulf', 'Cyan', 'Xen', 'Rad', 'Volt'],
                    'roots': ['ox', 'id', 'ate', 'ite', 'ate', 'yl', 'ene', 'ane', 'ous', 'ic'],
                    'suffixes': ['ine', 'ide', 'ate', 'ite', 'ium', 'ous', 'ic', 'on', 'um', 'ene'],
                },
            }

            if category is None:
                category = random.choice(list(categories.keys()))
            elif category not in categories:
                raise ValueError("Category must be 'magical', 'planet', 'element', or None")

            parts = categories[category]
            prefix = random.choice(parts['prefixes'])
            root = random.choice(parts['roots'])
            suffix = random.choice(parts['suffixes'])

            name = (prefix + root + suffix).capitalize()
            return name

        return generate_magical_name()


def create_view(bp):
    view = AIPromptsView('prompts', store='models')
    view.create_routes(bp)
