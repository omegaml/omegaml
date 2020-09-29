import math
import os
from itertools import repeat
from joblib import delayed, Parallel

from omegaml.util import PickableCollection

default_chunksize = int(1e4)


def dfchunker(df, size=default_chunksize):
    """ chunk a dataframe as in iterator """
    return (df.iloc[pos:pos + size] for pos in range(0, len(df), size))


def insert_chunk(job):
    """
    insert one chunk of data

    :param job: the (dataframe, mongo_url, collection_name) tuple. mongo_url
                should include the database name, as the collection is taken
                from the default database of the connection.
    """

    sdf, collection = job
    result = collection.insert_many(sdf.to_dict(orient='records'))
    collection.database.client.close()
    return len(result.inserted_ids)


def fast_insert(df, omstore, name, chunksize=default_chunksize):
    """
    fast insert of dataframe to mongodb

    Depending on size use single-process or multiprocessing. Typically
    multiprocessing is faster on datasets with > 10'000 data elements
    (rows x columns). Note this may max out your CPU and may use
    processor count * chunksize of additional memory. The chunksize is
    set to 10'000. The processor count is the default used by multiprocessing,
    typically the number of CPUs reported by the operating system.

    :param df: dataframe
    :param omstore: the OmegaStore to use. will be used to get the mongo_url
    :param name: the dataset name in OmegaStore to use. will be used to get the
    collection name from the omstore
    """
    # this is the fastest implementation (pool)
    # #records	pool	thread/wo copy	thread/w copy	pool w=0	pool dict	no chunking
    # 0.1m        1.47     2.06            2.17           1.59        2.11        2.28
    # 1m         17.4     19.8            20.6            16         17.8        22.2
    # 10m       149      193             183             177        213         256
    # based on
    # df = pd.DataFrame({'x': range(rows)})
    # om.datasets.put(df, 'test', replace=True) # no chunking: chunksize=False
    # - pool mp Pool, passes copy of df chunks, to_dict in pool processes
    # - thread/wo copy uses ThreadPool, shared memory on df
    # - thread/w copy uses ThreadPool, copy of chunks
    # - pool w=0 disables the mongo write concern
    # - pool dict performs to_dict on chunking, passes list of json docs pools just insert
    # - no chunking sets chunksize=False
    if chunksize and len(df) * len(df.columns) > chunksize:
        collection = PickableCollection(omstore.collection(name))
        # we crossed upper limits of single threaded processing, use a Pool
        # use the cached pool
        cores = max(1, math.ceil(os.cpu_count() / 2))
        jobs = zip(dfchunker(df, size=chunksize),
                   repeat(collection))
        approx_jobs = int(len(df) / chunksize)
        with Parallel(n_jobs=cores, backend='omegaml', verbose=False) as p:
            runner = delayed(insert_chunk)
            p_jobs = (runner(job) for job in jobs)
            p._job_count = approx_jobs
            p(p_jobs)
    else:
        # still within bounds for single threaded inserts
        omstore.collection(name).insert_many(df.to_dict(orient='records'))
