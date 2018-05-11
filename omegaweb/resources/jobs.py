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


class JobResource(CQRSApiMixin, OmegaResourceMixin, Resource):

    """
    Job resource implements the REST API to omegaml.jobs
    """
    content = DictField(attribute='content', readonly=False, blank=True,
                        null=True, help_text='Notebook content or report body')
    """
    the contents of the job's notebook, or the body of a report
    """

    class Meta:
        list_allowed_methods = ['get']
        detail_allowed_methods = ['get', 'post', 'delete']
        resource_name = 'job'
        authentication = ApiKeyAuthentication()

    @cqrsapi(allowed_methods=['post'])
    def run(self, request, *args, **kwargs):
        """
        Run a job

        HTTP POST :code:`/job/<name>/run/`
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

        HTTP GET :code:`/job/<name>/`

        Result is a dictionary of 

        { content => notebook JSON }

        For notebook JSON details, see https://nbformat.readthedocs.io/en/latest/
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

        HTTP GET :code:`/job/`

        Result is a dictionary of { meta => meta data, objects => list of 
        objects }

        :code:`objects` is a list of 

          >>> {
            'name': name of object
            'job_results': dictionary of results as { status => dataset }
            'job_runs': list of run time timestamps  
            'created': meta.created,
          }
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

        HTTP POST :code:`/job/name/`

        Pass the verbatim Python source code text as the :code:`code` body
        element.

        This creates a new job as a IPython notebook
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

        HTTP GET :code:`/job/name/report/`

        This returns an HTML representation of a notebook. Note that this
        does not run the notebook. To get the results of a notebook 
        execution in HTML format, get it's result.  
        """
        om = self.get_omega(request)
        name = kwargs.get('pk')
        format = request.GET.get('fmt', 'html')
        body, resources = om.jobs.export(name, 'memory', format=format)
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
