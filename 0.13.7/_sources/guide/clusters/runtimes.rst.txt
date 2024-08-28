The omega|ml runtime
====================

:code:`om.runtime` provides access to cloud resources:

Training a model
----------------

Training a model using a cloud cluster is straight forward:

.. code:: python

    # store some data and an unfitted model
    pd = pd.DataFrame({'x': range(100))
    reg = LinearRegression()
    om.models.put(reg, 'mymodel')

    # train the model using the cloud
    om.runtime.model('mymodel').fit('sample[x]', 'sample[y]')

The same also works from the command line:

.. code:: bash

    $ om datasets put sample.csv sample
    $ om models put mymodel.create_model mymodel
    $ om runtime model mymodel fit sample[x] sample[y]


Running grid search
-------------------

In a similar way we can run a gridsearch:

    $ om runtime model mymodel gridsearch

