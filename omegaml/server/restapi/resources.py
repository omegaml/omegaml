import builtins
import datetime
import flask
import numpy as np
import os
import pandas as pd
import re
from flask import Blueprint, render_template, url_for
from flask_restx import Resource, fields, Api
from flask_restx.apidoc import apidoc
from mongoengine import DoesNotExist
from omegaml.backends.restapi.asyncrest import AsyncTaskResourceMixin, AsyncResponseMixin, resolve
from omegaml.server.restapi.util import OmegaResourceMixin, strict, AnyObject
from omegaml.util import isTrue
from urllib.parse import unquote, urljoin
from werkzeug.exceptions import NotFound

# required to get payload from request
# -- see OmegaResourceMixin.get_query_payload
omega_api = None


class RemoteableSwaggerApi(Api):
    def render_doc(self):
        return render_template("swagger-ui.html", title=self.title,
                               specs_url=self.remote_specs_url or self.specs_url)


def create_app(url_prefix=None):
    """ create the omega-api blueprint

    This creates the requires blueprint for the Swagger UI and the omegaml REST API.
    The blueprint is created with the given url_prefix, or the default '/api'. The
    swagger UI is served at /api/doc, the API is served at /api/v1.

    If the environment variable OMEGA_RESTAPI_URL is set, the API will be served from
    the given URL. This is useful when the API is served from the omegaml hub

    """
    global omega_api
    omega_bp = Blueprint('omega-api',
                         __name__,
                         url_prefix=url_prefix)
    omega_api = api = RemoteableSwaggerApi(omega_bp, doc='/api/doc', version='1.0',
                                           default='omegaml-restapi',
                                           default_label='omega-ml REST API')
    apidoc.url_prefix = url_prefix
    # set up swagger ui, if not local
    # -- swagger.json is provided by the hub
    hub_url = os.environ.get('OMEGA_RESTAPI_URL')
    hub_api_uri = os.environ.get('OMEGA_RESTAPI_SPECS_URI', '/api/doc/v1/swagger/specs/swagger.json')
    omega_api.remote_specs_url = urljoin(hub_url, hub_api_uri) if hub_url else None

    @omega_bp.route('/api/docs')
    def api_docs():
        # convenience redirect to the API documentation
        return flask.redirect(url_for('omega-api.doc'), code=302)

    @api.documentation
    def custom_ui():
        swagger_json_url = url_for('omega-api.specs')
        return render_template("swagger-ui.html", title=api.title, specs_url=swagger_json_url)

    if omega_api.remote_specs_url is None:
        # only add api endpoints if we are not serving the hub's api
        add_api_endpoints(api)

    return omega_bp


def add_api_endpoints(api):
    PredictInput = strict(api).model('ModelInputSchema', {
        'columns': fields.List(fields.String),
        'data': fields.List(fields.Raw),
        'shape': fields.List(fields.Integer),
    })

    PredictOutput = api.model('PredictOutput', {
        'model': fields.String,
        'result': fields.Raw,
        'resource_uri': fields.String,
    })

    TaskInput = strict(api).model('TaskInput', {
        'resource_uri': fields.String,
    })

    TaskOutput = strict(api).model('TaskOutput', {
        'task_id': fields.String,
        'status': fields.String,
        'response': fields.Raw
    })

    DatasetInput = api.model('DatasetInput', {
        'data': fields.Raw,
        'dtypes': fields.Raw,
        'append': fields.Boolean,
    })

    DatasetIndex = api.model('DatasetIndex', {
        'values': fields.List(fields.Raw),
        'type': fields.String,
    })

    DatasetQueryOutput = api.model('DatasetQueryOutput', {
        'data': fields.Raw,
        'index': fields.Nested(DatasetIndex)
    })

    ScriptInput = api.model('ScriptInput', {
    })

    ScriptOutput = api.model('ScriptOutput', {
        'resource_uri': fields.String,
        'script': fields.String,
        'result': fields.Raw,
        'runtimes': fields.Float,
        'started': fields.DateTime,
        'ended': fields.DateTime,
    })

    ServiceInput = api.model('ServiceInput', {
    })

    ServiceOutput = api.model('ServiceOutput', {
        '*': AnyObject
    })

    JobInput = api.model('JobInput', {
    })

    JobOutput = api.model('JobOutput', {
        'resource_uri': fields.String,
        'job': fields.String,
        'source_job': fields.String,
        'job_results': fields.Raw,
        'job_runs': fields.List(fields.Raw),
        'created': fields.DateTime,
    })

    @api.errorhandler(Exception)
    def errorhandler(e):
        # if we have a json serializable description, use that as a response
        # as it will have been validated by the API already. Otherwise default to the
        # standard behavior of returning a string representation of the exception
        # see https://flask-restx.readthedocs.io/en/latest/errors.html
        description = getattr(e, 'description', repr(e))
        if isinstance(description, dict):
            return description, getattr(e, 'code', 400)
        if isinstance(description, list):
            # flask error handler will extract as body
            setattr(e, 'data', description)
            return {}, getattr(e, 'code', 400)
        return {'message': description}, getattr(e, 'code', 400)

    @api.route('/api/v1/ping')
    class PingResource(Resource):
        def get(self):
            dt = datetime.datetime.now()
            return {'ping': dt.isoformat()}

    @api.route('/api/v1/task/<string:taskid>/<string:action>')
    class TaskResource(OmegaResourceMixin, AsyncTaskResourceMixin, Resource):
        @api.expect(TaskInput, validate=False)
        @api.marshal_with(TaskOutput)
        def get(self, taskid, action):
            return self.process_task_action(taskid, action, request=flask.request)

        def resolve_resource_method(self, taskid, context):
            # this maps a tasks resource_uri to a resource method to resolve the async result
            resourceUri = api.payload.get('resource_uri')
            path, res_kwargs = resolve(resourceUri)
            URI_METHOD_MAP = {
                r'/api/.*/model/.*/.*/?$': ('_generic_model_resource', 'prepare_result', {'pk': 'model_id'}),
                r'/api/.*/job/.*/run/?$': ('_generic_job_resource', 'prepare_result', {'pk': 'job_id'}),
                r'/api/.*/script/.*/run/?$': ('_generic_script_resource', 'prepare_result', {'pk': 'script_id'}),
                # services are also exposed as top-level services, see ServiceResoure
                r'/api/.*/service/.*/(.*)?$': ('_generic_service_resource', 'prepare_result', {'pk': 'resource_id'}),
                r'/api/service/.*/(.*)?$': ('_generic_service_resource', 'prepare_result', {'pk': 'resource_id'}),
            }
            for regexp, specs in URI_METHOD_MAP.items():
                if re.match(regexp.replace(r'/', r'\/'), resourceUri):
                    resource_name, method_name, kwargs_map = specs
                    resource_pk = kwargs_map.get('pk')
                    meth = self._get_resource_method(resource_name, method_name)
                    return meth, dict(resource_name=res_kwargs.get(resource_pk))
            raise NotFound('unknown resource {}'.format(resourceUri))

    @api.route('/api/v1/model/<path:model_id>/<string:action>', methods=['GET', 'PUT'])
    @api.route('/api/v1/model/<path:model_id>/', defaults={'action': 'metadata'}, methods=['GET'])
    class ModelResource(OmegaResourceMixin, AsyncResponseMixin, Resource):
        result_uri = '/api/v1/task/{id}/result'

        @api.expect(PredictInput, validate=False)
        @api.marshal_with(PredictOutput)
        def get(self, model_id, action=None):
            return self.create_response_from_resource('_generic_model_resource', action, 'model', model_id)

        @api.expect(PredictInput, validate=False)
        @api.marshal_with(PredictOutput)
        def put(self, model_id, action=None):
            return self.create_response_from_resource('_generic_model_resource', action, 'model', model_id)

    @api.route('/api/v1/script/<path:script_id>/run', methods=['POST'])
    class ScriptResource(OmegaResourceMixin, AsyncResponseMixin, Resource):
        result_uri = '/api/v1/task/{id}/result'

        @api.expect(ScriptInput, validate=False)
        @api.marshal_with(ScriptOutput)
        def post(self, script_id):
            return self.create_response_from_resource('_generic_script_resource', 'run', 'script', script_id)

    @api.route('/api/service/<path:resource_id>', defaults={'action': '*'}, methods=['GET', 'PUT', 'POST', 'DELETE'])
    @api.route('/api/service/<path:resource_id>/', defaults={'action': '*'}, methods=['GET', 'PUT', 'POST', 'DELETE'])
    @api.route('/api/service/<path:resource_id>/<string:action>', methods=['GET', 'PUT', 'POST', 'DELETE'])
    @api.route('/api/v1/service/<path:resource_id>', defaults={'action': '*'}, methods=['GET', 'PUT', 'POST', 'DELETE'])
    @api.route('/api/v1/service/<path:resource_id>/', defaults={'action': '*'},
               methods=['GET', 'PUT', 'POST', 'DELETE'])
    @api.route('/api/v1/service/<path:resource_id>/<string:action>', methods=['GET', 'PUT', 'POST', 'DELETE'])
    # we expose service resources as /api/v1/service and /api/service
    # rationale: this is user-defined, and /v1/ does not make sense in this case
    # however in light of consistency, we also provide /v1/
    class ServiceResource(OmegaResourceMixin, AsyncResponseMixin, Resource):
        result_uri = '/api/v1/task/{id}/result'

        @api.expect(ServiceInput, validate=False)
        @api.marshal_with(ServiceOutput)
        def get(self, resource_id, action):
            action = 'get' if action == '*' else action
            return self.create_response_from_resource('_generic_service_resource', action, 'service', resource_id)

        @api.expect(ServiceInput, validate=False)
        @api.marshal_with(ServiceOutput)
        def post(self, resource_id, action):
            action = 'post' if action == '*' else action
            return self.create_response_from_resource('_generic_service_resource', action, 'service', resource_id)

        @api.expect(ServiceInput, validate=False)
        @api.marshal_with(ServiceOutput)
        def put(self, resource_id, action):
            action = 'put' if action == '*' else action
            return self.create_response_from_resource('_generic_service_resource', action, 'service', resource_id)

        @api.expect(ServiceInput, validate=False)
        @api.marshal_with(ServiceOutput)
        def delete(self, resource_id, action):
            action = 'delete' if action == '*' else action
            return self.create_response_from_resource('_generic_service_resource', action, 'service', resource_id)

    @api.route('/api/v1/job/<path:job_id>/run', methods=['POST'])
    @api.route('/api/v1/job/<path:job_id>/', methods=['GET'])
    @api.route('/api/v1/job/', methods=['GET'], defaults={'job_id': None})
    class JobResource(OmegaResourceMixin, AsyncResponseMixin, Resource):
        result_uri = '/api/v1/task/{id}/result'

        @api.expect(JobInput, validate=False)
        @api.marshal_with(JobOutput)
        def get(self, job_id):
            action = 'list' if job_id is None else 'metadata'
            return self.create_response_from_resource('_generic_job_resource', action, 'job', job_id)

        @api.expect(JobInput, validate=False)
        @api.marshal_with(JobOutput)
        def post(self, job_id):
            return self.create_response_from_resource('_generic_job_resource', 'run', 'job', job_id)

    @api.route('/api/v1/dataset/<path:dataset_id>')
    class DatasetResource(OmegaResourceMixin, Resource):
        # TODO shall implement as a GenericResource, like all other resources
        def _restore_filter(self, om, fltparams, name):
            """
            restore filter kwargs for query in om.datasets.get
            """
            # -- get filters as specified on request query args
            fltkwargs = {k: v for k, v in fltparams.items()
                         if k not in ['orient', 'limit', 'skip', 'page']}
            # -- get dtypes of dataframe and convert filter values
            metadata = om.datasets.metadata(name)
            kind_meta = metadata.kind_meta or {}
            dtypes = kind_meta.get('dtypes')
            # get numpy/python typemap. this is required for Py3 support
            # adopted from https://stackoverflow.com/a/34919415
            np_typemap = {v: getattr(builtins, k)
                          for k, v in np.sctypeDict.items()
                          if k in vars(builtins)}
            for k, v in fltkwargs.items():
                # -- get column name without operator (e.g. x__gt => x)
                col = k.split('__')[0]
                value = unquote(v)
                dtype = dtypes.get(str(col))
                if dtype:
                    # -- get dtyped value and convert to python type
                    value = np_typemap.get(getattr(np, dtype, str), str)(value)
                    fltkwargs[k] = value
            return fltkwargs

        @api.marshal_with(DatasetQueryOutput)
        def get(self, dataset_id):
            om = self._omega
            orient = flask.request.args.get('orient', 'dict')
            fltkwargs = self._restore_filter(om, flask.request.args, dataset_id)
            df = om.datasets.getl(dataset_id, filter=fltkwargs).value
            # get index values as python types to support Py3
            index_values = list(df.index.astype('O').values)
            index_type = type(df.index).__name__
            # get data set values as python types to support Py3
            df = df.reset_index(drop=True)
            df.index = df.index.astype('O')
            # convert nan to None
            # https://stackoverflow.com/a/34467382
            data = df.where(pd.notnull(df), None).astype('O').to_dict(orient)
            return {
                'data': data,
                'index': {
                    'values': index_values,
                    'type': index_type,
                }
            }

        @api.expect(DatasetInput, validate=True)
        @api.response(200, 'updated')
        def put(self, dataset_id):
            om = self._omega
            orient = flask.request.args.get('orient', 'dict')
            if 'append' in flask.request.args:
                append = isTrue(flask.request.args.get('append', 'true'))
            else:
                append = isTrue(api.payload.get('append', 'true'))
            dtypes = api.payload.get('dtypes')
            if orient == 'dict':
                orient = 'columns'
            if dtypes:
                # due to https://github.com/pandas-dev/pandas/issues/14655#issuecomment-260736368
                dtypes = {k: np.dtype(v) for k, v in dtypes.items()}
            df = pd.DataFrame.from_dict(api.payload.get('data'),
                                        orient=orient).astype(dtypes)
            om.datasets.put(df, dataset_id, append=append)
            return '', 200

        @api.response(200, 'updated')
        @api.response(404, 'does not exist')
        def delete(self, dataset_id):
            om = self._omega
            try:
                om.datasets.drop(dataset_id)
            except DoesNotExist:
                status = 404
            else:
                status = 200
            return '', status


omega_bp = create_app()
