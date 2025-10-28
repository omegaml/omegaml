omegaml.mdataframe
==================

.. autoclass:: omegaml.mdataframe.MDataFrame
   :members: groupby, inspect, __len__, value, sort, head, skip, merge, query, query_inplace, create_index, loc
   :special-members: __len__

.. autoclass:: omegaml.mdataframe.MSeries
   :inherited-members: groupby, inspect, value, sort, head, skip, merge, query, query_inplace, create_index, loc
   :special-members: __len__


.. autoclass:: omegaml.mdataframe.MGrouper
   :members: agg, aggregate, count

.. autoclass:: omegaml.mdataframe.MLocIndexer
   :special-members: __getitem__

.. autoclass:: omegaml.mdataframe.MPosIndexer
   :special-members: __getitem__

.. autoclass:: omegaml.mixins.mdf.ApplyContext

.. autoclass:: omegaml.mixins.mdf.ApplyArithmetics
   :special-members: __mul__, __add__,

.. autoclass:: omegaml.mixins.mdf.ApplyDateTime

.. autoclass:: omegaml.mixins.mdf.ApplyString

.. autoclass:: omegaml.mixins.mdf.ApplyAccumulators

