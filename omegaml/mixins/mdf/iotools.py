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
            om.datasets.read_csv('/path/filename.csv', 'dataset-name')

            Optionally define a process function that receives each dataframe chunk for processing:

            def process(df):
                # apply any processing to df
                return df

            om.datasets.read_csv(...., apply=process)
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
        """
        write an object that returns an iterable dataframe to s3, hdfs, http/s, sftp, scp, ssh

        Usage:
            om.datasets.write_csv(name, '/path/to/filename')
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
