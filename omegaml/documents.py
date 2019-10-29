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

    #: the list of accepted data types. extend using OmegaStore.register_backend
    KINDS = [
        PANDAS_DFROWS, PANDAS_SEROWS, PANDAS_HDF, PYTHON_DATA, SKLEARN_JOBLIB,
        PANDAS_DFGROUP, OMEGAML_JOBS, OMEGAML_RUNNING_JOBS, SPARK_MLLIB
    ]


def make_Metadata():
    # this is to create context specific Metadata classes that take the
    # database from the given alias at the time of use
    class Metadata(Document):
        """
        Metadata stores information about objects in OmegaStore
        """

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
        gridfile = FileField(
            db_alias='omega',
            collection_name=settings().OMEGA_MONGO_COLLECTION)
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
        # the actual db is defined in settings, OMEGA_MONGO_URL
        meta = {
            'db_alias': 'omega',
            'indexes': [
                # unique entry
                {
                    'fields': ['bucket', 'prefix', 'name'],
                },
                'created',  # most recent is last, i.e. [-1]
            ]
        }

        def __eq__(self, other):
            return self.objid == other.objid

        def __unicode__(self):
            fields = ('name', 'bucket', 'prefix', 'created', 'kind')
            kwargs = ('%s=%s' % (k, getattr(self, k))
                      for k in self._fields.keys() if k in fields)
            return u"Metadata(%s)" % ','.join(kwargs)

    return Metadata


def make_QueryCache():
    class QueryCache(Document):
        collection = StringField()
        key = StringField()
        value = DictField()
        meta = {
            'db_alias': 'omega',
            'indexes': [
                'key',
            ]
        }

    return QueryCache
