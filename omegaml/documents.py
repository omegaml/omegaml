from mongoengine.base.fields import ObjectIdField
from mongoengine.document import Document
from mongoengine.fields import StringField, FileField, DictField
class Metadata(Document):
    # various kinds of data
    PANDAS_DFROWS = 'pandas.dfrows'
    PANDAS_HDF = 'pandas.hdf'
    PYTHON_DATA = 'python.data'
    SKLEARN_JOBLIB = 'sklearn.joblib'
    KINDS = (PANDAS_DFROWS, PANDAS_HDF, PYTHON_DATA, SKLEARN_JOBLIB)
    # fields
    #: this is the name of the data
    name = StringField()
    #: kind of data
    kind = StringField(choices=KINDS)
    #: for PANDAS_HDF and SKLEARN_JOBLIB this is the gridfile
    gridfile = FileField(collection_name='store')
    #: for PANDAS_DFROWS this is the collection
    collection = StringField()
    #: for PYTHON_DATA this is the actual document
    objid = ObjectIdField()
    #: other meta attributes
    metadata = DictField()
    # the actual db is defined in settings, OMEGA_MONGO_URL
    meta = {'db_alias' : 'omega'}
