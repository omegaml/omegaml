import apispec
import json
import yaml
from apispec import APISpec
from apispec.ext.marshmallow import MarshmallowPlugin

from omegaml.runtimes.mixins.swagger.helpers import SpecFromModelHelper, SpecFromDatasetHelper, SpecFromScriptHelper, \
    SpecFromServiceHelper


class SwaggerGenerator:
    def __init__(self, om):
        self.om = om
        self.spec = self._make_spec()

    def _make_spec(self, title=None, version='1.0.0'):
        title = title or 'omega-ml service'
        # Create an APISpec
        spec = APISpec(
            title=title,
            version=version,
            openapi_version="2.0",
            plugins=[MarshmallowPlugin()],
        )
        return spec

    def _resource_helper(self, resource, as_service=False):
        RESOURCE_SPEC_HELPERS = {
            'model': SpecFromModelHelper,
            'dataset': SpecFromDatasetHelper,
            'script': SpecFromScriptHelper,
            'service': SpecFromServiceHelper,
        }
        handler = resource if not as_service else 'service'
        return RESOURCE_SPEC_HELPERS[handler]

    def to_json(self, indent=2, stream=None):
        dump = json.dump if stream else json.dumps
        return dump(self.spec.to_dict(), indent=indent)

    def to_yaml(self, stream=None):
        return yaml.dump(self.spec.to_dict(), stream=stream)

    def to_dict(self, **kwargs):
        return self.spec.to_dict()

    def include(self, path, as_service=False):
        for obj in self.om.list(path.replace('datasets/', 'data/')):
            self._include_obj(obj.replace('data/', 'datasets/'), as_service=as_service)

    def validate(self):
        apispec.utils.validate_spec(self.spec)

    def _include_obj(self, path, as_service=False):
        prefix, name = path.split('/', 1)
        store = getattr(self.om, prefix)
        meta = store.metadata(name)
        # cut the s (models => model, datasets => dataset)
        resource = prefix[:-1]
        signature = meta.attributes.get('signature', {})
        spec = self.spec
        resource_helper = self._resource_helper(resource, as_service)
        resource_helper(meta, name, resource, signature, spec, store).render()

    @staticmethod
    def build_swagger(self, include='*', format='yaml', file=None, as_service=False):
        gen = SwaggerGenerator(self.omega)
        includes = include.split(',') if isinstance(include, str) else include
        for path in includes:
            gen.include(path, as_service=as_service)
        formatter = {
            'yaml': gen.to_yaml,
            'dict': gen.to_dict,
            'json': gen.to_json,
        }
        return formatter.get(format)(stream=file)

