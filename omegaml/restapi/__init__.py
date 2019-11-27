import datetime
import flask
import numpy as np
import pandas as pd
import six
from flask import request
from flask_restplus import Resource, fields
from mongoengine import DoesNotExist

import omegaml as om
from omegaml.backends.restapi.model import GenericModelResource
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


class OmegaResourceMixin(object):
    """
    helper mixin to resolve the request to a configured Omega instance
    """

    @property
    def _omega(self):
        bucket = flask.request.headers.get('bucket')
        return om.setup()[bucket]

    @property
    def _generic_model_resource(self):
        return GenericModelResource(self._omega)


@api.route('/api/v1/ping')
class PingResource(Resource):
    def get(self):
        dt = datetime.datetime.now()
        return {'ping': dt.isoformat()}


@api.route('/api/v1/model/<string:model_id>/predict')
class ModelResource(OmegaResourceMixin, Resource):
    @api.expect(PredictInput, validate=False)
    @api.marshal_with(PredictOutput)
    def put(self, model_id):
        query = flask.request.args
        payload = api.payload
        return self._generic_model_resource.put(model_id, query, payload)


@api.route('/api/v1/dataset/<string:dataset_id>')
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
