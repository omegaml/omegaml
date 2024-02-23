import numpy as np
import pandas as pd

from omegaml.backends.monitoring.base import DriftMonitorBase


class DataDriftMonitor(DriftMonitorBase):
    def __init__(self, dataset=None, store=None, query=None, tracking=None, kind=None, **kwargs):
        kind = kind or 'data'
        super().__init__(resource=dataset, store=store, query=query,
                         tracking=tracking, kind=kind, **kwargs)

    def snapshot(self, dataset=None, chunksize=None, columns=None, _prefix=None, name=None, kind=None, **query):
        """
        Take a snapshot of a dataset and log its feature distribution for later drift detection

        Args:
            dataset (str|pd.DataFrame|np.ndarray): the dataset to snapshot
            chunksize (int): the chunksize to use for reading the dataset
            columns (list): the columns to snapshot, defaults to all columns
            prefix (str): prefix to apply to all columns
            kind (str): the kind of the snapshot (model, data)
            query (str|kwargs): additional query parameters to use when reading the dataset.
               If the dataset is a DataFrame, this is passed to df.query(); if the dataset is a
               stored resource, this is passed as store.get(, **query)

        Returns:
            dict: the snapshot
        """
        # TODO: for chunksizes need to combine hist for multiple chunks
        # -- https://stackoverflow.com/a/57884457/890242
        kind = kind or self._kind
        dataset = dataset if dataset is not None else self._resource
        name = name or (dataset if isinstance(dataset, str) else f'{kind}:{type(dataset)}')
        query = query or self._query
        df = self._assert_dataframe(dataset, **query)
        snapshot = self._do_snapshot(df, columns=columns, name=name, kind=kind, _prefix=_prefix)
        self._log_snapshot(snapshot)
        return snapshot
