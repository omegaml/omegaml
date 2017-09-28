TEST
====

.. code:: ipython2

    # WHY?
    import sys
    sys.path.insert(0, '/home/patrick/projects/omegaml')

.. code:: ipython2

    import omegaml as om
    
    om.datasets.mongodb




.. parsed-literal::

    Database(MongoClient(host=['localhost:27017'], document_class=dict, tz_aware=False, connect=False, serverselectiontimeoutms='2500', read_preference=Primary()), u'omega')



.. code:: ipython2

    import pandas as pd
    import numpy as np 
    
    df = pd.DataFrame({'x': np.random.random(size=10)})
    df['x'] = df.x.astype(np.float64)
    df *= 1.0
    db = om.datasets.mongodb
    coll = db['xx']
    
    coll.insert_many(df.to_dict('records'))




.. parsed-literal::

    <pymongo.results.InsertManyResult at 0x7f0c6b8230d8>



.. code:: ipython2

    df.dtypes




.. parsed-literal::

    x    float64
    dtype: object



.. code:: ipython2

    df = pd.DataFrame({'x': range(10)}, index=pd.DatetimeIndex(pd.date_range(pd.datetime(2016,1,1), pd.datetime(2016,1,10))))
    print(df.index)
    dfx = df.reset_index()
    om.datasets.put(dfx, 'date_index', append=False)
    dfxx = om.datasets.get('date_index').set_index('index')
    del dfxx.index.name
    dfxx


.. parsed-literal::

    DatetimeIndex(['2016-01-01', '2016-01-02', '2016-01-03', '2016-01-04',
                   '2016-01-05', '2016-01-06', '2016-01-07', '2016-01-08',
                   '2016-01-09', '2016-01-10'],
                  dtype='datetime64[ns]', freq='D')




.. raw:: html

    <div>
    <table border="1" class="dataframe">
      <thead>
        <tr style="text-align: right;">
          <th></th>
          <th>x</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <th>2016-01-01</th>
          <td>0</td>
        </tr>
        <tr>
          <th>2016-01-02</th>
          <td>1</td>
        </tr>
        <tr>
          <th>2016-01-03</th>
          <td>2</td>
        </tr>
        <tr>
          <th>2016-01-04</th>
          <td>3</td>
        </tr>
        <tr>
          <th>2016-01-05</th>
          <td>4</td>
        </tr>
        <tr>
          <th>2016-01-06</th>
          <td>5</td>
        </tr>
        <tr>
          <th>2016-01-07</th>
          <td>6</td>
        </tr>
        <tr>
          <th>2016-01-08</th>
          <td>7</td>
        </tr>
        <tr>
          <th>2016-01-09</th>
          <td>8</td>
        </tr>
        <tr>
          <th>2016-01-10</th>
          <td>9</td>
        </tr>
      </tbody>
    </table>
    </div>




.. code:: ipython2

    midx = pd.MultiIndex(levels=[[u'bar', u'baz', u'foo', u'qux'], [u'one', u'two']],
               labels=[[0, 0, 1, 1, 2, 2, 3, 3], [0, 1, 0, 1, 0, 1, 0, 1]],
               names=[u'first', u'second'])
    midxdf = midx.to_series().reset_index()
    om.datasets.put(midxdf, 'midx')
    om.datasets.get('midx')
    #pd.MultiIndex(levels=[midxdf.first, midxdf.second], )
    midx
    def unravel_index(df):
        """ 
        convert index columns into dataframe columns
        
        :param df: the dataframe
        :return: the unravelled dataframe, meta
        """
        # remember original names
        idx_meta = {
            'names': df.index.names,
        }
        # convert index names so we can restore them later
        store_idxnames = ['__idx_{}'.format(name or i) 
                          for i, name in enumerate(idx_meta['names'])]
        df.index.names = store_idxnames
        unravelled = df.reset_index(), idx_meta
        # restore index names on original dataframe
        df.index.names = idx_meta['names']
        return unravelled
    
    def restore_index(df, idx_meta):
        """
        restore index proper
        
        :parm
        """
        # -- get index columns
        index_cols = [col for col in df.columns if col.startswith('__idx')]
        # -- set index columns
        result = df.set_index(index_cols)
        result.index.names = idx_meta['names']
        return result
    
    from pandas.util.testing import assert_frame_equal
    
    tsidx = pd.date_range(pd.datetime(2016,1,1), pd.datetime(2016,5,1))
    df = pd.DataFrame({'x': range(0, len(tsidx))}, index=tsidx)
    dfx, idx_meta = unravel_index(df)
    dfxx = restore_index(dfx, idx_meta)
    df.columns = [col.replace('__idx_', '') for col in df.columns]
    
    #dfx.set_index(['__idx_first', '__idx_second']).index
    om.datasets.put(dfx, 'testxx', append=False)
    dfxx = restore_index(om.datasets.get('testxx'), idx_meta)
    assert_frame_equal(df, dfxx)


.. parsed-literal::

    /home/patrick/projects/shrebo-ext/edge/omegaml/omegaml/store/base.py:300: UserWarning: midx already exists, will append rows
      warn('%s already exists, will append rows' % name)


::


    ---------------------------------------------------------------------------

    AttributeError                            Traceback (most recent call last)

    <ipython-input-6-9e641c32b308> in <module>()
          3            names=[u'first', u'second'])
          4 midxdf = midx.to_series().reset_index()
    ----> 5 om.datasets.put(midxdf, 'midx')
          6 om.datasets.get('midx')
          7 #pd.MultiIndex(levels=[midxdf.first, midxdf.second], )


    /home/patrick/projects/shrebo-ext/edge/omegaml/omegaml/store/base.py in put(self, obj, name, attributes, **kwargs)
        256             index = kwargs.get('index', None)
        257             return self.put_dataframe_as_documents(
    --> 258                 obj, name, append, attributes, index, timestamp)
        259         elif is_ndarray(obj):
        260             return self.put_ndarray_as_hdf(obj, name,


    /home/patrick/projects/shrebo-ext/edge/omegaml/omegaml/store/base.py in put_dataframe_as_documents(self, obj, name, append, attributes, index, timestamp)
        327         }
        328         # create mongon indicies for data frame index columns
    --> 329         df_idxcols = [col for col in obj.columns if col.startswith('__idx_')]
        330         if df_idxcols:
        331             keys, idx_kwargs = MongoQueryOps().make_index(df_idxcols)


    /home/patrick/projects/shrebo-ext/edge/omegaml/omegaml/store/base.py in <listcomp>(.0)
        327         }
        328         # create mongon indicies for data frame index columns
    --> 329         df_idxcols = [col for col in obj.columns if col.startswith('__idx_')]
        330         if df_idxcols:
        331             keys, idx_kwargs = MongoQueryOps().make_index(df_idxcols)


    AttributeError: 'int' object has no attribute 'startswith'


.. code:: ipython2

    import omegaml as om
    import pandas as pd
    
    tsidx = pd.date_range(pd.datetime(2016,1,1), pd.datetime(2016,5,1))
    midx = pd.MultiIndex(levels=[[u'bar', u'baz', u'foo', u'qux'], [u'one', u'two']],
               labels=[[0, 0, 1, 1, 2, 2, 3, 3], [0, 1, 0, 1, 0, 1, 0, 1]],
               names=[u'first', u'second'])
    idx = midx
    
    
    om.datasets.put(df, 'testidx', append=False)
    om.datasets.get('testidx', __idx_first='bar')
    #list(om.datasets.collection('testidx').find({'__idx_first': 'bar'}))


::


    ---------------------------------------------------------------------------

    InvalidDocument                           Traceback (most recent call last)

    <ipython-input-5-cb3cb4695f65> in <module>()
          9 
         10 
    ---> 11 om.datasets.put(df, 'testidx', append=False)
         12 om.datasets.get('testidx', __idx_first='bar')
         13 #list(om.datasets.collection('testidx').find({'__idx_first': 'bar'}))


    /home/patrick/projects/shrebo-ext/edge/omegaml/omegaml/store/base.py in put(self, obj, name, attributes, **kwargs)
        256             index = kwargs.get('index', None)
        257             return self.put_dataframe_as_documents(
    --> 258                 obj, name, append, attributes, index, timestamp)
        259         elif is_ndarray(obj):
        260             return self.put_ndarray_as_hdf(obj, name,


    /home/patrick/projects/shrebo-ext/edge/omegaml/omegaml/store/base.py in put_dataframe_as_documents(self, obj, name, append, attributes, index, timestamp)
        334         obj.columns = [str(col) for col in obj.columns]
        335         # bulk insert
    --> 336         collection.insert_many(obj.to_dict(orient='records'))
        337         signals.dataset_put.send(sender=None, name=name)
        338         return self._make_metadata(name=name,


    /usr/local/anaconda/envs/py3k/lib/python3.5/site-packages/pymongo/collection.py in insert_many(self, documents, ordered, bypass_document_validation)
        682         blk = _Bulk(self, ordered, bypass_document_validation)
        683         blk.ops = [doc for doc in gen()]
    --> 684         blk.execute(self.write_concern.document)
        685         return InsertManyResult(inserted_ids, self.write_concern.acknowledged)
        686 


    /usr/local/anaconda/envs/py3k/lib/python3.5/site-packages/pymongo/bulk.py in execute(self, write_concern)
        468                 self.execute_no_results(sock_info, generator)
        469             elif sock_info.max_wire_version > 1:
    --> 470                 return self.execute_command(sock_info, generator, write_concern)
        471             else:
        472                 return self.execute_legacy(sock_info, generator, write_concern)


    /usr/local/anaconda/envs/py3k/lib/python3.5/site-packages/pymongo/bulk.py in execute_command(self, sock_info, generator, write_concern)
        300             results = _do_batched_write_command(
        301                 self.namespace, run.op_type, cmd,
    --> 302                 run.ops, True, self.collection.codec_options, bwc)
        303 
        304             _merge_command(run, full_result, results)


    InvalidDocument: Cannot encode object: 0


.. code:: ipython2

    import pandas as pd
    import omegaml as om
    df = pd.DataFrame({'x' : range(5, 10)})
    def convert(df):
        df = df.astype('O')
        return df
    %timeit convert(df)


.. parsed-literal::

    10000 loops, best of 3: 113 µs per loop


.. code:: ipython2

    import pandas as pd
    import omegaml as om
    df = pd.DataFrame({'x' : range(5, 10),
                       'y' : range(5, 10)})
    om.datasets.put(df, 'testxx', append=False)
    om.datasets.getl('testxx').loc[4].value




.. parsed-literal::

    x    9
    y    9
    Name: 4, dtype: int64



.. code:: ipython2

    df = pd.DataFrame({'x' : range(5, 10),
                       'y' : range(5, 10),
                       'z' : range(5, 10)})
    df.loc[[2,3]]




.. raw:: html

    <div>
    <table border="1" class="dataframe">
      <thead>
        <tr style="text-align: right;">
          <th></th>
          <th>x</th>
          <th>y</th>
          <th>z</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <th>2</th>
          <td>7</td>
          <td>7</td>
          <td>7</td>
        </tr>
        <tr>
          <th>3</th>
          <td>8</td>
          <td>8</td>
          <td>8</td>
        </tr>
      </tbody>
    </table>
    </div>



.. code:: ipython2

    df = pd.DataFrame({'x' : range(5, 10),
                       'y' : range(5, 10),
                       'z' : range(5, 10)})
    df.set_index(['x', 'y']).loc[5:6,'z']




.. parsed-literal::

    x  y
    5  5    5
    6  6    6
    Name: z, dtype: int64



.. code:: ipython2

    df = pd.DataFrame({'x' : range(5, 10),
                       'y' : range(5, 10),
                       'z' : range(5, 10)})
    df.loc[0,'x']




.. parsed-literal::

    5



.. code:: ipython2

    import string
    data = {
                'a': list(range(1, 10)),
                'b': list(range(1, 10))
    }
    idx = string.ascii_lowercase[0:9]
    df = pd.DataFrame(data, index=(c for c in idx))
    df.loc[['c', 'f']]




.. raw:: html

    <div>
    <table border="1" class="dataframe">
      <thead>
        <tr style="text-align: right;">
          <th></th>
          <th>a</th>
          <th>b</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <th>c</th>
          <td>3</td>
          <td>3</td>
        </tr>
        <tr>
          <th>f</th>
          <td>6</td>
          <td>6</td>
        </tr>
      </tbody>
    </table>
    </div>



.. code:: ipython2

    midx = pd.MultiIndex(levels=[[u'bar', u'baz', u'foo', u'qux'],
                                         [u'one', u'two']],
                                 labels=[
                                     [0, 0, 1, 1, 2, 2, 3, 3],
                                     [0, 1, 0, 1, 0, 1, 0, 1]],
                                 names=[u'first', u'second'])
    df = pd.DataFrame({'x': range(0, len(midx))}, index=midx)
    om.datasets.put(df, 'testxx', append=False)
    list(om.datasets.collection('testxx').find( {u'_idx_first': 'bar', u'_idx_second': 'one'}))




.. parsed-literal::

    [{'_id': ObjectId('5827b2adde39d16c7299c072'),
      '_idx_first': 'bar',
      '_idx_second': 'one',
      'x': 0}]



.. code:: ipython2

    df.iloc




.. parsed-literal::

    <pandas.core.indexing._iLocIndexer at 0x7feccc0b30f0>



.. code:: ipython2

    '__test'.split('__
                   ')




.. parsed-literal::

    ['', 'test']



.. code:: ipython2

    cl = om.datasets.collection('testxx')
    list(cl.find())



::


    ---------------------------------------------------------------------------

    NameError                                 Traceback (most recent call last)

    <ipython-input-1-7d2e48a7f8db> in <module>()
    ----> 1 cl = om.datasets.collection('testxx')
          2 list(cl.find())


    NameError: name 'om' is not defined


.. code:: ipython2

    a = slice(0,1,2).start
    a





.. parsed-literal::

    0



.. code:: ipython2

    import pandas as pd
    import omegaml as om
    import numpy as np
    def make_df():
        df = pd.DataFrame({'x' : range(5, int(10000000))})
        return df
    def convert(df):
        df['x'] = df.x.astype('O')
        return df
    def to_records(df):
        for i, row in df.iterrows():
            yield row.to_dict()
    def insertpart(rows):
        from omegaml.store.base import OmegaStore
        coll = OmegaStore(prefix='data/').collection('testxx')
        df = convert(pd.DataFrame.from_dict(rows))
        coll.insert_many(df.to_dict('records'))
        import gc
        gc.collect()
        
    def chunkit(df):
        for g, gdf in df.groupby(np.arange(len(df)) // 100000):
            yield gdf.to_dict()
            import gc
            gc.collect()
    
    def insertparallel(df):
        pool = mp.Pool(4)
        pool.map(insertpart, chunkit(df))
        
    def timed(f):
      import time
      start = time.time()
      ret = f()
      elapsed = time.time() - start
      return ret, elapsed
    
    if __name__ == '__main__':
        import multiprocessing as mp
        om.datasets.drop('testxx', force=True)
        df = make_df()
        df = convert(df)
        print(timed(lambda *args: insertparallel(df)))


.. parsed-literal::

    /usr/local/anaconda/envs/py3k/lib/python3.5/site-packages/pymongo/topology.py:143: UserWarning: MongoClient opened before fork. Create MongoClient with connect=False, or create client after forking. See PyMongo's documentation for details: http://api.mongodb.org/python/current/faq.html#using-pymongo-with-multiprocessing>
      "MongoClient opened before fork. Create MongoClient "
    /usr/local/anaconda/envs/py3k/lib/python3.5/site-packages/pymongo/topology.py:143: UserWarning: MongoClient opened before fork. Create MongoClient with connect=False, or create client after forking. See PyMongo's documentation for details: http://api.mongodb.org/python/current/faq.html#using-pymongo-with-multiprocessing>
      "MongoClient opened before fork. Create MongoClient "
    /usr/local/anaconda/envs/py3k/lib/python3.5/site-packages/pymongo/topology.py:143: UserWarning: MongoClient opened before fork. Create MongoClient with connect=False, or create client after forking. See PyMongo's documentation for details: http://api.mongodb.org/python/current/faq.html#using-pymongo-with-multiprocessing>
      "MongoClient opened before fork. Create MongoClient "
    /usr/local/anaconda/envs/py3k/lib/python3.5/site-packages/pymongo/topology.py:143: UserWarning: MongoClient opened before fork. Create MongoClient with connect=False, or create client after forking. See PyMongo's documentation for details: http://api.mongodb.org/python/current/faq.html#using-pymongo-with-multiprocessing>
      "MongoClient opened before fork. Create MongoClient "


.. parsed-literal::

    (None, 210.1572666168213)


.. code:: ipython2

    import omegaml as om
    from omegaml.mdataframe import MDataFrame
    %timeit list(om.datasets.collection('testxx').find())


.. parsed-literal::

    1 loop, best of 3: 43 s per loop


.. code:: ipython2

    l = range(0,10)
    


.. code:: ipython2

    %timeit coll.insert_many(to_records(df), ordered=False)

.. code:: ipython2

    coll = om.datasets.collection('testxx') 
    %timeit df.to_dict()


.. parsed-literal::

    10 loops, best of 3: 164 ms per loop


.. code:: ipython2

    
    %timeit coll.insert_many(df.to_dict('records'), ordered=False)


.. parsed-literal::

    1 loop, best of 3: 38.1 s per loop


.. code:: ipython2

    om.datasets.put(df, groupby='')

.. code:: ipython2

    group = ['a', 'b']
    values = [1,2]
    d = dict(zip(group, values))
    df = pd.DataFrame(d, index=range(0, len(d)))
    df.to_dict('records
               ')




.. parsed-literal::

    [{'a': 1, 'b': 2}, {'a': 1, 'b': 2}]



.. code:: ipython2

    d1 = {'a': 5}
    d2 = {'b': 6}
    d1.update(d2)
    d1.pop()




.. parsed-literal::

    {'a': 5}



.. code:: ipython2

    class a(object):
        def __getitem__(self, spec):
            return spec
            
    sl = a()[:,5]
    sl




.. parsed-literal::

    (slice(None, None, None), 5)



.. code:: ipython2

    list(coll.find())




.. parsed-literal::

    [{'_id': ObjectId('582678a0de39d158ed6f4aa1'), 'x': 1},
     {'_id': ObjectId('582678a0de39d158ed6f4aa2'), 'x': 2},
     {'_id': ObjectId('582678a0de39d158ed6f4aa3'), 'x': 3},
     {'_id': ObjectId('582678a0de39d158ed6f4aa4'), 'x': 4},
     {'_id': ObjectId('582678a0de39d158ed6f4aa5'), 'x': 5},
     {'_id': ObjectId('582678a0de39d158ed6f4aa6'), 'x': 6},
     {'_id': ObjectId('582678a0de39d158ed6f4aa7'), 'x': 7},
     {'_id': ObjectId('582678a0de39d158ed6f4aa8'), 'x': 8},
     {'_id': ObjectId('582678a0de39d158ed6f4aa9'), 'x': 9},
     {'_id': ObjectId('582678bade39d158ed6f4aaa'), 'x': 1.0},
     {'_id': ObjectId('582678bade39d158ed6f4aab'), 'x': 2.0},
     {'_id': ObjectId('582678bade39d158ed6f4aac'), 'x': 3.0},
     {'_id': ObjectId('582678bade39d158ed6f4aad'), 'x': 4.0},
     {'_id': ObjectId('582678bade39d158ed6f4aae'), 'x': 5.0},
     {'_id': ObjectId('582678bade39d158ed6f4aaf'), 'x': 6.0},
     {'_id': ObjectId('582678bade39d158ed6f4ab0'), 'x': 7.0},
     {'_id': ObjectId('582678bade39d158ed6f4ab1'), 'x': 8.0},
     {'_id': ObjectId('582678bade39d158ed6f4ab2'), 'x': 9.0},
     {'_id': ObjectId('582678f7de39d15ab250a26e'), 'x': 1.0},
     {'_id': ObjectId('582678f7de39d15ab250a26f'), 'x': 2.0},
     {'_id': ObjectId('582678f7de39d15ab250a270'), 'x': 3.0},
     {'_id': ObjectId('582678f7de39d15ab250a271'), 'x': 4.0},
     {'_id': ObjectId('582678f7de39d15ab250a272'), 'x': 5.0},
     {'_id': ObjectId('582678f7de39d15ab250a273'), 'x': 6.0},
     {'_id': ObjectId('582678f7de39d15ab250a274'), 'x': 7.0},
     {'_id': ObjectId('582678f7de39d15ab250a275'), 'x': 8.0},
     {'_id': ObjectId('582678f7de39d15ab250a276'), 'x': 9.0},
     {'_id': ObjectId('58267926de39d15afa6734df'), 'x': 1.0},
     {'_id': ObjectId('58267926de39d15afa6734e0'), 'x': 2.0},
     {'_id': ObjectId('58267926de39d15afa6734e1'), 'x': 3.0},
     {'_id': ObjectId('58267926de39d15afa6734e2'), 'x': 4.0},
     {'_id': ObjectId('58267926de39d15afa6734e3'), 'x': 5.0},
     {'_id': ObjectId('58267926de39d15afa6734e4'), 'x': 6.0},
     {'_id': ObjectId('58267926de39d15afa6734e5'), 'x': 7.0},
     {'_id': ObjectId('58267926de39d15afa6734e6'), 'x': 8.0},
     {'_id': ObjectId('58267926de39d15afa6734e7'), 'x': 9.0},
     {'1': 0.3711823673084317, '_id': ObjectId('58267962de39d15afa6734fb')},
     {'1': 0.9852658755614759, '_id': ObjectId('58267962de39d15afa6734fc')},
     {'1': 0.9901468306077602, '_id': ObjectId('58267962de39d15afa6734fd')},
     {'1': 0.12299521735403429, '_id': ObjectId('58267962de39d15afa6734fe')},
     {'1': 0.3455834874583561, '_id': ObjectId('58267962de39d15afa6734ff')},
     {'1': 0.8038320201324776, '_id': ObjectId('58267962de39d15afa673500')},
     {'1': 0.46082093593135887, '_id': ObjectId('58267962de39d15afa673501')},
     {'1': 0.296080334700752, '_id': ObjectId('58267962de39d15afa673502')},
     {'1': 0.036414842195998554, '_id': ObjectId('58267962de39d15afa673503')},
     {'1': 0.4916342037525985, '_id': ObjectId('58267962de39d15afa673504')},
     {'1': 0.0652152689233767, '_id': ObjectId('58267971de39d15afa673505')},
     {'1': 0.03434916158193413, '_id': ObjectId('58267971de39d15afa673506')},
     {'1': 0.6895309033209304, '_id': ObjectId('58267971de39d15afa673507')},
     {'1': 0.9458095324288607, '_id': ObjectId('58267971de39d15afa673508')},
     {'1': 0.2956413122440644, '_id': ObjectId('58267971de39d15afa673509')},
     {'1': 0.2892704742507375, '_id': ObjectId('58267971de39d15afa67350a')},
     {'1': 0.6662402845857539, '_id': ObjectId('58267971de39d15afa67350b')},
     {'1': 0.25619157172398677, '_id': ObjectId('58267971de39d15afa67350c')},
     {'1': 0.3747847092697826, '_id': ObjectId('58267971de39d15afa67350d')},
     {'1': 0.5253374300105172, '_id': ObjectId('58267971de39d15afa67350e')}]



.. code:: ipython2

    
    list(coll.find())




.. parsed-literal::

    []


