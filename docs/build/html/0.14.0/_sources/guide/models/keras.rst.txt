Keras
=====

The Keras backend implements the `.fit()` method with the following Keras-specific extensions:

* :code:`validation_data=` can refer to a tuple of (testX, testY) dataset names instead of actual
  data values, similar to X, Y. This will load the validation dataset before :code:`model.fit()`.

* :code:`Metadata.attributes.history` stores the history.history object, which is a dictionary
  of all metrics with one entry per epoch as the return value of Keras's model.fit() method.


