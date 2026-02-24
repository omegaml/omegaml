Object helpers
==============

Object helpers are user-specified Python functions that can be applied to stored objects. They
work similar to storage backends, that is an object helper is called upon storing (put), retrieving (get)
and deleting (drop) an object to and from a store. This enables user-specified behavior for specific
objects, types or kinds of objects. For example, a user may specify an object helper for a specific
model type that needs customized processing before saving and upon loading (e.g. a PyTorch model).

A basic object helper
---------------------

Here is a basic object helper. It instantiates a custom model class

.. code-block:: python

    from omegaml.backends.virtualobj import virtualobj

    @virtualobj
    def myhelper(obj=None, name=None, meta=None, method=None, **kwargs):
        if method == 'get':
            class MyModel:
                def predict(self, *args, **kwargs):
                    return 42

            return MyModel()

    om.models.put(myhelper, 'myhelper', replace=True)

Let's use this helper with the most simple object we can store - a dictionary. We store the object
as usual, specifying our `myhelper` object helper. When retrieving the model, our helper gets called
with the `method='get'` kwarg, and returns a `MyModel` instance.

.. code-block:: python

    om.models.put({}, 'mymodel', helper='myhelper', kind='python.model', replace=True)
    model = om.models.get('mymodel')
    model.predict()
    => 42


