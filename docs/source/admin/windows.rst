Windows
=======

.. note::

    Should use WSL

working as a client is SUPPORTED
runtime worker is not NOT OFFICIALLY SUPPORTED on windows due to celery not supporting windows since v4.x
(however it works, with limits: no concurrency)

# python 3.9
$ pip install "celery < 5"

celery worker
-------------

source of issue: https://www.distributedpython.com/2018/08/21/celery-4-windows/

# using this, prefork should work
set FORKED_BY_MULTIPROCESSING=1

# it prefork does not work, use --pool solo
$ celery worker --pool solo -A omegaml.celeryapp -Q win -debuglevel=DEBUG -E

Pool solo means that there is only 1 worker process, thus no parallel processing.
You may, however, start multiple solo processes which should give you parallel
processing nevertheless.

celery R worker
---------------

R> library(reticulate)
R> om <- import("omegaml")
R> om$runtimes$rsystem$load()
R> om$runtimes$rsystem$start_worker(om, queue = "win -E --pool solo")

In Windows, R workers support pool solo only.


setup ipykernel
---------------

python -m ipykernel install --name ompython3 --env=omega

install r
---------

https://www.biostars.org/p/498049/

conda config --add channels conda-forge
conda config --set channel_priority strict
conda install -c conda-forge r-base

better: use miniforge and r-essentials



