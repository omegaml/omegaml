Tensorflow
==========

Tensorflow provides several types of models

* Native tensorflow models
* Tensorflow Keras models
* Estimator models
* SavedModel

omega|ml supports all model variants as trained SavedModels. Keras models and Estimator models can also
be serialized to and trained by the cluster as Python instances. The runtime can execute arbitrary
functions that generate a model, train and save it as a SavedModel for subsequent consumption e.g. via the
model REST API.

Concepts
++++++++

Keras models
++++++++++++

.. _Modelnet: https://www.tensorflow.org/tutorials/load_data/images

Consider the following Tensorflow model (source `Modelnet`_). This is a stanard TF Keras model
that uses the MobileNetV2 for image detection and trains a new output layer.

.. code:: python

    (...)
    mobile_net = tf.keras.applications.MobileNetV2(input_shape=(192, 192, 3), include_top=False)
    mobile_net.trainable=False
    model = tf.keras.Sequential([
      mobile_net,
      tf.keras.layers.GlobalAveragePooling2D(),
      tf.keras.layers.Dense(len(label_names))])
    model.compile(optimizer='adam',
                  loss=tf.keras.losses.sparse_categorical_crossentropy,
                  metrics=["accuracy"])
    model.summary()
    model.fit(ds, epochs=1, steps_per_epoch=3)

Store the model to omega|ml as follows:

.. code:: python

    om.models.put(model, 'tfkeras-flower')

Load and use the model for prediction as follows. This runs the prediction on the local computer and
does not use omega|ml's runtime cluster.

.. code:: python

    model_ = om.models.get('tfkeras-flower')
    img = plt.imread('/path/to/image')
    result = model_.predict(np.array([img]))

Using the runtime cluster is equally straight forward:

.. code:: python

    img = plt.imread('/path/to/image')
    result = om.runtime.model('tfkeras-flower').predict(np.array([img]))

The REST API similarly provides prediction:

.. code:: python

    resp = requests.put(predict_url, json={
                'columns': ['x'],
                'data': [{'x': img.flatten().tolist()}],
                'shape': [192, 192, 3],
          })
    data = resp.json()
    prediction = data['result']

tf.data.Dataset
+++++++++++++++

Estimator models support :code:`tf.data.Dataset` by means of virtual datasets. Virtual datasets are Python
functions stored by `om.datasets`. On accessing a virtual dataset, the function is executed and the
result is returned. Thus for Estimator models, a virtual dataset should be used to return a :code:`tf.data.Dataset`.



:code:`om.datasets` supports storing :code:`tf.train.Example` records, a :code:`tf.data.Dataset` can easily be constructed
from this.






