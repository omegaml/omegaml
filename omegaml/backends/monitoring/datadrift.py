import numpy as np
import pandas as pd

from omegaml.backends.monitoring.base import DriftMonitorBase


class DataDriftMonitor(DriftMonitorBase):
    def __init__(self, dataset=None, store=None, query=None, tracking=None, **kwargs):
        super().__init__(resource=dataset, store=store, query=query,
                         tracking=tracking, **kwargs)

    def snapshot(self, dataset=None, chunksize=None, columns=None, _prefix=None, kind='data', **query):
        """
        Take a snapshot of a dataset and log its feature distribution for later drift detection

        Args:
            dataset (str|pd.DataFrame|np.ndarray): the dataset to snapshot
            chunksize (int): the chunksize to use for reading the dataset
            columns (list): the columns to snapshot, defaults to all columns
            query (str|kwargs): additional query parameters to use when reading the dataset.
               If the dataset is a DataFrame, this is passed to df.query(); if the dataset is a
               stored resource, this is passed as store.get(, **query)

        Returns:
            dict: the snapshot
        """
        # TODO: for chunksizes need to combine hist for multiple chunks
        # -- https://stackoverflow.com/a/57884457/890242
        dataset = dataset if dataset is not None else self._resource
        query = query or self._query
        if isinstance(dataset, pd.DataFrame):
            df = dataset
            query = query.get('query')
            if query:
                df = df.query(query) if isinstance(query, str) else df[query]
        else:
            df = self.store.get(dataset, **query)
            if isinstance(df, np.ndarray):
                df = pd.DataFrame(df)
                df.columns = [str(col) for col in
                              df.columns]  # ensure column names are strings (needed for json storage)
        snapshot = self._do_snapshot(df, columns=columns, name=str(dataset), kind=kind, _prefix=_prefix)
        return snapshot
