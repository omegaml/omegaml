from __future__ import absolute_import

import datetime
from mongoengine.base.fields import ObjectIdField
from mongoengine.document import Document
from mongoengine.fields import (
    StringField, FileField, DictField, DateTimeField
)

from omegaml.util import settings


# default kinds of objects
class MDREGISTRY:
    PANDAS_DFROWS = 'pandas.dfrows'  # dataframe
    PANDAS_SEROWS = 'pandas.serows'  # series
    PANDAS_HDF = 'pandas.hdf'
    PYTHON_DATA = 'python.data'
    PANDAS_DFGROUP = 'pandas.dfgroup'
    SKLEARN_JOBLIB = 'sklearn.joblib'
    OMEGAML_JOBS = 'script.ipynb'
    SPARK_MLLIB = 'spark.mllib'
    OMEGAML_RUNNING_JOBS = 'job.run'
    MINIBATCH_STREAM = 'stream.minibatch'

    #: the list of accepted data types. extend using OmegaStore.register_backend
    KINDS = [
        PANDAS_DFROWS, PANDAS_SEROWS, PANDAS_HDF, PYTHON_DATA, SKLEARN_JOBLIB,
        PANDAS_DFGROUP, OMEGAML_JOBS, OMEGAML_RUNNING_JOBS, SPARK_MLLIB, MINIBATCH_STREAM,
    ]


class Metadata:
    """
    Metadata stores information about objects in OmegaStore
    """

    # NOTE THIS IS ONLY HERE FOR DOCUMENTATION PURPOSE.
    #
    # If you use this class to save a document, it will raise a NameError
    #
    # The actual Metadata class is created in make_Metadata() below.
    # Rationale: If we let mongoengine create Metadata here the class
    # is bound to a specific MongoClient instance. Using make_Metadata
    # binds the class to the specific instance that exists at the time
    # of creation. Open to better ways.

    # fields
    #: this is the name of the data
    name = StringField(unique_with=['bucket', 'prefix'])
    #: bucket
    bucket = StringField()
    #: prefix
    prefix = StringField()
    #: kind of data
    kind = StringField(choices=MDREGISTRY.KINDS)
    #: for PANDAS_HDF and SKLEARN_JOBLIB this is the gridfile
    gridfile = FileField()
    #: for PANDAS_DFROWS this is the collection
    collection = StringField()
    #: for PYTHON_DATA this is the actual document
    objid = ObjectIdField()
    #: omegaml technical attributes, e.g. column indicies
    kind_meta = DictField()
    #: customer-defined other meta attributes
    attributes = DictField()
    #: s3file attributes
    s3file = DictField()
    #: location URI
    uri = StringField()
    #: created datetime
    created = DateTimeField(default=datetime.datetime.now)
    #: created datetime
    modified = DateTimeField(default=datetime.datetime.now)


def make_Metadata(db_alias='omega', collection=None):
    # this is to create context specific Metadata class that takes the
    # database from the given alias at the time of use
    from omegaml.documents import Metadata as Metadata_base
    class Metadata(Metadata_base, Document):
        # override db_alias in gridfile
        gridfile = FileField(
            db_alias=db_alias,
            collection_name=collection or settings().OMEGA_MONGO_COLLECTION)
        # the actual db is defined at runtime
        meta = {
            'db_alias': db_alias,
            'strict': False,
            'indexes': [
                # unique entry
                {
                    'fields': ['bucket', 'prefix', 'name'],
                },
                'created',  # most recent is last, i.e. [-1]
            ]
        }

        def __new__(cls, *args, **kwargs):
            # undo the Metadata.__new__ protection
            newcls = super(Metadata, cls).__real_new__(cls)
            return newcls

        def __eq__(self, other):
            return self.objid == other.objid

        def __unicode__(self):
            fields = ('name', 'bucket', 'prefix', 'created', 'kind')
            kwargs = ('%s=%s' % (k, getattr(self, k))
                      for k in self._fields.keys() if k in fields)
            return u"Metadata(%s)" % ','.join(kwargs)

        def save(self, *args, **kwargs):
            assert self.name is not None, "a dataset name is needed before saving"
            self.modified = datetime.datetime.now()
            return super(Metadata_base, self).save(*args, **kwargs)

    return Metadata


def make_QueryCache(db_alias='omega'):
    class QueryCache(Document):
        collection = StringField()
        key = StringField()
        value = DictField()
        meta = {
            'db_alias': db_alias,
            'indexes': [
                'key',
            ]
        }

    return QueryCache


def raise_on_use(exc):
    def inner(*args, **kwargs):
        raise exc

    return inner


Metadata.__real_new__ = Metadata.__new__
Metadata.__new__ = raise_on_use(NameError("You must use make_Metadata()() to instantiate a working object"))
