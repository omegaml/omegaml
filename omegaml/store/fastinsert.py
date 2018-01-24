from multiprocessing import Pool
from itertools import repeat
from pymongo import MongoClient


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
    collection = MongoClient(mongo_url).get_database()[collection_name]
    collection.insert_many(sdf.to_dict(orient='records'))


def fast_insert(df, omstore, name):
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
    mongo_url = omstore.mongo_url
    collection_name = omstore.collection(name).full_name
    if len(df) * len(df.columns) > 10000:
        # we crossed upper limits of single threaded processing, use a Pool
        pool = Pool()
        jobs = zip(dfchunker(df), repeat(mongo_url), repeat(collection_name))
        pool.map(insert_chunk, (job for job in jobs))
    else:
        # still within bounds for single threaded inserts
        collection = MongoClient(mongo_url).get_database()[collection_name]
        collection.insert_many(df.to_dict(orient='records'))
