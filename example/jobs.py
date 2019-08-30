#!/usr/bin/env python
"""
example program to run in ipython
"""
# demo the functionality of the jobs API
from __future__ import absolute_import
from __future__ import print_function
from omegaml import Omega
from omegaml.documents import make_Metadata
from omegaml.util import override_settings
import argparse


def testOmegamlJobs(
        broker_url,
        queue,
        exchange,
        mongo_url,
        collection):
    # make sure to set accordingly
    override_settings(
        OMEGA_BROKER=broker_url,
        OMEGA_CELERY_DEFAULT_QUEUE=queue,
        OMEGA_CELERY_DEFAULT_EXCHANGE=exchange,
        OMEGA_MONGO_URL=mongo_url,
        OMEGA_NOTEBOOK_COLLECTION=collection
    )

    om = Omega()
    fs = om.jobs.get_fs(collection)
    nb_file = 'job_example.ipynb'
    with open(nb_file, 'r') as f:
        fs.put(f.read(), filename=nb_file)
    # list jobs
    job_list = om.jobs.list()
    print("Job list:")
    print(job_list)
    # run notebook
    result = om.jobs.run(nb_file)
    # retrieve result from metadata
    metadata = make_Metadata().objects.get(created=result.created)
    print("\n")
    print("Result from metadata:")
    file = om.jobs.get_result(metadata)
    print(file)
    print("Filename: {0}".format(file.filename))
    task_id = metadata.attributes.get('task_id')
    print("\n")
    print("Result from task_id:")
    print("Task ID: {0}".format(task_id))
    file = om.jobs.get_result(metadata)
    print(file)
    print("Filename: {0}".format(file.filename))
    # retrieve result from task_id
    print("\n")
    print("Result from notebook filename:")
    print("Notebook Script: {0}".format(nb_file))
    # retrieve result from task_id
    file = om.jobs.get_result(nb_file)
    print(file)
    print("Filename: {0}".format(file.filename))
    print("\n")
    print("Job Status:")
    print(om.jobs.get_status(nb_file))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--broker-url", action="store", help="celery broker url", required=True)
    parser.add_argument("--queue", action="store", help="celery queue", required=True)
    parser.add_argument("--exchange", action="store", help="celery exchange", required=True)
    parser.add_argument("--mongo-url", action="store", help="Mongo url", required=True)
    parser.add_argument("--collection", action="store", help="Mongo Notebook Collection", required=True)
    args = parser.parse_args()
    testOmegamlJobs(**vars(args))
