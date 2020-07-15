import datetime
import re

import flask
import numpy as np
import pandas as pd
import six
from flask import request
from flask_restplus import Resource, fields
from mongoengine import DoesNotExist
from werkzeug.exceptions import NotFound, BadRequest

import omegaml as om
from omegaml.backends.restapi.asyncrest import AsyncTaskResourceMixin, AsyncResponseMixin, resolve
from omegaml.backends.restapi.job import GenericJobResource
from omegaml.backends.restapi.model import GenericModelResource
from omegaml.backends.restapi.script import GenericScriptResource
from omegaml.restapi.util import strict
from .app import api

isTrue = lambda v: v if isinstance(v, bool) else (
      v.lower() in ['yes', 'y', 't', 'true', '1'])

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


class OmegaResourceMixin(object):
    """
    helper mixin to resolve the request to a configured Omega instance
    """

    def __init__(self, *args, **kwargs):
        self._omega_instance = None
        super().__init__(*args, **kwargs)

    def dispatch_request(self, *args, **kwargs):
        self._omega_instance = None  # always start with a fresh omega instance
        return super().dispatch_request(*args, **kwargs)

    @property
    def _omega(self):
        if self._omega_instance is None:
            bucket = flask.request.headers.get('bucket')
            self._omega_instance = om.setup()[bucket]
        return self._omega_instance

    def get_query_payload(self):
        query = flask.request.args.to_dict()
        payload = api.payload or {}
        return query, payload

    def create_response_from_resource(self, generic_resource, resource_method, resource_name, resource_pk, *args,
                                      **kwargs):
        query, payload = self.get_query_payload()
        async_body = {
            resource_name: resource_pk,
            'result': 'pending',
        }
        try:
            meth = self._get_resource_method(generic_resource, resource_method)
            result = meth(resource_pk, query, payload)
            resp = self.create_maybe_async_response(result, async_body=async_body, **kwargs)
        except Exception as e:
            raise BadRequest(str(e))
        return resp

    def _get_resource_method(self, resource_name, method_name):
        resource = getattr(self, resource_name)
        meth = getattr(resource, method_name)
        return meth

    @property
    def _generic_model_resource(self):
        return GenericModelResource(self._omega, is_async=self.is_async)

    @property
    def _generic_script_resource(self):
        return GenericScriptResource(self._omega, is_async=self.is_async)

    @property
    def _generic_job_resource(self):
        return GenericJobResource(self._omega, is_async=self.is_async)

    @property
    def celeryapp(self):
        return self._omega.runtime.celeryapp


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
            r"/api/.*/model/.*/.*/?$": ('_generic_model_resource', 'prepare_result', {'pk': 'model_id'}),
            r'/api/.*/job/.*/run/?$': ('_generic_job_resource', 'prepare_result_from_run', {'pk': 'job_id'}),
            r'/api/.*/script/.*/run/?$': ('_generic_script_resource', 'prepare_result_from_run', {'pk': 'script_id'}),
        }
        for regexp, specs in URI_METHOD_MAP.items():
            if re.match(regexp.replace(r'/', r'\/'), resourceUri):
                resource_name, method_name, kwargs_map = specs
                meth = self._get_resource_method(resource_name, method_name)
                return meth, res_kwargs
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
    def _restore_filter(self, om, fltparams, name):
        """
        restore filter kwargs for query in om.datasets.get
        """
        # -- get filters as specified on request query args
        fltkwargs = {k: v for k, v in six.iteritems(fltparams)
                     if k not in ['orient', 'limit', 'skip', 'page']}
        # -- get dtypes of dataframe and convert filter values
        metadata = om.datasets.metadata(name)
        kind_meta = metadata.kind_meta or {}
        dtypes = kind_meta.get('dtypes')
        # get numpy/python typemap. this is required for Py3 support
        # adopted from https://stackoverflow.com/a/34919415
        np_typemap = {v: getattr(six.moves.builtins, k)
                      for k, v in np.typeDict.items()
                      if k in vars(six.moves.builtins)}
        for k, v in six.iteritems(fltkwargs):
            # -- get column name without operator (e.g. x__gt => x)
            col = k.split('__')[0]
            value = six.moves.urllib.parse.unquote(v)
            dtype = dtypes.get(str(col))
            if dtype:
                # -- get dtyped value and convert to python type
                value = np_typemap.get(getattr(np, dtype, str), str)(value)
                fltkwargs[k] = value
        return fltkwargs

    @api.marshal_with(DatasetQueryOutput)
    def get(self, dataset_id):
        om = self._omega
        orient = request.args.get('orient', 'dict')
        fltkwargs = self._restore_filter(om, request.args, dataset_id)
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
        orient = request.args.get('orient', 'dict')
        if 'append' in request.args:
            append = isTrue(request.args.get('append', 'true'))
        else:
            append = isTrue(api.payload.get('append', 'true'))
        dtypes = api.payload.get('dtypes')
        if orient == 'dict':
            orient = 'columns'
        if dtypes:
            # due to https://github.com/pandas-dev/pandas/issues/14655#issuecomment-260736368
            dtypes = {k: np.dtype(v) for k, v in six.iteritems(dtypes)}
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
