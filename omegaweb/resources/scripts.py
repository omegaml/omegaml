"""
REST API to jobs
"""

from tastypie.authentication import ApiKeyAuthentication
from tastypie.exceptions import ImmediateHttpResponse
from tastypie.http import HttpBadRequest
from tastypie.resources import Resource

from omegaml.backends.restapi.asyncrest import AsyncResponseMixinTastypie
from omegaweb.resources.omegamixin import OmegaResourceMixin
from tastypiex.cqrsmixin import CQRSApiMixin, cqrsapi


class ScriptResource(CQRSApiMixin, OmegaResourceMixin, AsyncResponseMixinTastypie, Resource):
    """
    Script resource implements the REST API to omegaml.scripts
    """

    class Meta:
        list_allowed_methods = ['post']
        detail_allowed_methods = []
        resource_name = 'script'
        authentication = ApiKeyAuthentication()
        result_uri = '/api/v1/task/{id}/result'

    @cqrsapi(allowed_methods=['post'])
    def run(self, request, *args, **kwargs):
        """
        Run a script

        HTTP POST :code:`/script/<name>/run/`
        """
        return self.create_response_from_resource(request, '_generic_script_resource', 'run', *args, **kwargs)

        om = self.get_omega(request)
        name = kwargs.pop('pk')
        try:
            result = om.runtime.script(name).run(**request.GET.dict(),
                                                 __format='python')
            data = result.get()
        except Exception:
            raise ImmediateHttpResponse(HttpBadRequest(str(e)))
        return self.create_response(request, data)
