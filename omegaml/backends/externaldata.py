import six

from omegaml.backends.basedata import BaseDataBackend
import pandas as pd


class PandasExternalData(BaseDataBackend):

    """
    external data is stored as a uri on some external medium
    """
    SCHEMES = ['http', 'https', 'ftp', 'file', 's3']
    KIND = 'pandas.csv'

    @classmethod
    def supports(cls, obj, name, **kwargs):
        supported_scheme = _is_supported_scheme(obj, **kwargs)
        supported_type = _is_supported_type(obj, **kwargs)
        return supported_scheme | supported_type

    def put(self, obj, name, attributes=None, **kwargs):
        """
        Store external data (currently only csv)

        This supports various pandas file sources as:

        * storing the URI to an external csv file
        * storing a pd.DataFrame, pd.Series, as a csv, at an external URI
        * copying an external CSV from one URI to another URI

        Only URIs implemented by pandas.read_csv() are supported to store
        the URI (http, ftp, file, s3). Only s3 and local files are supported
        to copy a csv file from either a supported URI or from an object
        into a csv on s3 or on the local file system.

        Examples:

        # store a reference to S3
        om.datasets.put('s3://bucket/test/google.csv', 'google-s3')
        # from dataframe direcly to s3
        om.datasets.put(df, 'google-s3', uri='s3://bucket/test/google.csv')
        # from s3 into mongodb
        om.datasets.put(None, 'google-mongo', uri='s3://bucket/test/google.csv')
        # from dataframe to local
        om.datasets.put(df, 'google-local', uri='file:///tmp/google.csv')
        # from local directly to s3
        om.datasets.put('s3://bucket/test/google2.csv',
        'google-s3-direct', uri='file:///tmp/google.csv')

        :param obj: (str|pd.Series|pd.DataFrame) the object to store. If str
          must be URI of the form scheme://location/name.csv where scheme
          is one of the upported schemes by pandas.read_csv
        :param name: (str) the name of the object in the store
        :param attributes: custom attributes to store with the object
        """
        uri = kwargs.get('uri')
        # case object is a supported uri, e.g. s3://bucket/name.ext
        if _is_supported_scheme(obj, **kwargs):
            if uri is None:
                # store object as a location pointer with given name
                metadata = self.data_store.make_metadata(name, self.KIND,
                                                         attributes=attributes)
                metadata.uri = obj
            else:
                # read object, store in given location
                # then store as a location pointer with given name
                df = pd.read_csv(uri)
                metadata = self.data_store.put(df, name, uri=obj,
                                               attributes=attributes)
        # case object is a supported object type
        elif _is_supported_type(obj, **kwargs) and uri:
            # if object is None we read the file from the URI first
            if obj is None:
                obj = pd.read_csv(uri)
            # convert to CSV data
            data = obj.to_csv()
            # store in supported location
            if uri.startswith('s3://'):
                import s3fs
                data = obj.to_csv()
                fs = s3fs.S3FileSystem()
                with fs.open(uri, 'wb') as fout:
                    fout.write(data.encode(encoding='utf-8'))
                metadata = self.data_store.make_metadata(
                    name, self.KIND, attributes=attributes)
                metadata.uri = uri
            elif uri.startswith('file'):
                obj.to_csv(uri.replace('file://', ''))
                metadata = self.data_store.make_metadata(
                    name, self.KIND, attributes=attributes)
                metadata.uri = uri
            # case erroneous
            else:
                raise ValueError(
                    ('Not supported type obj={} with '
                     'name={} and uri={}').format(type(obj), name, uri))
        # case erroneous parameters
        else:
            raise ValueError(('Not supported type obj={} '
                              'with name={}').format(type(obj), name))
        return metadata.save()

    def get(self, name, version=-1, force_python=False, lazy=False, **kwargs):
        """
        Get a csv stored at an external location
        """
        meta = self.data_store.metadata(name)
        read_kwargs = meta.kind_meta.get('pandas_kwargs', {})
        read_kwargs.update(dict(usecols=kwargs.get('columns')))
        read_kwargs.update(kwargs)
        read_kwargs.update(kwargs.get('pandas_kwargs', {}))
        df = pd.read_csv(meta.uri, **read_kwargs)
        return df


def _is_supported_scheme(obj, **kwargs):
    if isinstance(obj, six.string_types):
        parts = obj.split('://')
        if len(parts) > 1:
            scheme, loc = parts
            return scheme in PandasExternalData.SCHEMES
    elif obj is None and kwargs.get('uri') is not None:
        return True
    return False


def _is_supported_type(obj, **kwargs):
    uri = kwargs.get('uri')
    supported_type = isinstance(obj, (pd.Series, pd.DataFrame))
    supported_scheme = _is_supported_scheme(uri)
    return supported_type & supported_scheme

