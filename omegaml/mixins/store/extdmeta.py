import warnings

from apispec import APISpec
from apispec.ext.marshmallow import MarshmallowPlugin
from marshmallow import fields, Schema


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

    # terms use in this class
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

    def link_datatype(self, name, X=None, Y=None, result=None, meta=None, **kwargs):
        """

        Args:
            name (str): the name of the model, script
            X (Schema|type): the schema for the X data (dataX)
            Y (Schema|type): the schema for the Y data (dataY)
            datatype: the actual data type

        Returns:

        """
        meta = meta or self.metadata(name, **kwargs)
        meta.attributes.setdefault('signature', {})
        meta.attributes['signature'] = {
            'X': {
                'datatype': f'{X.__module__}.{X.__name__}',
                'schema': self._schema_from_datatype(X)
            } if X is not None else None,
            'Y': {
                'datatype': f'{Y.__module__}.{Y.__name__}',
                'schema': self._schema_from_datatype(Y)
            } if Y is not None else None,
            'result': {
                'datatype': f'{result.__module__}.{result.__name__}',
                'schema': self._schema_from_datatype(result)
            } if result is not None else None,
        }
        return meta.save()

    def validate(self, name, X=None, Y=None, result=None, **kwargs):
        meta = self.metadata(name, **kwargs)

        def _do_validate(meta, k, v):
            signature = meta.attributes['signature']
            XSchema = self._datatype_from_schema(signature[k]['schema'], name=f'{name}_{k}')
            XSchema().load(v)

        nop = lambda: ()
        _do_validate(meta, 'X', X) if X is not None else nop()
        _do_validate(meta, 'Y', Y) if Y is not None else nop()
        _do_validate(meta, 'result', result) if result is not None else nop()
        return True

    def _datatype_from_schema(self, schema, name=None, orient='records'):
        # orient 'records' => every instance of the Schema reflects one item (default)
        #                     where each field is a distinct value of its type
        #        'columns' => every instance of the Schema reflects a full dataset, where
        #                     where each field is a list of values of its type
        # map OpenAPI 3.x to marshmallow.fields
        # -- nested types are not supported (except arrays)
        # https://swagger.io/specification/
        # https://marshmallow.readthedocs.io/en/stable/marshmallow.fields.html
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
        prop = schema['properties']
        sdict = {}
        for prop, pspec in prop.items():
            ptype = pspec.get('type', 'object')
            pformat = pspec.get('format', '')
            fptype = '.'.join((ptype, pformat))
            ftype = TYPE_MAP.get(fptype) or TYPE_MAP.get(ptype) or TYPE_MAP.get('default')
            if ptype == 'array':
                ptype = TYPE_MAP.get(pspec['items'].get('type'))
                ftype = ftype(ptype) if ptype else ftype(fields.Dict())
            else:
                ftype = ftype()
            if orient == 'columns':
                ftype = fields.List(ftype)
            sdict[prop] = ftype
        return Schema.from_dict(sdict, name=name)

    def _datatype_from_metadata(self, meta, orient='records'):
        TYPE_MAP = {
            "object": fields.String,
            "int64": fields.Integer,
            "float": fields.Float,
            "dict": fields.Raw,
            "bool": fields.Boolean,
            "datetime": fields.DateTime,
            "date": fields.Date,
            "defaults": fields.String,
        }
        kind_meta = meta['kind_meta']
        dtypes = kind_meta['dtypes']
        sdict = {}
        for col, colType in dtypes.items():
            if '#' in col:
                continue
            ftype = TYPE_MAP.get(colType) or TYPE_MAP.get('default')
            sdict[col] = ftype() if orient == 'records' else fields.List(ftype)
        return Schema.from_dict(sdict, name=meta.get('name'))

    def _schema_from_datatype(self, datatype):
        spec = APISpec(
            title="Swagger Petstore",
            version="1.0.0",
            openapi_version="3.0",
            plugins=[MarshmallowPlugin()],
        )
        name = datatype.__name__
        spec.components.schema(name, schema=datatype)
        return spec.to_dict()['components']['schemas'][name]


class ScriptSignatureMixin(SignatureMixin):
    @classmethod
    def supports(cls, store, **kwargs):
        return store.prefix in ('scripts/')

    def _pre_run(self, scriptname, *args, om=None, **kwargs):
        meta = self.metadata(scriptname)
        if 'signature' in meta.attributes:
            vkwargs = {
                'X': args[0] if len(args) > 0 else kwargs.get('X'),
                'Y': args[1] if len(args) > 1 else kwargs.get('Y')
            }
            self.validate(scriptname, **vkwargs)
        return (scriptname, *args), kwargs

    def _post_run(self, result, scriptname, *args, om=None, **kwargs):
        meta = self.metadata(scriptname)
        if 'signature' in meta.attributes:
            self.validate(scriptname, result=result)
        return result


class ModelSignatureMixin(SignatureMixin):
    @classmethod
    def supports(cls, store, **kwargs):
        return store.prefix in ('models/')

    def link_dataset(self, name, Xname=None, Yname=None, Xmeta=None, Ymeta=None,
                     rName=None, features=None, labels=None, data_store=None,
                     meta=None, signature=True, **kwargs):
        """ link dataset information to this model

        This sets the 'dataset' entry in metadata.attributes of a model. By default
        this method is called by any .fit() call initiated from the runtime. The 'dataset'
        entry is a dict that records the following information::

            {
                'Xname': Xname,  # the X dataset
                'Yname': Yname,  # the Y dataset
                'features': features, # features for this model
                'labels': labels, # labels for this model
                'metaX': metaX, # Metadata for this model (at time of fit)
                'metaY': metaY, # Metadata for this model (at time of fit)
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
            signature (bool): if True the object's signature will also be updated
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
            self.link_datatype(name, X=self._datatype_from_metadata(metaX), meta=meta) if metaX else None
            self.link_datatype(name, Y=self._datatype_from_metadata(metaY), meta=meta) if metaY else None
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

    def _pre_decision_function(self, modelname, Xname, **kwargs):
        return self._resolve_dataset_defaults(modelname, Xname, **kwargs)

    def _pre_predict_proba(self, modelname, Xname, **kwargs):
        return self._resolve_dataset_defaults(modelname, Xname, **kwargs)

    def _pre_score(self, modelname, Xname, **kwargs):
        return self._resolve_dataset_defaults(modelname, Xname, **kwargs)

    def _pre_transform(self, modelname, Xname, **kwargs):
        return self._resolve_dataset_defaults(modelname, Xname, **kwargs)

    def pre_fit_transform(self, modelname, Xname, **kwargs):
        return self._resolve_dataset_defaults(modelname, Xname, **kwargs)

    def link_dependencies(self, name, select=None, **kwargs):
        meta = self.metadata(name, **kwargs)
        return meta.save()
