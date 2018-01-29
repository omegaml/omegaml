import json

from sklearn.exceptions import NotFittedError
from tastypie.authentication import ApiKeyAuthentication
from tastypie.exceptions import ImmediateHttpResponse
from tastypie.fields import CharField, ListField, DictField
from tastypie.http import HttpBadRequest, HttpCreated, HttpAccepted
from tastypie.resources import Resource

from omegaml.util import load_class
from omegaweb.resources.omegamixin import OmegaResourceMixin
from tastypiex.cqrsmixin import CQRSApiMixin, cqrsapi


class ModelResource(CQRSApiMixin, OmegaResourceMixin, Resource):
    datax = CharField(attribute='datax', blank=True, null=True,
                      help_text='The name of X dataset')
    datay = CharField(attribute='datay', blank=True, null=True,
                      help_text='The name of Y dataset')
    result = ListField(attribute='result', readonly=True, blank=True,
                       null=True, help_text='the list of results')
    model = DictField(attribute='model', readonly=True, blank=True,
                      null=True, help_text='Dictionary of model details')
    pipeline = ListField(attribute='model', blank=True,
                         null=True, help_text='List of pipeline steps')

    class Meta:
        list_allowed_methods = ['get', 'post']
        detail_allowed_methods = ['get', 'delete']
        resource_name = 'model'
        authentication = ApiKeyAuthentication()

    @cqrsapi(allowed_methods=['get'])
    def predict(self, request, *args, **kwargs):
        """
        foo
        """
        om = self.get_omega(request)
        name = kwargs.get('pk')
        query = request.GET
        datax = query.get('datax')
        try:
            result = om.runtime.model(name).predict(datax)
            data = result.get()
        except NotFittedError as e:
            raise ImmediateHttpResponse(HttpBadRequest(str(e)))
        else:
            if data.shape[1] == 1:
                data = data[:, 0]
            data = data.tolist()
            result = {
                'datax': datax,
                'datay': None,
                'result': data
            }
        return self.create_response(request, result)

    @cqrsapi(allowed_methods=['put'])
    def fit(self, request, *args, **kwargs):
        """
        foo
        """
        om = self.get_omega(request)
        name = kwargs.get('pk')
        query = request.GET
        datax = query.get('datax')
        datay = query.get('datay')
        result = om.runtime.model(name).fit(datax, datay)
        meta = result.get()
        data = {
            'datax': datax,
            'datay': datay,
            'result': 'ok' if meta else 'error',
        }
        return self.create_response(request, data, response_class=HttpAccepted)

    @cqrsapi(allowed_methods=['put'])
    def partial_fit(self, request, *args, **kwargs):
        """
        foo
        """
        om = self.get_omega(request)
        name = kwargs.get('pk')
        query = request.GET
        datax = query.get('datax')
        datay = query.get('datay')
        result = om.runtime.model(name).partial_fit(datax, datay)
        data = {
            'datax': datax,
            'datay': datay,
            'result': [result.get()]
        }
        return self.create_response(request, data, response_class=HttpAccepted)

    @cqrsapi(allowed_methods=['get'])
    def score(self, request, *args, **kwargs):
        """
        foo
        """
        om = self.get_omega(request)
        name = kwargs.get('pk')
        query = request.GET
        datax = query.get('datax')
        datay = query.get('datay')
        result = om.runtime.model(name).score(datax, datay)
        data = {
            'datax': datax,
            'datay': datay,
            'result': [result.get()]
        }
        return self.create_response(request, data)

    @cqrsapi(allowed_methods=['get'])
    def transform(self, request, *args, **kwargs):
        """
        foo
        """
        om = self.get_omega(request)
        name = kwargs.get('pk')
        query = request.GET
        datax = query.get('datax')
        datay = query.get('datay')
        result = om.runtime.model(name).transform(datax, datay)
        data = {
            'datax': datax,
            'datay': datay,
            'result': [result.get()]
        }
        return self.create_response(request, data)

    def get_detail(self, request, **kwargs):
        """
        get model information
        """
        name = kwargs.get('pk')
        data = self._getmodel_detail(request, name)
        return self.create_response(request, data)

    def _getmodel_detail(self, request, name):
        om = self.get_omega(request)
        meta = om.models.metadata(name)
        data = {
            'model': {
                'name': meta.name,
                'kind': meta.kind,
                'created': '{}'.format(meta.created),
                'bucket': meta.bucket,
            }
        }
        return data

    def post_list(self, request, **kwargs):
        """
        create a model
        """
        om = self.get_omega(request)
        data = json.loads(request.body.decode('latin1'))
        name = data.get('name')
        pipeline = data.get('pipeline')
        # TODO extend with more models
        MODEL_MAP = {
            'LinearRegression': 'sklearn.linear_model.LinearRegression',
            'LogisticRegression': 'sklearn.linear_model.LogisticRegression',
        }
        # TODO setup a pipeline instead of singular models
        for step in pipeline:
            modelkind, kwargs = step
            model_cls = MODEL_MAP.get(modelkind)
            if model_cls:
                model_cls = load_class(model_cls)
            model = model_cls(**kwargs)
            om.models.put(model, name)
        data = self._getmodel_detail(request, name)
        return self.create_response(request, data, response_class=HttpCreated)
