from omegaml.backends.genai import GenAIModelHandler

class MyHandler(GenAIModelHandler):
    def complete(self, *args, **kwargs):
       return dict(content='hello')
