"""
omegaml write and read large CSV files from/to remote or local file paths
Supports s3, hdfs, http/s, sftp, scp, ssh

Usage:
    # read
    om.read_csv('protocol://path/test.csv', 'foobar')

    # write
    mdf = om.datasets.getl('tripdata')
    mdf.to_csv('protocol://path/test.csv')

    -- note path can be local, s3, http/s, scp, ftp, ssh (anything that smart_open supports,
       see https://github.com/RaRe-Technologies/smart_open

(c) 2019, 2020 omegaml.io by oneseven GmbH, Zurich, Switzerland
"""
import pandas as pd
from tqdm import tqdm

try:
    from smart_open import open as open_file
except:
    open_file = open


class IOToolsMDFMixin:
    def to_csv(mdf, csvfn, chunksize=10000, maxobs=None, apply=None, mode='w', open_kwargs=None, **kwargs):
        """
        write MDataframe to s3, hdfs, http/s, sftp, scp, ssh, write to om.datasets

        Usage:
            mdf = om.datasets.getl('name')
            mdf.to_csv('/path/filename.csv')
        """
        df_iter = mdf.iterchunks(chunksize=chunksize)
        _chunked_to_csv(df_iter, csvfn, mode, apply, open_kwargs=open_kwargs, **kwargs)


class IOToolsStoreMixin:
    def read_csv(self, csvfn, name, chunksize=10000, append=False, apply=None, mode='r',
                 open_kwargs=None, **kwargs):
        """
        read large files from s3, hdfs, http/s, sftp, scp, ssh, write to om.datasets

        Usage:

            To insert a local csv file into a dataset::

                om.datasets.read_csv('/path/filename.csv', 'dataset-name')

            To insert a file stored in any of the supported locations specify
            its fully qualified location and filename. The specific format must
            be specified according to the `smart_open`_ library::

                om.datasets.read_csv('https://...', 'dataset-name')
                om.datasets.read_csv('s3://...', 'dataset-name')
                om.datasets.read_csv('hdfs://...', 'dataset-name')
                om.datasets.read_csv('sftp://...', 'dataset-name')
                om.datasets.read_csv('scp://...', 'dataset-name')
                om.datasets.read_csv('ssh://...', 'dataset-name')

            Optionally define a function to receives each chunk as a dataframe
            and apply further processing (e.g. transformations, filtering)::

                def process(df):
                    # apply any processing to df
                    return df

                om.datasets.read_csv(...., apply=process)

        Args:
            csvfn (str): the fully qualified path and name of the csv file,
               according to the `smart_open`_ library
            chunksize (int): the size of each chunk processed before writing
                to the dataset
            append (bool): if True, appends to the dataset. defaults to False
            apply (callable): if specified, each chunk is forwarded as a
               DataFrame and the returned result is inserted to the dataset.
               Use this for transformations or filtering
            mode (str): file open mode, defaults to r
            open_kwargs (dict): additional kwargs to `smart_open`_
            **kwargs: additional kwargs are passed to ``pandas.read_csv``

        Returns:
            MDataFrame

        See Also:

            * `smart_open` https://github.com/RaRe-Technologies/smart_open
            * `pandas.read_csv`

        .. _smart_open: https://github.com/RaRe-Technologies/smart_open
        """
        store = self
        open_kwargs = open_kwargs or {}
        with open_file(csvfn, mode=mode, **open_kwargs) as fin:
            it = pd.read_csv(fin, chunksize=chunksize, iterator=True, **kwargs)
            pbar = tqdm(it)
            try:
                for i, chunkdf in enumerate(pbar):
                    if apply:
                        result = apply(chunkdf)
                        chunkdf = chunkdf if result is None else result
                    store.put(chunkdf, name, append=(i > 0) or append)
            finally:
                pbar.close()
        return store.getl(name)

    def to_csv(self, name, csvfn, chunksize=10000, apply=None, mode='w', open_kwargs=None, **kwargs):
        """ write any dataframe to s3, hdfs, http/s, sftp, scp, ssh

        Usage:

            To write a dataframe::

                om.datasets.write_csv('dataframe-dataset', '/path/to/filename')

            To write a large dataframe in chunks:

                om.datasets.write_csv('dataframe-dataset', '/path/to/filename',
                chunksize=100)

        Args:
            name (str): the name of the dataframe dataset
            csvfn (str): the fully qualified path and name of the csv file,
               according to the `smart_open`_ library
            chunksize (int): the size of each chunk processed before writing
                to the file
            apply (callable): if specified, each chunk is forwarded as a
               DataFrame and the returned result is written to the file.
               Use this for transformations or filtering
            mode (str): file open mode, defaults to w
            open_kwargs (dict): additional kwargs to `smart_open`_
            **kwargs: additional kwargs are passed to ``pandas.to_csv``

        See Also:

            * ``pandas.to_csv``
        """
        df_iter = self.get(name, chunksize=chunksize)
        _chunked_to_csv(df_iter, csvfn, mode, apply, open_kwargs=open_kwargs, **kwargs)


def _chunked_to_csv(df_iter, csvfn, mode, apply, open_kwargs=None, **kwargs):
    open_kwargs = open_kwargs or {}
    with open_file(csvfn, mode, **open_kwargs) as fout:
        for i, chunkdf in tqdm(enumerate(df_iter)):
            if apply:
                result = apply(chunkdf)
                chunkdf = chunkdf if result is None else result
            chunkdf.to_csv(fout, **kwargs)
