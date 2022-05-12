import json

import datetime

from dataset_orm import types, Model, Column


class Metadata(Model):
    # fields
    #: this is the name of the data
    name = Column(types.string(length=255))
    #: bucket
    bucket = Column(types.string(length=255))
    #: prefix
    prefix = Column(types.string(length=255))
    #: kind of data
    kind = Column(types.string(length=255))
    #: for PANDAS_HDF and SKLEARN_JOBLIB this is the gridfile
    gridfile = Column(types.file)
    #: for PANDAS_DFROWS this is the collection
    collection = Column(types.string(length=255))
    #: for PYTHON_DATA this is the actual document
    objid = Column(types.string(length=255))
    #: omegaml technical attributes, e.g. column indicies
    kind_meta = Column(types.json, default={})
    #: customer-defined other meta attributes
    attributes = Column(types.json, default={})
    #: s3file attributes
    s3file = Column(types.json)
    #: location URI
    uri = Column(types.string(length=255))
    #: created datetime
    created = Column(types.datetime, default=datetime.datetime.now)
    #: created datetime
    modified = Column(types.datetime, default=datetime.datetime.now,
                      on_update=datetime.datetime.now)

    def __getitem__(self, k):
        return getattr(self, k)

    def __eq__(self, other):
        return self.name == other.name and self.bucket == self.bucket

    def __repr__(self):
        return (f"Metadata(name={self.name},bucket={self.bucket},prefix={self.prefix},"
                f"created={self.created},kind={self.kind})")


