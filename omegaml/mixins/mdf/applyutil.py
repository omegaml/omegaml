import pandas as pd

from omegaml.mdataframe import MDataFrame, MSeries


class UtilitiesMixin:
    """
    Add functionality to MDataFrame, MSeries
    """
    standard_quantiles = [.25, .5, .75]

    @property
    def dtypes(self):
        """
        Implement MDataFrame.dtypes to list all dtypes

        Returns:
            dtypes based on first row of data
        """
        if isinstance(self, MDataFrame):
            cursor = self.collection.find(limit=1)
            return self._get_dataframe_from_cursor(cursor)[self.columns].dtypes
        raise AttributeError('dtypes')

    @property
    def dtype(self):
        """
        Implement MSeries.dtype to get the dtype of a column

        Returns:
            dtype based on first row of data
        """
        if isinstance(self, MSeries):
            cursor = self.collection.find(limit=1)
            return self._get_dataframe_from_cursor(cursor)[self.name].dtype
        raise AttributeError('dtypes')

    def describe(self, quantiles=None):
        """
        implement MDataFrame.describe()

        Args:
            quantiles: a list of quantiles to compute, defaults to .25, .5, .75

        Returns:
            dataframe with quantiles
        """
        import numpy as np
        dtypes = self.dtypes
        # stats
        stats = ['mean', 'std', 'min', 'max']
        numcols = [col for col in dtypes.index
                   if np.issubdtype(dtypes[col], np.number)]
        specs = {col: stats for col in numcols}
        stats_df = self.apply(lambda v: v.agg(**specs)).value
        melted = stats_df.melt()
        melted['stat'] = (melted['variable']
                          .str.split('_')
                          .apply(lambda v: v[-1]))
        melted['variable'] = (melted['variable']
                              .str.split('_')
                              .apply(lambda v: '_'.join(v[:-1])))
        stats_df = melted.pivot_table(index='stat',
                                      columns='variable',
                                      values='value')
        # quantiles
        if quantiles:
            if not isinstance(quantiles, (tuple, list)):
                quantiles = self.standard_quantiles
            quants_df = self.quantile(quantiles).value
            stats_df = pd.concat([stats_df, quants_df], sort=False)
        return stats_df[numcols]

    def _amend_pipeline(self, pipeline):
        pipeline = super()._amend_pipeline(pipeline)
        if self.head_limit:
            pipeline.insert(0, {'$limit': self.head_limit})
        if self.skip_topn:
            pipeline.insert(0, {'$skip': self.skip_topn})
        return pipeline
