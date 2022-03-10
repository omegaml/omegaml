""" R system runtime support

This implements omegaml's R interface

How it works:

    Using the R:reticulate package omegaml is transparently available
    from within R and RStudio. For the runtime we start the omegaml
    worker (celery) using reticulate (see omworker.R).

    Storage:

        The RModelBackend implements the models storage backend to save and
        load models by providing a facade to the respective R functions.
        Model persistence works the same as with Python models, namely the
        backend generates a temporary path for model saving, then
        calls the respective R function for model saving (see omegaml.R). The
        saved file is then transferred to the storage's filesystem. Model loading
        works the other way around. Note that the actual R model object is not
        converted to Python, instead a uuid-like random name is used to store the
        object in R's OmegaEnv. R code can get the actual object by using the
        rmodel() helper function.

    Runtime:

        The runtime is the omegaml celery worker, started from within an R session.
        To start the worker use the cli:

        $ om runtime celery rworker

        This starts the R session and launches the celery worker using reticulate
        (see omworker.R)

    Notebooks (jobs):

        R Jupyter notebooks work the very same way as Python notebooks, except
        that they specify the R kernel. From an omega-ml perspective, there is
        no difference in starting a Jupyter notebook with any kernel.

        To initialize the omegaml session within the notebook add a first cell
        that loads omegaml into the R environment started by the R kernel:

            # first cell of notebook
            library(reticulate)
            om <- import("omegaml")
            om$runtimes$rsystem$load()

Usage:

    # R
    library(reticulate)
    om <- import("omegaml")
    om$runtimes$rsystem$load()

    # operations
    om$datasets$list()
    om$datasets$put(df, 'myname')
    df <- om$datasets$get('myname')

    etc.

See Also

    https://github.com/rstudio/reticulate
"""
from pathlib import Path

import sys

# R:reticulate injects the r helper object into the main module
# there is not much documentation on this, however a few hints
# https://rstudio.github.io/reticulate/news/index.html#reticulate-111
# https://github.com/rstudio/reticulate/issues/235#issuecomment-388150587
# https://github.com/rstudio/reticulate/blob/4967abddb35865a1be6ad839298695f1481bcade/R/python.R#L1290
# keep track whether R has already sourced omegaml helpers
R_LOAD_STATUS = {}


def rhelper(init=True):
    r_session = getattr(sys.modules['__main__'], 'r', None)
    load(r_session) if r_session and init and id(r_session) not in R_LOAD_STATUS else None
    return r_session


def load(r_session=None):
    """ load omegamlr helper methods

    This is the equivalent of a future library(omegamlr) statement.
    It loads all dependencies and functions required for omegaml R support.
    """
    r = r_session or rhelper(init=False)
    omegamlr_path = Path(__file__).parent / 'omegamlr.R'
    r.source(str(omegamlr_path))
    R_LOAD_STATUS[id(r)] = True


def start_worker(om, queue=None):
    """ start the omega runtime worker from within R env

    This starts the omega worker within a R session, ensuring
    the R helper object is initialized. This is the equivalent
    of '$ om runtime celery rworker'

    Usage:
        # omworker.R
        library(reticulate)
        om <- import("omegaml")
        om$runtimes$rsystem$start_worker(om)

    Args:
        om (Omega): the omega instance

    Returns:
        this is a blocking call, does not stop until worker is stopped
    """
    argv = 'worker --loglevel=DEBUG -E'.split(' ')
    if queue:
        argv.extend(f'-Q {queue}'.split(' '))
    om.runtime.celeryapp.worker_main(argv=argv)
