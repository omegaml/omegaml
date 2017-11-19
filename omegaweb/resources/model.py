from sklearn.exceptions import NotFittedError
from tastypie.authentication import ApiKeyAuthentication
from tastypie.exceptions import ImmediateHttpResponse
from tastypie.fields import CharField, ListField
from tastypie.http import HttpBadRequest
from tastypie.resources import Resource

from omegaweb.resources.omegamixin import OmegaResourceMixin

from .util import BundleObj


class ModelResource(OmegaResourceMixin, Resource):
    datax = CharField(attribute='datax', blank=True, null=True)
    datay = CharField(attribute='datay', blank=True, null=True)
    result = ListField(attribute='result', readonly=True, blank=True,
                       null=True)

    class Meta:
        list_allowed_methods = ['get']
        detail_allowed_methods = ['get', 'put', 'delete']
        resource_name = 'model'
        authentication = ApiKeyAuthentication()

    def obj_get(self, bundle, **kwargs):
        """
        get a prediction
        """
        om = self.get_omega(bundle)
        name = kwargs.get('pk')
        query = bundle.request.GET
        datax = query.get('datax') or bundle.data.get('datax')
        try:
            result = om.runtime.model(name).predict(datax)
            data = result.get()
        except NotFittedError as e:
            raise ImmediateHttpResponse(HttpBadRequest(str(e)))
        else:
            bundle.datax = datax
            # if we have a list of lists with 1 dimension, e.g. [[1], [2]]
            # return as a single list, i.e. [1]
            if data.shape[1] == 1:
                data = data[:, 0]
            bundle.result = data.tolist()
        return bundle

    def obj_update(self, bundle, **kwargs):
        """
        train a model
        """
        om = self.get_omega(bundle)
        name = kwargs.get('pk')
        query = bundle.request.GET
        datax = query.get('datax') or bundle.data.get('datax')
        datay = query.get('datay') or bundle.data.get('datay')
        result = om.runtime.model(name).fit(datax, datay)
        data = result.get()
        bundle.result = [data]
        return bundle
