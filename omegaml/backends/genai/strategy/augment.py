from uuid import uuid4

from jinja2.sandbox import SandboxedEnvironment

from omegaml.backends.genai.retrieval.index import DocumentIndex
from omegaml.util import utcnow


class AugmentationMixin:
    @property
    def _default_template(self):
        return """
        {% if documents -%} 
            documents found: {{ documents }} 
        {%- endif %} 
        {{ prompt }}
        """

    def _system_message(self, prompt, conversation_id=None):
        return {
            "role": self.strategy['system_role'],
            "content": prompt,
            "conversation_id": conversation_id or uuid4().hex,
        }

    def _augment_prompt(self, prompt, documents: DocumentIndex = None, query=None, template=None):
        query = query or prompt
        template = template or self.template
        if not documents:
            context = dict(prompt=prompt, query=query, documents=None, datetime=utcnow())
            return self._resolve_template(template, **context)
        retrieve_kwargs = self.strategy.get('retrieve', {})
        docs = documents.retrieve(query, **retrieve_kwargs)
        if docs:
            documents = '\n\n'.join(d.get('text') for d in docs)
        else:
            documents = '(no documents found)'
        context = dict(prompt=prompt, query=query, documents=documents, datetime=utcnow())
        return self._resolve_template(template, **context)

    def _resolve_template(self, template, **context):
        env = SandboxedEnvironment()
        template = env.from_string(template)
        return template.render(**context).strip()

    def _augment_message(self, message, documents: DocumentIndex = None, query=None, template=None):
        augmented = self._augment_prompt(
            message.get('content', ''), documents=documents, query=query, template=template
        )
        message['content'] = augmented if augmented else message.get('content')
        return message
