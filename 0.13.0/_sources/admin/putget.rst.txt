Interface with omega|ml to get/put models and objects
=====================================================

The below snippet displays how omega|ml can be used to store and retrieve
models and objects.

::

    from omegaml import Omega
    om = Omega()
    x = np.array(range(10, 20))
    y = x * 2
    df = pd.DataFrame(dict(x=x, y=y))

    # store dataset object
    om.datasets.put(X, 'datax')
    om.datasets.put(Y, 'datay')

    # fit locally and store model for comparison
    lr = LinearRegression()
    lr.fit(X, Y)
    pred = lr.predict(X)
    # store the fitted model
    om.models.put(lr, 'duplicate')

    # for spark models
    # create and store spark KMeans model
    # for the below to work
    # 'pyspark.mllib.clustering.KMeans' must be a working model provided by spark
    # further required parameters can be sent to the model for processing using params
    om.models.put('pyspark.mllib.clustering.KMeans', 'sparktest', params=dict(k=10))

    # retrieve dataset
    datax = om.datasets.get('datax')
