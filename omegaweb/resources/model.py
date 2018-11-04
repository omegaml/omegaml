"""
REST API to models
"""
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
    """
    ModelResource implements the REST API to omegaml.models
    """

    datax = CharField(attribute='datax', blank=True, null=True,
                      help_text='The name of X dataset')
    """ the name of the X dataset
    
    The dataset must exist 
    """

    datay = CharField(attribute='datay', blank=True, null=True,
                      help_text='The name of Y dataset')
    """ the name of the Y dataset
    
    The dataset must exist
    """

    result = ListField(attribute='result', readonly=True, blank=True,
                       null=True, help_text='the list of results')
    """ the result 
    
    result is a list of result values 
    """

    model = DictField(attribute='model', readonly=True, blank=True,
                      null=True, help_text='Dictionary of model details')
    """
    Metadata on the model
    
    dictionary of the model 
    
    :Example:
    
       > { name => name of the model,
           kind => kind of model,
           created => date of creation }

    """

    pipeline = ListField(attribute='model', blank=True,
                         null=True, help_text='List of pipeline steps')
    """
    Pipeline steps (on POST only)
    
    list of steps in the pipeline, as :code:`[ step, ... ]` 
    
    * :code:`step` is a list of :code:`[ type, kwargs ]`.
    * :code:`type` is the type of the model. the type must be loadable
      by Python, e.g. `sklearn.linear_model.LinearRegression`
    * :code:`kwargs` is a dictionary of keyword arguments used
      to initialize the model class
    
    """

    class Meta:
        list_allowed_methods = ['get', 'post']
        detail_allowed_methods = ['get', 'delete']
        resource_name = 'model'
        authentication = ApiKeyAuthentication()

    @cqrsapi(allowed_methods=['get', 'put'])
    def predict(self, request, *args, **kwargs):
        """
        predict from model

        HTTP GET :code:`/model/<name>/predict/?datax=dataset-name`

        where 

        * :code:`datax` is the name of the features dataset
        """
        om = self.get_omega(request)
        name = kwargs.get('pk')
        datax = request.GET.get('datax')
        try:
            result = om.runtime.model(name).predict(datax)
            data = result.get()
        except NotFittedError as e:
            raise ImmediateHttpResponse(HttpBadRequest(str(e)))
        else:
            # if we have a single column, get as a list
            if len(data.shape) > 1 and data.shape[1] == 1:
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
        fit a model

        HTTP PUT :code:`/model/<name>/fit/?datax=dataset-name&datay=dataset-name`

        where 

        * :code:`datax` is the name of the features dataset
        * :code:`datay` is the name of the target dataset (if required by
          the algorithm)
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
        partially fit a model

        HTTP PUT :code:`/model/<name>/partial_fit/?datax=dataset-name&datay=dataset-name`

        where 

        * :code:`datax` is the name of the features dataset
        * :code:`datay` is the name of the target dataset (if required by
          the algorithm)
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
        score a model

        HTTP GET :code:`/model/<name>/score/?datax=dataset-name&datay=dataset-name`

        where 

        * :code:`datax` is the name of the features test dataset
        * :code:`datay` are the true labels of the test dataset
        """
        om = self.get_omega(request)
        name = kwargs.get('pk')
        query = request.GET
        datax = query.get('datax')
        datay = query.get('datay')
        try:
            result = om.runtime.model(name).score(datax, datay)
            result_data = result.get()
        except NotFittedError as e:
            raise ImmediateHttpResponse(HttpBadRequest(str(e)))
        data = {
            'datax': datax,
            'datay': datay,
            'result': [result_data]
        }
        return self.create_response(request, data)

    @cqrsapi(allowed_methods=['get'])
    def decision_function(self, request, *args, **kwargs):
        """
        call the decision function of a model

        HTTP GET :code:`/model/<name>/score/?datax=dataset-name&datay=dataset-name`

        where

        * :code:`datax` is the name of the features test dataset
        """
        om = self.get_omega(request)
        name = kwargs.get('pk')
        query = request.GET
        datax = query.get('datax')
        try:
            result = om.runtime.model(name).decision_function(datax)
            result_data = result.get()
        except NotFittedError as e:
            raise ImmediateHttpResponse(HttpBadRequest(str(e)))
        data = {
            'datax': datax,
            'result': [result_data]
        }
        return self.create_response(request, data)

    @cqrsapi(allowed_methods=['get'])
    def transform(self, request, *args, **kwargs):
        """
        transform a model

        HTTP GET :code:`/model/<name>/transfer/?datax=dataset-name`

        where 

        * :code:`datax` is the name of the features test dataset
        """
        om = self.get_omega(request)
        name = kwargs.get('pk')
        query = request.GET
        datax = query.get('datax')
        datay = query.get('datay')
        try:
            result = om.runtime.model(name).transform(datax, datay)
            result_data = result.get()
        except NotFittedError as e:
            raise ImmediateHttpResponse(HttpBadRequest(str(e)))
        data = {
            'datax': datax,
            'datay': datay,
            'result': result_data.tolist()
        }
        return self.create_response(request, data)

    def get_detail(self, request, **kwargs):
        """
        get model information

        HTTP GET :code:`/model/<name>/`
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

    def get_list(self, request, **kwargs):
        """
        list all models

        HTTP GET :code:`/model/<name>/`
        """
        om = self.get_omega(request)
        objs = [{
                    'model': {
                        'name': meta.name,
                        'kind': meta.kind,
                        'created': '{}'.format(meta.created),
                        'bucket': meta.bucket,
                    }
                } for meta in om.models.list(raw=True)
                ]
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

    def post_list(self, request, **kwargs):
        """
        create a model

        HTTP POST :code:`/model/<name>/`

        Pass the model specification as the dictionary of 

        * :code:`name` - see name field<
        * :code: `pipeline` - see pipeline field

        Note the method attempts to create a scikit-learn pipeline from
        your specification. 
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
            model_cls = MODEL_MAP.get(modelkind, modelkind)
            if model_cls:
                model_cls = load_class(model_cls)
            model = model_cls(**kwargs)
            om.models.put(model, name)
        data = self._getmodel_detail(request, name)
        return self.create_response(request, data, response_class=HttpCreated)
