import datetime

from mongoengine.base.fields import ObjectIdField
from mongoengine.document import Document
from mongoengine.fields import StringField, FileField, DictField, DateTimeField


class Metadata(Document):
    # various kinds of data
    PANDAS_DFROWS = 'pandas.dfrows'
    PANDAS_HDF = 'pandas.hdf'
    PYTHON_DATA = 'python.data'
    PANDAS_DFGROUP = 'pandas.dfgroup'
    SKLEARN_JOBLIB = 'sklearn.joblib'
    OMEGAML_JOBS = 'script.ipynb'
    OMEGAML_RUNNING_JOBS = 'job.run'
    KINDS = (PANDAS_DFROWS, PANDAS_HDF, PYTHON_DATA, SKLEARN_JOBLIB, PANDAS_DFGROUP, OMEGAML_JOBS, OMEGAML_RUNNING_JOBS)
    # fields
    #: this is the name of the data
    name = StringField()
    #: bucket
    bucket = StringField()
    #: prefix
    prefix = StringField()
    #: kind of data
    kind = StringField(choices=KINDS)
    #: for PANDAS_HDF and SKLEARN_JOBLIB this is the gridfile
    gridfile = FileField(db_alias='omega', collection_name='store')
    #: for PANDAS_DFROWS this is the collection
    collection = StringField()
    #: for PYTHON_DATA this is the actual document
    objid = ObjectIdField()
    #: customer-defined other meta attributes
    attributes = DictField()
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

    def __unicode__(self):
        kwargs = ('%s=%s' % (k, getattr(self, k))
                  for k in self._fields.keys())
        return u"Metadata(%s)" % ','.join(kwargs)
