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


class JobResource(CQRSApiMixin, OmegaResourceMixin, Resource):
    content = DictField(attribute='content', readonly=False, blank=True,
                        null=True, help_text='Notebook content')

    class Meta:
        list_allowed_methods = ['get']
        detail_allowed_methods = ['get', 'post', 'delete']
        resource_name = 'job'
        authentication = ApiKeyAuthentication()

    @cqrsapi(allowed_methods=['post'])
    def run(self, request, *args, **kwargs):
        """
        Run a job
        """
        om = self.get_omega(request)
        name = kwargs.get('pk')
        try:
            result = om.runtime.job(name).run()
            result.get()
        except Exception as e:
            raise ImmediateHttpResponse(HttpBadRequest(str(e)))
        else:
            meta = om.jobs.metadata(name)
            data = self._get_job_detail(meta)
        return self.create_response(request, data)

    def get_detail(self, request, **kwargs):
        """
        get job information
        """
        name = kwargs.get('pk')
        om = self.get_omega(request)
        meta = om.jobs.metadata(name)
        data = self._get_job_detail(meta)
        content = om.jobs.get(name)
        data['content'] = content
        return self.create_response(request, data)

    def get_list(self, request, **kwargs):
        """
        get list of jobs
        """
        om = self.get_omega(request)
        jobs = om.jobs.list(raw=True)
        objs = [self._get_job_detail(job) for job in jobs]
        data = {
            'meta': {
                'limit': 20,
                'next': None,
                'offset': 0,
                'previous': None,
                'total_count': len(objs),
            },
            'objects': objs,
        }
        return self.create_response(request, data)

    def post_detail(self, request, **kwargs):
        """
        create a new job
        """
        name = kwargs.get('pk')
        om = self.get_omega(request)
        try:
            code = self.deserialize(request, request.body).get('code')
            if not code:
                raise ImmediateHttpResponse(
                    HttpBadRequest(str("Need job code to create a new job ")))
        except Exception as e:
            raise ImmediateHttpResponse(str(e))
        cells = []
        cells.append(v4.new_code_cell(source=code))
        notebook = v4.new_notebook(cells=cells)
        meta = om.jobs.put(notebook, name)
        data = self._get_job_detail(meta)
        return self.create_response(request, data, response_class=HttpCreated)

    @cqrsapi(allowed_methods=['get'])
    def report(self, request, **kwargs):
        """
        get a html report of results
        """
        om = self.get_omega(request)
        name = kwargs.get('pk')
        body, resources = om.jobs.export(name, 'memory', format='html')
        data = {
            'name': name,
            'content': body,
        }
        return self.create_response(request, data)

    def _get_job_detail(self, meta):
        data = {
            'name': meta.name,
            'job_results': meta.attributes.get('job_results', {}),
            'job_runs': meta.attributes.get('job_runs', []),
            'created': meta.created,
        }
        if 'source_job' in meta.attributes:
            data['source_job'] = meta.attributes['source_job']
        return data
