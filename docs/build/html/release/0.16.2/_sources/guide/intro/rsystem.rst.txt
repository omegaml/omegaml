Working with R
==============

.. contents::

Using omega-ml in R
-------------------

omega-ml works with R through the reticulate package, which enables R
users to have the same API and fidelity to omega-ml as in Python.

.. code:: r

    # load omegaml
    library(reticulate)
    om <- import("omegaml")

    # try a few things
    $om$datasets$list()
    $om$models$list()

    # store
    data(mtcars)
    om$datasets$put(mtcars, 'mtcars')
    => Metadata(name=mtcars,bucket=omegaml,prefix=data/,kind=pandas.dfrows,created=2022-02-23 18:21:09.250569)

    # retrieve
    om$datasets$get('mtcars')
    ...

    # create a model
    library(caret)
    model <- train(mpg ~ wt,
                   data = mtcars,
                  method = "lm")
    predict(model, mtcars)
    om$models$put('r$model', 'mtcars-model')
    om$datasets$put(mtcars, 'mtcars')

    # predict from runtime
    result <- om$runtime$model('mtcars-model')$predict('mtcars')
    result$get()

Specifics for omega-ml in R
---------------------------

While all omega-ml functionality is available to R users and in principle works
the same as in Python there a few specifics that you should be aware of.

Storing R objects as datasets
+++++++++++++++++++++++++++++

.. _reticulate's type conversion: https://rstudio.github.io/reticulate/index.html#type-conversions

The following R objects can be stored in :code:`om$datasets`. The data
conversion is done according to `reticulate's type conversion`_:

* list, vector => will be stored as Python list, dict
* matrix/array => will be stored as Python numpy arrays
* data.frame => will be stored as Python's pandas.DataFrame

Getting help
++++++++++++

To retrieve a description on any stored object, use the :code:`$help` method
on any of the stores:

.. code:: r

    cat(om$models$help('mtcars-model'))
    =>
    Python Library Documentation: RModelBackend in module omegaml.backends.rsystem.rmodels object

    class RModelBackend(omegaml.backends.basemodel.BaseModelBackend)
     |  RModelBackend(model_store=None, data_store=None, tracking=None, **kwargs)
     |
     |  Method resolution order:
     |      RModelBackend
     |      omegaml.backends.basemodel.BaseModelBackend
     |      omegaml.backends.basecommon.BackendBaseCommon
     |      builtins.object
     |
     |  Methods defined here:
     |
     |  predict(self, modelname, Xname, rName=None, pure_python=True, **kwargs)
     |      predict using data stored in Xname
     |
     |      :param modelname: the name of the model object
     |      :param Xname: the name of the X data set
     |      :param rName: the name of the result data object or None
     |      :param pure_python: if True return a python object. If False return
     |          a dataframe. Defaults to True to support any client.
     |      :param kwargs: kwargs passed to the model's predict method
     |      :return: return the predicted outcome
     |

To retrieve help on any Python object, use the :code:`om$help()` function.
This is the equivalent to reticulate's :code:`help()`, however also works
on custom objects.

.. code::

    library(reticulate)
    om <- import("omegaml")

    # enable help
    om <- om$setup()
    cat(om$help(om))
    =>
    Python Library Documentation: Omega in module omegaml.omega object

    class Omega(omegaml.store.combined.CombinedOmegaStoreMixin)
     |  Omega(defaults=None, mongo_url=None, celeryconf=None, bucket=None, **kwargs)
     |
     |  Client API to omegaml
     |
     |  Provides the following APIs:
     |
     |  * :code:`datasets` - access to datasets stored in the cluster
     |  * :code:`models` - access to models stored in the cluster
     |  * :code:`runtimes` - access to the cluster compute resources
     |  * :code:`jobs` - access to jobs stored and executed in the cluster
     |  * :code:`scripts` - access to lambda modules stored and executed in the cluster
    ...


Storing and retrieving R models
-------------------------------

R models are serialized by :code:`saveRDS` and :code:`readRDS`. To this end,
the models cannot be passed to :code:`om$models.put` directly. Instead you
must specify the R variable that holds the model:

.. code:: r

    library(caret)

    model <- train(...)
    om$models$put('r$model', 'mtcars-model')
    => Metadata(name=mtcars-model,bucket=omegaml,prefix=models/,kind=model.r,created=2021-11-23 18:40:14.055000)

Similarly, when retrieving a model, it is returned as a Python object. This
enables the Python part of omega-ml to transparently interact with the model.
To retrieve the R model itself, use the :code:`rmodel()` function:

.. code:: r

    rmodel(om$models$get('mtcars-model'))
    Linear Regression

    32 samples
     1 predictor
    ...


Using the runtime to fit R models
---------------------------------

The only method supported by fitted R models stored in omega-ml is :code:`model$predict()`.
To fit models using the omega-ml runtime, you should write a job (notebook) or
a script.


Processing large datasets
-------------------------

Using :code:`MDataFrame.transform` omega-ml can process datasets that are
larger than memory in chunks, applying a function to each chunk. In Python,
this processing can be done in parallel. In R, this can only be done in
sequence (note the :code:`n_jobs=1L`, specifying sequential processing).

.. code:: r

    mdf <- om$datasets$getl('r-dataframe')
    convert <- function(df, n) {
        df
    }

    mdf$transform(convert, n_jobs=1L)$persist('foo', store=om$datasets)


Submitting jobs in parallel
---------------------------

It is not currently supported to submit R notebooks for parallel processing
via :code:`om$runtime$job()$map()`. However, it is possible to submit
R notebooks in parallel using the runtime's :code:`parallel()`
and :code:`mapreduce()`.

Consider this example notebook, stored as 'r-parallel':

.. code:: r

    # r-parallel.ipynb
    print("hello from R")

Let's run this in parallel. The result is a list of the :code:`Metadata`
entries created for the resulting notebooks.

.. code:: r

    with(om$runtime$parallel() %as% crt, {
        crt$job('r-parallel')$run()
        crt$job('r-parallel')$run()
        crt$job('r-parallel')$run()
        result <- crt$run()
        })

    result$get()
    =>
    '<Metadata: Metadata(name=results/r-parallel_2022-02-24 17:24:15.230259.ipynb,bucket=omegaml,prefix=jobs/,kind=script.ipynb,created=2022-02-24 17:24:16.519483)>'
    '<Metadata: Metadata(name=results/r-parallel_2022-02-24 17:24:16.610554.ipynb,bucket=omegaml,prefix=jobs/,kind=script.ipynb,created=2022-02-24 17:24:17.856297)>'
    '<Metadata: Metadata(name=results/r-parallel_2022-02-24 17:24:17.933696.ipynb,bucket=omegaml,prefix=jobs/,kind=script.ipynb,created=2022-02-24 17:24:19.096552)>'

Running a worker for R models and scripts
-----------------------------------------

omega-ml workers are distributed processes that wait for commands, such as
*fit model M with data X, Y* or *predict from data X*. Once a command is
received, the worker retrieves these objects (M, X, Y) using the *Metadata*
and then executes the requested command.

To setup the omega-ml runtime for R, use the following command. This will
start an R session that runs the omega-ml worker. This works the same
as the omega-ml worker in Python, except that it is enabled to process
R models and datasets.

.. code:: bash

    $ om runtime celery rworker

In order to dedicate R and Python workers, e.g. on different VMs, specify
the worker label using the :code:`CELERY_Q` envvar. Then use
:code:`om$runtime$require()` to specify this label when issuing runtime
tasks.

.. code:: bash

    # start R worker
    $ CELERY_Q=default:R om runtime celery rworker

    # in R
    om$runtime$require('default:R')$ping()
    =>
    $message 'ping return message'$time'2022-02-24T10:46:58.642168'
    ...
