from multiprocessing import Pool
from itertools import repeat

import math

import os

from omegaml.mongoshim import MongoClient 

pool = None

def dfchunker(df, size=10000):
    """ chunk a dataframe as in iterator """
    return (df.iloc[pos:pos + size].copy() for pos in range(0, len(df), size))


def insert_chunk(job):
    """
    insert one chunk of data 

    :param job: the (dataframe, mongo_url, collection_name) tuple. mongo_url
                should include the database name, as the collection is taken
                from the default database of the connection.
    """
    sdf, mongo_url, collection_name = job
    client = MongoClient(mongo_url, authSource='admin')
    db = client.get_database()
    collection = db[collection_name]
    result = collection.insert_many(sdf.to_dict(orient='records'))
    client.close()
    return mongo_url, db.name, collection_name, len(result.inserted_ids)


def fast_insert(df, omstore, name, chunk_size=int(1e4)):
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
    global pool
    if len(df) * len(df.columns) > chunk_size:
        mongo_url = omstore.mongo_url
        collection_name = omstore.collection(name).name
        # we crossed upper limits of single threaded processing, use a Pool
        # use the cached pool
        cores = max(1, math.ceil(os.cpu_count() / 2))
        pool = pool or Pool(processes=cores)
        jobs = zip(dfchunker(df, size=chunk_size),
                   repeat(mongo_url), repeat(collection_name))
        pool.map(insert_chunk, (job for job in jobs))
    else:
        # still within bounds for single threaded inserts
        omstore.collection(name).insert_many(df.to_dict(orient='records'))
