"""
REST API to models
"""
import json

from tastypie.authentication import ApiKeyAuthentication, MultiAuthentication, SessionAuthentication
from tastypie.fields import CharField, ListField, DictField
from tastypie.http import HttpCreated
from tastypie.resources import Resource

from omegaml.backends.restapi.asyncrest import AsyncResponseMixinTastypie
from omegaml.util import load_class
from tastypiex.jwtauth import JWTAuthentication
from omegaweb.resources.omegamixin import OmegaResourceMixin
from tastypiex.cqrsmixin import CQRSApiMixin, cqrsapi


class ModelResource(CQRSApiMixin, OmegaResourceMixin, AsyncResponseMixinTastypie, Resource):
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
        authentication = MultiAuthentication(ApiKeyAuthentication(),
                                             JWTAuthentication(),
                                             SessionAuthentication())
        result_uri = '/api/v1/task/{id}/result'

    @cqrsapi(allowed_methods=['put', 'get'])
    def predict(self, request, *args, **kwargs):
        """
        predict from model

        HTTP GET :code:`/model/<name>/predict/?datax=dataset-name`

        where

        * :code:`datax` is the name of the features dataset
        """
        return self.create_response_from_resource(request, '_generic_model_resource', 'predict', *args, **kwargs)

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
        return self.create_response_from_resource(request, '_generic_model_resource', 'fit', *args, **kwargs)

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
        return self.create_response_from_resource(request, '_generic_model_resource', 'partial_fit', *args, **kwargs)

    @cqrsapi(allowed_methods=['get'])
    def score(self, request, *args, **kwargs):
        """
        score a model

        HTTP GET :code:`/model/<name>/score/?datax=dataset-name&datay=dataset-name`

        where

        * :code:`datax` is the name of the features test dataset
        * :code:`datay` are the true labels of the test dataset
        """
        return self.create_response_from_resource(request, '_generic_model_resource', 'score', *args, **kwargs)

    @cqrsapi(allowed_methods=['get'])
    def decision_function(self, request, *args, **kwargs):
        """
        call the decision function of a model

        HTTP GET :code:`/model/<name>/score/?datax=dataset-name&datay=dataset-name`

        where

        * :code:`datax` is the name of the features test dataset
        """
        return self.create_response_from_resource(request, '_generic_model_resource', 'decision_function', *args,
                                                  **kwargs)

    @cqrsapi(allowed_methods=['get'])
    def transform(self, request, *args, **kwargs):
        """
        transform a model

        HTTP GET :code:`/model/<name>/transfer/?datax=dataset-name`

        where

        * :code:`datax` is the name of the features test dataset
        """
        return self.create_response_from_resource(request, '_generic_model_resource', 'transform', *args, **kwargs)

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
