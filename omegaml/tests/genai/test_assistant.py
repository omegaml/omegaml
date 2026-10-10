from unittest import TestCase

from omegaml.backends.genai.assistant import Assistant, AssistantBackend
from omegaml.tests.util import OmegaTestMixin


class AssistantTests(OmegaTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.om.models.register_backend(AssistantBackend.KIND, AssistantBackend)

    def test_assistant(self):
        om = self.om

        def weather(location):
            return f'the weather in {location} is nice'

        self.om.models.put(weather, 'tools/weather')
        self.om.models.put('openai+http://localhost/mymodel', 'llms/mymodel')
        obj = Assistant(model='llms/mymodel', tools=['weather'])
        meta = om.models.put(obj, 'assistants/test')
        self.assertEqual(meta.kind, AssistantBackend.KIND)
        self.assertEqual(meta.attributes['model'], 'llms/mymodel')
        self.assertEqual(meta.attributes['tools'], ['weather'])
        obj_ = om.models.get('assistants/test')
        self.assertIsInstance(obj_, Assistant)
        self.assertEqual(obj_.model, 'llms/mymodel')
        self.assertEqual(obj_.tools, ['weather'])
        self.assertIn('weather', (f.__name__ for f in obj_._model.tools))
