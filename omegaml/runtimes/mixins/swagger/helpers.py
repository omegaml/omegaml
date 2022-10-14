import warnings

from functools import reduce

from marshmallow import Schema, fields


class Operation:
    """ apispec operation builder

    Usage:

        spec = APISpec(...)
        operations = [
            Operation(spec, "put")
               .add_request(InputSchema)
               .add_respone(200, OutputSchema),
            Operation(spec, "put")
               .add_request(InputSchema)
               .add_respone(201, OutputSchema),s
        ]
        spec.path('/resource', operations=Operation.to_path(operations))
    """

    def __init__(self, spec, method, description=None, operation_id=None):
        self.spec = spec
        self.method = method
        self.responses = {}
        self.request = None
        self.parameters = {}
        self.description = description
        self.operation_id = operation_id

    def add_response(self, status, schema, description=None):
        """ add operation by http status code

        Args:
            status (int|str): http status code, e.g. 200, 400, "2XX", "4XX"
            schema (Schema|type): the response Schema
            description (str): arbitrary description

        Returns:
            self
        """
        resp = {
            "description": description,
        }
        resp.update(schema=schema) if schema else None
        self.responses[str(status)] = resp
        return self

    def add_request(self, schema):
        """ add a request (body) schema

        Args:
            schema (Schema|type): the name of the schema

        Returns:
            self
        """
        self.request = schema
        return self

    def add_parameter(self, location, name, schema=None, description=None, required=False):
        """ add a parameter in path, header, cookie

        Args:
            location (str): path, header, cookie
            name (str): the name
            schema (Schema): the schema name
            description (str): arbitrary description
            required (bool): whether this parameter is required

        Returns:
            self
        """
        self.parameters[name] = {
            "in": location,
            "schema": schema,
            "description": description,
            "required": required,
        }
        return self

    def to_dict(self):
        """ return the json representation according to the spec major version """
        # swagger 2.0
        if self.request:
            self.add_parameter("body", "body", schema=self.request)
        return {
            self.method: {
                "summary": "summary",
                "description": self.description or ('no description'),
                "operationId": f'{self.operation_id}#{self.method}',
                "consumes": ["application/json"],
                "produces": ["application/json"],
                "parameters": [{
                    "in": param["in"],
                    "name": name,
                    "description": param["description"] or ('no description'),
                    "schema": {
                        "$ref": f'#/definitions/{schema_name(param["schema"])}'
                    }
                } for name, param in self.parameters.items()],
                "responses": {
                    status: {
                        "description": resp["description"] or ('no description'),
                        "schema": {
                            "$ref": f'#/definitions/{schema_name(resp["schema"])}'
                        } if not getattr(resp["schema"], 'many', False) else {
                            "type": "array",
                            "items": {
                                "$ref": f'#/definitions/{schema_name(resp["schema"])}'
                            }
                        }
                    } for status, resp in self.responses.items()
                }
            }
        }

    @classmethod
    def to_path(self, operations):
        operations = (op.to_dict() for op in operations)
        return reduce(lambda a, b: a.update(b) or a, operations)


class SpecFromResourceHelperBase:
    path_template = '/api/v1/{resource}/{name}/{action}'
    default_actions = {'': ['post']}
    default_orient = 'columns'

    def __init__(self, meta, name, resource, signature, spec, store):
        self.meta = meta
        self.name = name
        self.resource = resource
        self.signature = signature
        self.spec = spec
        self.store = store

    def add_schema_from_datatype(self, name, datatype):
        # idempotent way to add schema.
        # Args:
        #     schema (Schema): the Schema class
        if name in self.spec.components.schemas:
            return
        self.spec.components.schema(name, {}, schema=datatype)

    def add_schema_from_meta(self, name, meta):
        # idempotent way to add schema.
        # Args:
        #     meta (dict): the Metadata.to_dict() equivalent of a dataset
        if name in self.spec.components.schemas and meta:
            return
        self.spec.components.schema(name, {}, meta=meta)

    def match_data_orient(self, datatype, orient):
        # return the datatype as a Nested(Schema) or List(Nested(Schema))
        # -- orient == 'records' => fields.List(fields.Nested(datatype))
        #           == 'columns' => fields.Nested(datatype)
        # Examples:
        #    records => { data: [ { x: 1, y: 2, ... }, ... ]}
        #    columns => { data: { x: [ 1, 2, ... ] }}
        # See also:
        # - https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.html
        # - https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_json.html
        return fields.List(fields.Nested(datatype)) if orient == 'records' else fields.Nested(datatype)

    def render(self):
        # render endpoint
        orient = self.signature.get('orient') or self.default_orient
        datatypes = self.datatypes(orient)
        InputSchema = datatypes['X']
        DefaultOutputSchema = Schema.from_dict({
            'data': fields.Raw(),
        })
        OutputSchema = datatypes.get('Y') or datatypes.get('result') or DefaultOutputSchema
        self.render_operations(InputSchema, {200: OutputSchema})
        self.add_schema_from_datatype(schema_name(InputSchema), InputSchema)
        self.add_schema_from_datatype(schema_name(OutputSchema), OutputSchema)

    def render_operations(self, input_schema, responses):  # add operations
        # renders paths according to self.path_template and signature.actions
        # if no signature.actions are specified, uses self.default_actions
        # inputs: Schema
        # responses: mapping http status => schema, or Schema => 200: Schema
        name = self.name
        resource = self.resource
        responses = {200: responses} if isinstance(responses, Schema) else dict(responses)
        operations = []
        actions = self.signature.get('actions') or self.default_actions
        for action, http_methods in actions.items():
            for http_method in http_methods:
                operation_id = f'{self.name}#{action}'
                opspec = (Operation(self.spec, http_method, operation_id=operation_id)
                          .add_request(input_schema))
                for status_code, output_schema in responses.items():
                    opspec.add_response(status_code, output_schema)
                operations.append(opspec)
            self.spec.path(self.path_template.format(**locals()),
                           operations=Operation.to_path(operations))

    def datatypes(self, orient):
        # convert signature specs back to Schema types
        signature = self.signature
        store = self.store
        name = self.name.replace('/', '_')
        if signature:
            datatypes = {
                k: store._datatype_from_schema(spec['schema'], name=f'{name}_{k}',
                                               orient=orient,
                                               many=spec.get('many', False))
                for k, spec in signature.items() if k in ('X', 'Y', 'result') and spec
            }
        else:
            datatypes = None
        if not datatypes:
            raise ValueError(f"Missing signature specification for object {store.prefix}/{name}")
        return datatypes


class SpecFromModelHelper(SpecFromResourceHelperBase):
    default_actions = {'predict': ['post']}
    default_orient = 'records'

    def datatypes(self, orient):
        name = self.name.replace('/', '_')
        datatypes_ = super().datatypes(orient)
        datatypes_['X'] = Schema.from_dict({
            'data': self.match_data_orient(datatypes_.get('X', fields.Raw), orient),
            'columns': fields.List(fields.String),
            'shape': fields.List(fields.Integer),
        }, name=f'PredictInput_{name}')
        Result = datatypes_.get('Y') or datatypes_.get('result')
        datatypes_['Y'] = Schema.from_dict({
            'model': fields.String(),
            'result': fields.Nested(Result) if Result else fields.Raw(),
            'resource_uri': fields.String(),
        }, name=f'PredictOutput_{name}')
        return datatypes_


class SpecFromDatasetHelper(SpecFromResourceHelperBase):
    path_template = '/api/v1/dataset/{name}'
    default_actions = {'get': ['get'], 'put': ['put']}

    def datatypes(self, orient):
        name = self.name.replace('/', '_')
        store = self.store
        meta = self.meta
        datasetType = store._datatype_from_metadata(meta.to_dict(), orient=orient)
        DatasetInput = Schema.from_dict({
            'data': self.match_data_orient(datasetType, orient),
            'dtypes': fields.Raw(),
            'append': fields.Boolean(),
        }, name=f'DatasetInput_{name}')
        datatypes_ = {
            'X': DatasetInput,
            'result': DatasetInput,
        }
        return datatypes_


class SpecFromScriptHelper(SpecFromResourceHelperBase):
    path_template = '/api/v1/{resource}/{name}/{action}'
    default_actions = {'run': ['post']}
    default_orient = 'records'

    def datatypes(self, orient):
        datatypes_ = super().datatypes(orient)
        name = self.name.replace('/', '_')
        Result = datatypes_.get('result')
        datatypes_['result'] = Schema.from_dict({
            'resource_uri': fields.String(),
            'script': fields.String(),
            'result': Result if Result else fields.Raw,
            'runtimes': fields.Float,
            'started': fields.DateTime,
            'ended': fields.DateTime,
        }, name=f'ScriptOutput_{name}')
        return datatypes_


class SpecFromServiceHelper(SpecFromResourceHelperBase):
    path_template = '/api/service/{name}'
    default_actions = {'run': ['post'], 'predict': ['post']}
    default_orient = 'records'

    def datatypes(self, orient):
        try:
            datatypes = super().datatypes(orient=orient)
        except ValueError:
            if self.store.prefix == 'data/':
                warnings.warn('datasets are not properly supported as services yet, '
                              'please use the generic /api/v1/dataset resource')
                datasetHelper = SpecFromDatasetHelper(self.meta, self.name, self.resource,
                                                      self.signature, self.spec, self.store)
                datatypes = datasetHelper.datatypes(orient=orient)
            else:
                raise
        return datatypes


schema_name = lambda s: getattr(s, '__name__', s.__class__.__name__)
