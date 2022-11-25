import os
from uuid import uuid4

#: maximum size in bytes where PassthroughDataset is used on om.runtime.model() calls
#: refers to object size determined by os.getsizeof(). Set to "0" to disable.
_max_size = os.environ.get('OMEGA_PASSTHROUGH_MAX_SIZE', 1024 * 1024 * 10)


class PassthroughMixin:
    """ Resolve a PasstroughDataset to its actual value

    Behaves as a normal dataset, however retrieves the value from the in-memory
    representation, i.e. PasshroughDataset.data. This should only be used
    by om.runtime to pass along relatively small client data in an efficient
    manner.

    Rationale:

        This enables the runtime to pass a PassthroughDataset as part of the
        message, as it would a dataset's name. It does so while preserving the
        name semantics due to the PassthroughDataset posing as type(str)

    Usage:

        private
    """

    def get(self, name, **kwargs):
        if isinstance(name, PassthroughDataset):
            return name.data
        return super().get(name, **kwargs)

    def metadata(self, name, **kwargs):
        if isinstance(name, PassthroughDataset):
            kind_meta = {'data': repr(name)}
            return self.make_metadata(name=str(name), kind='passthrough', kind_meta=kind_meta)
        return super().metadata(name, **kwargs)


class PassthroughDataset(str):
    """ A dataset that exists in-memory when passed through om.runtime.model()

    Rationale:

        With small datasets typically used for model prediction the overhead of
        writing to om.datasets can be too high. In this case we pass the dataset
        as a native Python object along with other parameters for the om.runtime
        task. This way the object is serialized to the message payload and is not
        stored in the database.

    How this works:

        The PasshtroughDataset represents as the './system/passthrough/<uuid>'
        dataset (type str), carrying the payload as the ._passthrough attribute.
        The attribute is directly accessible as the .data property.

    Dependencies:

        - ModelMixin._ensure_data_is_stored passes a PassthroughDataset if
          the data provided is of a native container type (dict, list, duple)
        - SimpleTracker._common_log_data resolves the actual value of any
          positional argument passed as a PassthroughDataset
    """
    # cut off to passthrough
    # -- checked by ModelMixin.__ensure_data_is_stored
    # -- rabbitmq max size with reasonable performance is considered 128MB
    # -- in practice message sizes above 10MB carry too large an overhead
    MAX_SIZE = int(_max_size)

    def __new__(cls, content):
        return super().__new__(cls, f'./system/passthrough/{uuid4().hex}')

    def __init__(self, data):
        # simulate OmegaStore.put_pyobj_as_document
        # -- dicts are stored as documents, resulting in a list of documents
        # -- list of lists are stored as lists of single documents
        # -- any other object is also stored as a document, like dicts
        if isinstance(data, dict):
            self._passthrough_data = [data]
        elif isinstance(data, (list, tuple)) and isinstance(data[0], (list, tuple)):
            self._passthrough_data = data
        else:
            self._passthrough_data = [data]

    @property
    def data(self):
        return self._passthrough_data

    def __repr__(self):
        return f'PassthroughDataset({self.data})'
