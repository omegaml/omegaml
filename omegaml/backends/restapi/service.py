from omegaml.backends.restapi.job import GenericJobResource
from omegaml.backends.restapi.model import GenericModelResource
from omegaml.backends.restapi.script import GenericScriptResource


class GenericServiceResource:
    """ backend for /api/service/ resources

    Acts as an adapter to a concrete resource, returning only its bare result.
    If the resource (=stored object) has a signature attached, it has already
    been validated by the object's backend or as part of the SignatureMixin.

    If your resource returns a value that is not json serializable (i.e. the
    return value is not a dict), dict(value=<result>) will be returned.
    """
    RESOURCE_MAP = {
        'models/': GenericModelResource,
        'scripts/': GenericScriptResource,
        'jobs/': GenericJobResource,
    }

    def __init__(self, om, is_async=False):
        self.om = om
        self.is_async = is_async

    def doc(self, resource_id, query, payload):
        om = self.om
        meta = self.resolve_object(resource_id)
        specs = om.runtime.swagger(include=meta.name, format='dict', as_service=True)
        return specs

    def predict(self, model_id, query, payload):
        # TODO the validation should be in SignatureMixin (as with scripts), however
        #      this would not match the semantics of runtime ModelProxy/ModelBackend, whereby ModelProxy
        #      stores the payload as a dataset and only passes the dataset name for the ModelBackend to retrieve
        #      Options
        #      1) keep like this - mismatch, validation only works through the service call
        #      2) move all validation to service call - at odds with pre/post call semantics of Backend.perform()
        #      3) refactor model data retrieval to SignatureMixin, away from model backend (or optional)
        #      4) move validation responsibility to backend - not good, removes generality of validation
        #      5) change ModelProxy semantics, i.e. do not store payload as a dataset, but pass as actual payload
        #         (requires a ModelBackend/Mixin.pre_predict to keep semantics with backend)
        self.om.models.validate(model_id, X=payload)
        promise = self.om.runtime.model(model_id).predict(payload, **query)
        result = self.prepare_result(promise.get(), model_id=model_id) if not self.is_async else promise
        self.om.models.validate(model_id, Y=result)
        return result

    def predict_proba(self, model_id, query, payload):
        self.om.models.validate(model_id, X=payload)
        promise = self.om.runtime.model(model_id).predict(payload, **query)
        result = self.prepare_result(promise.get(), model_id=model_id) if not self.is_async else promise
        self.om.models.validate(model_id, Y=result) if isinstance(result, dict) else None
        return result

    def default_action(http_method):
        # decorator to generate a method for each http method
        def do_action(self, resource_id, query, payload):
            meta = self.resolve_object(resource_id)
            # check first method that matches http_method in signature.actions
            actions = meta.attributes.get('signature', {}).get('actions') or {}
            for method, http_methods in actions.items():
                # SignatureMixin.link_datatype
                if http_method in http_methods:
                    meth = getattr(self, method)
                    break
            else:
                # no matching signature.actions found, revert to default for object type
                if meta.prefix == 'models/':
                    meth = self.predict
                elif meta.prefix in ['scripts/', 'jobs/']:
                    meth = self.run
                else:
                    raise ValueError(f'No default action for {meta.prefix}/{resource_id}')
            result = meth(resource_id, query, payload)
            return result

        return do_action

    get = default_action('get')
    post = default_action('post')
    put = default_action('put')
    delete = default_action('delete')

    def run(self, script_id, query, payload):
        promise = self.om.runtime.script(script_id).run(payload, __format='python', **query)
        result = self.prepare_result(promise.get(), script_id=script_id) if not self.is_async else promise
        return result

    def prepare_result(self, result, model_id=None, script_id=None, resource_name=None, **kwargs):
        if script_id or resource_name:
            # FIXME all resource outputs provide 'result', except jobs
            # scripts provide structured task output, not just the result
            data = result.get('job_results') or result.get('result')
        else:
            data = result
        # ensure response is json serializable
        if not isinstance(data, (list, dict, tuple)):
            data = {'data': data}
        return data

    def resolve_object(self, resource_id):
        objects = self.om.list(resource_id, raw=True)
        meta = objects[-1] if objects else None
        if not meta or meta.prefix not in self.RESOURCE_MAP:
            raise ValueError(f'{resource_id} is not available as a service')
        return meta


class GenericServiceResourceFallback(GenericServiceResource):
    """ backend for /api/service/ resources

    Acts as an adapter to a concrete resource, returning only its bare result.
    If the resource (=stored object) has a signature attached, it has already
    been validated by the object's backend or as part of the SignatureMixin
    """
    RESOURCE_MAP = {
        'models/': GenericModelResource,
        'scripts/': GenericScriptResource,
        'jobs/': GenericJobResource,
    }

    def __getattr__(self, item):
        for resource in self.RESOURCE_MAP.values():
            if hasattr(resource, item):
                return self.handle_resource_method(item)
        raise AttributeError(item)

    def handle_resource_method(self, method):
        # returns a wrapper to forward the resource method to the actual resource
        def resource_method_adapter(resource_pk, query, payload):
            # find the actual object, get the actual Resource to handle it
            meta = self.resolve_object(resource_pk)
            Resource = self.RESOURCE_MAP[meta.prefix]
            # this behaves the same way as a call on the actual resource
            # -- except we intercept Resource.prepare_result_from to provide result extraction
            resource = Resource(self.om, is_async=self.is_async)
            self.handle_resource_prepare_result(resource)
            meth = getattr(resource, method)
            return meth(resource_pk, query, payload)

        return resource_method_adapter

    def handle_resource_prepare_result(self, resource):
        # intercepts resource.prepare_result to remove the default api outputs
        def override(actual_prepare_result):
            def prepare_result_adapter(*args, **kwargs):
                result = actual_prepare_result(*args, **kwargs)
                # FIXME all resource outputs provide 'result', except jobs
                data = result.get('job_results') or result.get('result')
                if not isinstance(data, dict):
                    # ensure response is json serializable
                    data = {'data': data}
                return data

            return prepare_result_adapter

        resource.prepare_result = override(resource.prepare_result)

    def prepare_result(self, result, resource_name=None, **kwargs):
        meta = self.resolve_object(resource_name)
        Resource = self.RESOURCE_MAP[meta.prefix]
        resource = Resource(self.om, is_async=self.is_async)
        self.handle_resource_prepare_result(resource)
        return resource.prepare_result(result, **kwargs)
