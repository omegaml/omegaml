"""
REST API to jobs
"""
import json

from nbformat import v4
from tastypie.authentication import ApiKeyAuthentication
from tastypie.exceptions import ImmediateHttpResponse
from tastypie.fields import DictField
from tastypie.http import HttpBadRequest, HttpCreated
from tastypie.resources import Resource

from omegaml.util import load_class
from omegaweb.resources.omegamixin import OmegaResourceMixin
from tastypiex.cqrsmixin import CQRSApiMixin, cqrsapi


class ScriptResource(CQRSApiMixin, OmegaResourceMixin, Resource):
    """
    Script resource implements the REST API to omegaml.scripts
    """

    class Meta:
        list_allowed_methods = ['post']
        detail_allowed_methods = []
        resource_name = 'script'
        authentication = ApiKeyAuthentication()

    @cqrsapi(allowed_methods=['post'])
    def run(self, request, *args, **kwargs):
        """
        Run a script

        HTTP POST :code:`/script/<name>/run/`
        """
        om = self.get_omega(request)
        name = kwargs.pop('pk')
        try:
            result = om.runtime.script(name).run(**request.GET.dict())
            data = result.get()
        except Exception as e:
            raise ImmediateHttpResponse(HttpBadRequest(str(e)))
        return self.create_response(request, data)
