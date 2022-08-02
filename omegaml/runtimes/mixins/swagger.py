import apispec
import json
import yaml
from apispec import APISpec
from apispec.ext.marshmallow import MarshmallowPlugin
from functools import reduce
from marshmallow import Schema, fields


class SwaggerGenerator:
    def __init__(self, om):
        self.om = om
        self.spec = self._make_spec()

    def _make_spec(self):
        # Create an APISpec
        spec = APISpec(
            title="Swagger Petstore",
            version="1.0.0",
            openapi_version="2.0",
            plugins=[MarshmallowPlugin()],
        )
        return spec

    def to_json(self, indent=2, stream=None):
        dump = json.dump if stream else json.dumps
        return dump(self.spec.to_dict(), indent=indent)

    def to_yaml(self, stream=None):
        return yaml.dump(self.spec.to_dict(), stream=stream)

    def to_dict(self, **kwargs):
        return self.spec.to_dict()

    def include(self, path):
        for obj in self.om.list(path.replace('datasets/', 'data/')):
            self._include_obj(obj.replace('data/', 'datasets/'))

    def validate(self):
        apispec.utils.validate_spec(self.spec)

    def _include_obj(self, path):
        prefix, name = path.split('/', 1)
        store = getattr(self.om, prefix)
        meta = store.metadata(name)
        resource = prefix[:-1]  # cut the s (models => model, datasets => dataset)
        signature = meta.attributes.get('signature', {})
        spec = self.spec
        RESOURCE_SPEC_HELPERS = {
            'model': SpecFromModelHelper,
            'dataset': SpecFromDatasetHelper,
            'script': SpecFromScriptHelper,
        }
        resource_helper = RESOURCE_SPEC_HELPERS[resource]
        resource_helper(meta, name, resource, signature, spec, store).render()

    @staticmethod
    def build_swagger(self, include='*', format='yaml', file=None):
        gen = SwaggerGenerator(self.omega)
        for path in include.split(','):
            gen.include(path)
        formatter = {
            'yaml': gen.to_yaml,
            'dict': gen.to_dict,
            'json': gen.to_json,
        }
        return formatter.get(format)(stream=file)


class Operation:
    """ apispec operation builder

    Usage:

        spec = APISpec(...)
        operations = [
            Operation(spec, "put)
               .add_request(InputSchema)
               .add_respone(200, OutputSchema),
            Operation(spec, "put)
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
                "description": self.description or ('no description found'),
                "operationId": f'{self.operation_id}#{self.method}',
                "consumes": ["application/json"],
                "produces": ["application/json"],
                "parameters": [{
                    "in": param["in"],
                    "name": name,
                    "description": param["description"] or ('no description found'),
                    "schema": {
                        "$ref": f'#/definitions/{param["schema"].__name__}'
                    }
                } for name, param in self.parameters.items()],
                "responses": {
                    status: {
                        "description": resp["description"] or '(no description found)',
                        "schema": {
                            "$ref": f'#/definitions/{resp["schema"].__name__}'
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
        #    records:  { data: [ { x: 1, y: 2, ... }, ... ]}
        #    columns:  { data: { x: [ 1, 2, ... ] }}
        # See also:
        # - https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.html
        # - https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_json.html
        return fields.List(fields.Nested(datatype)) if orient == 'records' else fields.Nested(datatype)

    def render(self):
        raise NotImplementedError

    def datatypes(self, orient):
        raise NotImplementedError


class SpecFromModelHelper(SpecFromResourceHelperBase):
    def render(self):
        orient = self.signature.get('orient', 'columns')
        datatypes = self.datatypes(orient)
        self.render_predict(datatypes, orient)

    def datatypes(self, orient):
        # convert signature specs back to Schema types
        signature = self.signature
        store = self.store
        name = self.name
        if signature:
            datatypes = {
                k: store._datatype_from_schema(spec['schema'], name=f'{name}_{k}', orient=orient)
                for k, spec in signature.items() if spec
            }
        else:
            datatypes = None
        if not datatypes:
            raise ValueError(f"Missing signature specification for model {name}")
        return datatypes

    def render_predict(self, datatypes, orient):
        # render predict endpoint
        name = self.name
        resource = self.resource
        orient = self.signature.get('orient', 'columns')
        action = 'predict'
        # combine X and Y Schemas into inputs
        PredictInput = Schema.from_dict({
            'data': self.match_data_orient(datatypes.get('X', fields.Raw), orient),
            'columns': fields.List(fields.String),
            'shape': fields.List(fields.Integer),
        }, name=f'PredictInput_{name}')
        # use result Schema as output
        Result = datatypes.get('result')
        PredictOutput = Schema.from_dict({
            'model': fields.String(),
            'result': fields.Nested(Result) if Result else fields.Raw(),
            'resource_uri': fields.String(),
        }, name=f'PredictOutput_{name}')
        # add operations
        operations = [
            Operation(self.spec, 'get', operation_id=self.name)
                .add_request(PredictInput)
                .add_response(200, PredictOutput),
            Operation(self.spec, 'put', operation_id=self.name)
                .add_request(PredictInput)
                .add_response(200, PredictOutput),
        ]
        self.add_schema_from_datatype(PredictInput.__name__, PredictInput)
        self.add_schema_from_datatype(PredictOutput.__name__, PredictOutput)
        self.spec.path(f'/api/v1/{resource}/{name}/{action}', operations=Operation.to_path(operations))


class SpecFromDatasetHelper(SpecFromResourceHelperBase):
    def render(self):
        name = self.name
        resource = self.resource
        orient = self.signature.get('orient', 'columns')
        # build input schema
        datatypes = self.datatypes(orient)
        DatasetInput = Schema.from_dict({
            'data': self.match_data_orient(datatypes.get('dataset', fields.Raw), orient),
            'dtypes': fields.Raw(),
            'append': fields.Boolean(),
        }, name=f'DatasetInput_{name}')
        # add operations
        operations = [
            Operation(self.spec, 'get', operation_id=self.name)
                .add_request(DatasetInput)
                .add_response(200, DatasetInput),
            Operation(self.spec, 'put', operation_id=self.name)
                .add_request(DatasetInput)
                .add_response(200, DatasetInput),
        ]
        self.add_schema_from_datatype(DatasetInput.__name__, DatasetInput)
        self.spec.path(f'/api/v1/{resource}/{name}/', operations=Operation.to_path(operations))

    def datatypes(self, orient):
        store = self.store
        meta = self.meta
        datasetType = store._datatype_from_metadata(meta.to_dict(), orient=orient)
        return {'dataset': datasetType}


class SpecFromScriptHelper(SpecFromResourceHelperBase):
    def render(self):
        # render predict endpoint
        name = self.name
        resource = self.resource
        action = 'run'
        # combine X and Y Schemas into inputs
        datatypes = self.datatypes('custom')
        ScriptInput = datatypes['X']
        # use result Schema as output
        ScriptOutput = datatypes.get('result')
        # add operations
        operations = [
            Operation(self.spec, 'get', operation_id=self.name)
                .add_request(ScriptInput)
                .add_response(200, ScriptOutput),
            Operation(self.spec, 'put', operation_id=self.name)
                .add_request(ScriptInput)
                .add_response(200, ScriptOutput),
        ]
        self.add_schema_from_datatype(ScriptInput.__name__, ScriptInput)
        self.add_schema_from_datatype(ScriptOutput.__name__, ScriptOutput)
        self.spec.path(f'/api/v1/{resource}/{name}/{action}', operations=Operation.to_path(operations))

    def datatypes(self, orient):
        # convert signature specs back to Schema types
        signature = self.signature
        store = self.store
        name = self.name
        if signature:
            datatypes = {
                k: store._datatype_from_schema(spec['schema'], name=f'{name}_{k}', orient=orient)
                for k, spec in signature.items() if spec
            }
        else:
            datatypes = None
        if not datatypes:
            raise ValueError(f"Missing signature specification for {store.prefix}{name}")
        return datatypes
