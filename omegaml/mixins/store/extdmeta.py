import string
import warnings
from apispec import APISpec
from apispec.ext.marshmallow import MarshmallowPlugin
from marshmallow import fields, Schema

from omegaml.util import markup


class SignatureMixin:
    """ Associate a models corresponding dataset

    This provides methods to record additional metadata on models.
    On runtime-called calls, this additional metadata is used to
    provide defaults for Xname, Yname, rName respectively.

    Usage::

        # recording information
        om.models.link_dataset('modelname', Xname=..., Yname=...)
        om.models.link_docs('modelname', doc_or_ref)

        # using default dataset names, using the metadata.attributes['dataset'] entry
        om.runtime.model('mymodel').fit('*', '*')
        om.runtime.model('mymodel').predict('*')

    Notes:
        - Provides pre/post processing for model actions. Currently fit(), predict()
        - Pre/post processing is triggered when called as
          ModelBackend.perform('method', *args, **kwargs)
    """

    # terms used in this class
    # -- "datatype" => marshmallow Schema class/instance
    # -- "schema" => "schemas" component

    def link_docs(self, name, doc_or_ref, **kwargs):
        """ set or link documentation returned by om.models.help()

        Args:
            name: the model name
            doc_or_ref: the docstring or the URL to a web page
            **kwargs:

        Returns:

        """
        meta = self.metadata(name, **kwargs)
        meta.attributes['docs'] = doc_or_ref
        return meta.save()

    def link_datatype(self, name, X=None, Y=None, result=None, orient=None,
                      meta=None, actions=None, errors=None,
                      **kwargs):
        """ link a Schema to a model or script

        Args:
            name (str): the name of the model, script
            X (Schema|list): the schema for the X data (dataX), applies to models, scripts. Pass [Schema] to
               indicate many objects of type Schema.
            Y (Schema|list): the schema for the Y data (dataY), applies to models only. Pass [Schema] to
               indicate many objects of type Schema.
            result (Schema): the schema for the successful result, applies to scripts only. Pass [Schema] to
               indicate many objects of type Schema.
            errors (list|dict): list of tuples or dict of Schema|Exception => http status code to indicate errors
            orient (str): the datatype orientation, defaults to 'columns' for models, 'records' for datasets and scripts
            actions (list|dict): the list of valid actions ['predict', ...],
               or a list of tuples to map actions to http methods [('predict', ['post', ...]), ...]. If
               the http method is not specified, it is assumed as 'post'

        Returns:
            Metadata
        """
        meta = meta or self.metadata(name, **kwargs)
        if actions:
            if isinstance(actions, (list, tuple)) and isinstance(actions[0], str):
                # list of strings
                actions = {action: ['post'] for action in actions}
            else:
                # list of tuples [(http_method, [action, ...])] or dict
                actions = dict(actions)
        else:
            actions = None
        existing = meta.attributes.setdefault('signature', {})
        # determine object or array
        is_many = lambda T: isinstance(T, list) or getattr(T, 'many', False)
        many_type = lambda T: T[0] if isinstance(T, list) else X
        Xmany, X = (True, many_type(X)) if is_many(X) else (False, X)
        Ymany, Y = (True, many_type(Y)) if is_many(Y) else (False, Y)
        Rmany, result = (True, many_type(result)) if is_many(result) else (False, result)
        iter_errors = (errors.items() if isinstance(errors, dict)
                       else ((E, status) for E, status in errors) if isinstance(errors, (list, tuple)) else [])
        errors = {
            (True, many_type(E)) if is_many(E) else (False, E): status
            for E, status in iter_errors}
        # build signature specification
        is_schema = lambda T: isinstance(T, Schema) or issubclass(T, Schema)
        ExceptionSchema = Schema.from_dict({'message': fields.String()}, name=f'{name}Exception')
        meta.attributes['signature'] = {
            'X': {
                'datatype': f'{X.__module__}.{schema_name(X)}',
                'schema': self._schema_from_datatype(X),
                'many': Xmany,
            } if X is not None else existing.get('X'),
            'Y': {
                'datatype': f'{Y.__module__}.{schema_name(Y)}',
                'schema': self._schema_from_datatype(Y),
                'many': Ymany,
            } if Y is not None else existing.get('Y'),
            'result': {
                'datatype': f'{result.__module__}.{schema_name(result)}',
                'schema': self._schema_from_datatype(result),
                'many': Rmany,
            } if result is not None else existing.get('result'),
            'errors': {
                str(status): {
                    'datatype': f'{E.__module__}.{schema_name(E)}',
                    'schema': self._schema_from_datatype(E if is_schema(E) else ExceptionSchema),
                    'many': many,
                    'exception': isinstance(E, Exception) or isinstance(E(), Exception),
                } for (many, E), status in errors.items()
            } if errors is not None else existing.get('errors'),
            'actions': actions,
            'orient': orient,
        }
        return meta.save()

    def link_swagger(self, specs, operations=None):
        """ link swagger specs to operations

        Args:
            specs (dict|filename): the swagger specifications
            operations (list|dict): the operations to support (names of services, models),
                if dict, a mapping of { '/api/path': 'name#action#method' }, where name is
                the name of a service or model, action is the method to call (e.g. predict),
                and method is the http method (e.g. post)

        Returns:
            list of mapped Metadata
        """
        specs = specs if isinstance(specs, dict) else markup(specs)
        assert specs.get('swagger') == '2.0', f"Only swagger version 2.0 is currently supported."
        paths = specs['paths']
        definitions = specs['definitions']
        actions = []
        operations = operations or self.list()
        metas = []

        def pathspecs():
            for path, pathspec in paths.items():
                for method, opspec in pathspec.items():
                    yield path, method, opspec

        for path, method, opspec in pathspecs():
            # operation mapping
            # -- format: name#action#method[,method]
            # -- name is the model or service name
            # -- action is the method to call (e.g. predict)
            # -- method(s) is the name of the http method
            opId = opspec.get('operationId')
            if opId is None:
                # extract from given operations spec
                if isinstance(operations, dict):
                    opId = operations.get(path)
                else:
                    # fallback to default operation
                    pathName = path.split('/')[-1]
                    opId = f'{pathName}#predict#post'
            name, action, methods = opId.split('#')
            if not self.exists(name):
                print(f"{name} not found in {self.prefix}, ignored.")
                continue
            methods = methods.split(',')
            actions.append((action, methods))
            # parameters
            params = opspec['parameters']
            for prmspec in params:
                if prmspec.get('in') != 'body':
                    continue
                # resolve schema spec
                # -- either direct spec of schema
                # -- or $ref: #/definitions/<name>, where name is the key into definitions
                schemaSpec = prmspec.get('schema')
                Xis_many = schemaSpec.get('type', 'object') == 'array'
                schemaRef = schemaSpec.get('$ref') if not Xis_many else schemaSpec['items'].get('$ref')
                Xschema = schemaSpec if schemaRef is None else definitions.get(schemaRef.split('/')[-1])
                break
            else:
                print("No body found, cannot generate X datatype")
                Xschema = None
                Xis_many = None
            resps = opspec['responses']
            errors = []
            Yschema = None
            for code, respspec in resps.items():
                if code == '200':
                    schemaSpec = respspec.get('schema')
                    Yis_many = schemaSpec.get('type', 'object') == 'array'
                    schemaRef = schemaSpec.get('$ref') if not Yis_many else schemaSpec['items'].get('$ref')
                    Yschema = schemaSpec if schemaRef is None else definitions.get(schemaRef.split('/')[-1])
                else:
                    schemaSpec = respspec.get('schema')
                    Eis_many = schemaSpec.get('type', 'object') == 'array'
                    schemaRef = schemaSpec.get('$ref') if not Eis_many else schemaSpec['items'].get('$ref')
                    Eschema = schemaSpec if schemaRef is None else definitions.get(schemaRef.split('/')[-1])
                    Edtype = self._datatype_from_schema(Eschema, name=f'{name}_{code}', many=Eis_many)
                    errors.append(([type(Edtype)] if Eis_many else Edtype, code))
            if Yschema is None:
                print("No response 200 found, cannot generate Y datatype")
                Yschema = None
                Yis_many = None
            # finally link
            Xdtype = self._datatype_from_schema(Xschema, name=f'{name}Input_{action}', many=Xis_many)
            Ydtype = self._datatype_from_schema(Yschema, name=f'{name}Output_{action}', many=Yis_many)
            meta = self.link_datatype(name, X=Xdtype, Y=Ydtype, actions=actions, errors=errors)
            metas.append(meta)
        return metas

    def validate(self, name, X=None, Y=None, result=None, error=None, **kwargs):
        meta = self.metadata(name, **kwargs)
        signature = meta.attributes.get('signature')

        def _do_validate(k, v):
            vv = v.get('data') if isinstance(v, dict) else None
            v = vv if isinstance(vv, Exception) else v
            status_code = None
            if isinstance(v, Exception) or k == 'error':
                status_code = v.args[-1] if len(v.args) > 0 else 400
                schema = (signature.get('errors') or {}).get(str(status_code), {}).get('schema')
                many = (signature.get('errors') or {}).get(str(status_code), {}).get('many', False)
                v = v.args[0] if len(v.args) > 0 else v  # parse exception value instead of instance
                v = dict(message=v) if not isinstance(v, (list, dict)) else v
            else:
                schema = (signature.get(k) or {}).get('schema')
                many = (signature.get(k) or {}).get('many', False)
            if schema:
                Schema = self._datatype_from_schema(schema, name=f'{name}_{k}')
                Schema(many=many).load(v)

        if signature:
            nop = lambda: ()
            # if we have an exception, process as error
            if isinstance(result, Exception):
                error, result = result, None
            # validate all inputs provided
            _do_validate('X', X) if X is not None else nop()
            _do_validate('Y', Y) if Y is not None else nop()
            _do_validate('result', result) if result is not None else nop()
            _do_validate('error', error) if error is not None else nop()
        return True

    def _datatype_from_schema(self, schema, name=None, orient='records', many=False):
        # from an apispec schema, create a marshmallow Schema
        #
        # orient 'records' => every instance of the Schema reflects one item (default)
        #                     where each field is a distinct value of its type
        #        'columns' => every instance of the Schema reflects a full dataset, where
        #                     where each field is a list of values of its type
        # many   if True, the Schema has Schema.many = True
        # map OpenAPI 3.x to marshmallow.fields
        # -- nested types are not supported (except arrays)
        # https://swagger.io/specification/
        # https://marshmallow.readthedocs.io/en/stable/marshmallow.fields.html
        # convert apispec schema to marshmallow Schema
        # -- type conversions from apispec to marshmallow
        TYPE_MAP = {
            'integer': fields.Integer,
            'number': fields.Float,
            'string': fields.String,
            'string.byte': fields.String,
            'string.date-time': fields.DateTime,
            'string.date': fields.Date,
            'array': fields.List,
            'boolean': fields.Boolean,
            'password': fields.String,
            'default': fields.String,
            'object': fields.Raw,
        }
        # -- properties conversion from apispec to marhsmallow
        PROPS_MAP = {
            'nullable': 'allow_none',
        }
        # -- determine Schema type, Fields and respective properties
        prop = schema['properties']
        sdict = {}
        for prop, pspec in prop.items():
            # -- ptype is the apispec type of the property (e.g. integer, string, array)
            ptype = pspec.get('type', 'object')
            # -- fptype is the formatted type (fully qualified) of the property (e.g. string.byte, string.date-time)
            pformat = pspec.get('format', '')
            fptype = '.'.join((ptype, pformat))
            # -- ftype is the marshmallow type of the property (e.g. fields.Integer, fields.String, fields.List)
            ftype = TYPE_MAP.get(fptype) or TYPE_MAP.get(ptype) or TYPE_MAP.get('default')
            # -- props are the properties of the field (e.g. nullable, allow_none)
            #    in case of arrays, a nested type is determined (TODO: support nested schemas)
            props = {PROPS_MAP.get(p): v for p, v in pspec.items() if p in PROPS_MAP}
            if ptype == 'array':
                ptype = TYPE_MAP.get(pspec['items'].get('type'))
                ftype = ftype(ptype) if ptype else ftype(fields.Dict())
            else:
                ftype = ftype(**props)
            if orient == 'columns':
                ftype = fields.List(ftype)
            sdict[prop] = ftype
        # -- finally, create the schema
        schema = Schema.from_dict(sdict, name=name)
        schema.error_messages = {
            'type': f'invalid input for schema {name}'
        }
        return schema if not many else schema(many=True)

    def _datatype_from_metadata(self, meta, orient='records'):
        # https://pbpython.com/pandas_dtypes.html
        TYPE_MAP = {
            "object": fields.String,
            "int": fields.Integer,
            "float": fields.Float,
            "dict": fields.Raw,
            "bool": fields.Boolean,
            "datetime": fields.DateTime,
            "timedelta[ns]": fields.DateTime,
            "date": fields.Date,
            "default": fields.String,
        }
        kind_meta = meta['kind_meta']
        dtypes = kind_meta.get('dtypes', {})
        name = meta.get('name')
        sdict = {}
        infer = lambda v: v.rstrip(string.digits)
        for col, colType in dtypes.items():
            if '#' in col:
                continue
            # orient == 'records' means every item is one value
            #        == 'columns' means every item is a list of values
            ftype = TYPE_MAP.get(infer(colType)) or TYPE_MAP.get('default')
            sdict[col] = ftype() if orient == 'records' else fields.List(ftype)
        schema = Schema.from_dict(sdict, name=name)
        schema.error_messages = {
            'type': f'invalid input for schema {name}'
        }
        return schema

    def _schema_from_datatype(self, datatype):
        spec = APISpec(
            title="omega-ml service",
            version="1.0.0",
            openapi_version="3.0",
            plugins=[MarshmallowPlugin()],
        )
        name = schema_name(datatype)
        spec.components.schema(name, schema=datatype)
        return spec.to_dict()['components']['schemas'][name]


class ScriptSignatureMixin(SignatureMixin):
    @classmethod
    def supports(cls, store, **kwargs):
        return store.prefix in ('scripts/')

    def _pre_run(self, scriptname, *args, **kwargs):
        validate_kwargs = {
            'X': args[0] if len(args) > 0 else kwargs.get('X'),
            'Y': args[1] if len(args) > 1 else kwargs.get('Y')
        }
        self.validate(scriptname, **validate_kwargs)
        return (scriptname, *args), kwargs

    def _post_run(self, result, scriptname, *args, om=None, **kwargs):
        meta = self.metadata(scriptname)
        self.validate(scriptname, result=result)
        return result


class ModelSignatureMixin(SignatureMixin):
    @classmethod
    def supports(cls, store, **kwargs):
        return store.prefix in ('models/')

    def link_dataset(self, name, Xname=None, Yname=None, Xmeta=None, Ymeta=None,
                     rName=None, features=None, labels=None, data_store=None,
                     meta=None, signature=True, actions=None, **kwargs):
        """ link dataset information to this model

        This sets the 'dataset' entry in metadata.attributes of a model. By default
        this method is called by any .fit() call initiated from the runtime. The 'dataset'
        entry is a dict that records the following information::

            {
                'Xname': Xname,  # the X dataset
                'Yname': Yname,  # the Y dataset
                'features': features, # features for this model
                'labels': labels, # labels for this model
                'Xmeta': Xmeta, # Metadata for this model (at time of fit)
                'Ymeta': Ymeta, # Metadata for this model (at time of fit)
                'rName': rName, # the result dataset
                'kwargs': kwargs, # other kwargs used for fitting
            }

        Args:
            name (str): the name of the model or script
            Xname (str): the name of dataset, may include modifiers
            Yname (str): the name of dataset, may include modifiers
            rName (str): the result dataset
            Xmeta (Metadata): the Metadata for X (features), defaults to data_store.metadata(Xname)
            Ymeta (Metadata): the Metadata for Y (features), defaults to data_store.metadata(Yname)
            features (list|dict): a list of feature names or dict(name=info), where info is a
               dict with further information for each features
            labels (list|dict): a list of label names or dict(label=info), where info is a
               dict with futher information for each label
            signature (bool): if True the object's signature will also be updated, defaults to True
            meta (Metadata): the metadata object, if provided .metadata() is not called again
            data_store (OmegaStore): the data store to retrieve Xmeta, Ymeta if not provided
            **kwargs: passed to self.metadata(name, **kwargs) to retrieve the model metadata
        """
        meta = meta or self.metadata(name, **kwargs)
        if data_store is None and (Xname or Yname):
            warnings.warn('Specify data_store=om.store to store metadata')
        metaX = (Xmeta or data_store.metadata(Xname)).to_mongo() if Xname and data_store else None
        metaY = (Ymeta or data_store.metadata(Yname)).to_mongo() if Yname and data_store else None
        model_attrs = {
            'Xname': Xname,
            'Yname': Yname,
            'features': features,
            'labels': labels,
            'Xmeta': metaX,
            'Ymeta': metaY,
            'rName': rName,
            'kwargs': kwargs,
        }
        meta.attributes.setdefault('dataset', {})
        meta.attributes['dataset'].update(model_attrs)
        if signature:
            self.link_datatype(name, X=self._datatype_from_metadata(metaX),
                               meta=meta, actions=actions) if metaX else None
            self.link_datatype(name, Y=self._datatype_from_metadata(metaY),
                               meta=meta, actions=actions) if metaY else None
        return meta.save()

    def link_dependencies(self, name, select=None, **kwargs):
        # TODO determine exact use and implementation
        meta = self.metadata(name, **kwargs)
        return meta.save()

    def _resolve_dataset_defaults(self, modelname, Xname, **kwargs):
        # use the linked dataset name if Xname == '*'
        kwargs = dict(kwargs)
        is_default = lambda name: name in ('*', None)

        def apply_default(key, kwargs):
            if key in kwargs and is_default(kwargs[key]):
                kwargs[key] = dataset_meta.get(key)

        meta = self.metadata(modelname)
        dataset_meta = meta.attributes.get('dataset', {})
        Xname = dataset_meta.get('Xname') if is_default(Xname) else Xname
        [apply_default(key, kwargs) for key in ('Yname', 'rName')]
        return (modelname, Xname), kwargs

    def _post_fit_link_dataset_(self, result, modelname, Xname, meta=None, data_store=None, **kwargs):
        meta = meta or self.metadata(modelname, **kwargs)
        self.link_dataset(modelname, Xname=Xname, meta=meta, data_store=data_store, **kwargs)
        return result

    def _pre_fit(self, modelname, Xname, **kwargs):
        # get default Xname, Yname if provided as '*'
        return self._resolve_dataset_defaults(modelname, Xname, **kwargs)

    def _pre_partial_fit(self, modelname, Xname, **kwargs):
        # get default Xname, Yname if provided as '*'
        return self._resolve_dataset_defaults(modelname, Xname, **kwargs)

    def _post_fit(self, result, modelname, Xname, **kwargs):
        # link the input dataset names with
        return self._post_fit_link_dataset_(result, modelname, Xname, **kwargs)

    def _post_partial_fit(self, result, modelname, Xname, **kwargs):
        return self._post_fit_link_dataset_(result, modelname, Xname, **kwargs)

    def _pre_predict(self, modelname, Xname, **kwargs):
        return self._resolve_dataset_defaults(modelname, Xname, **kwargs)

    def _post_predict(self, result, modelname, Xname, **kwargs):
        self.validate(modelname, result=result)
        return result

    def _pre_decision_function(self, modelname, Xname, **kwargs):
        return self._resolve_dataset_defaults(modelname, Xname, **kwargs)

    def _pre_predict_proba(self, modelname, Xname, **kwargs):
        return self._resolve_dataset_defaults(modelname, Xname, **kwargs)

    def _pre_score(self, modelname, Xname, **kwargs):
        return self._resolve_dataset_defaults(modelname, Xname, **kwargs)

    def _pre_transform(self, modelname, Xname, **kwargs):
        return self._resolve_dataset_defaults(modelname, Xname, **kwargs)

    def _pre_fit_transform(self, modelname, Xname, **kwargs):
        return self._resolve_dataset_defaults(modelname, Xname, **kwargs)


schema_name = lambda s: getattr(s, '__name__', s.__class__.__name__)
