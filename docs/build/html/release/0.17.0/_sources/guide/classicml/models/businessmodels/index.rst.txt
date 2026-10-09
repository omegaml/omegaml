Adding business logic to models
===============================

Sometimes we need to add business logic to a model, for example to load feature data or to convert
the model's response to a value that is meaningful to the client application. omega-ml offers two
approaches for this use case:

* *virtual objects* - Python functions or classes marked as a :code:`virtualobj`. Virtual objects are
  useful for small functions that load data, call a model and prepare customized responses.
* *scripts* - pip-installable Python applications. This is useful for more complex processing where
  the code requires structure beyond a single function.

Business logic in virtual objects
---------------------------------

We can designate any Python function to be a virtual object by adding the
:code:`@virtualobj` decorator:

.. code:: python

    from omegaml.backends.virtualobj import virtualobj

    @virtualobj
    def mymodel(*args, data=None, **kwargs):
        ... # business logic
        return data # a json-serializable response (dict or list)

    # store the function
    om.models.put(mymodel, 'mymodel')

Alternatively we can create a sub-class to a :code:`VirtualObjectHandler`:

.. code:: python

    from omegaml.backends.virtualobj import VirtualObjectHandler

    class MyModel(VirtualObjectHandler):
        def predict(self, data=None, **kwargs):
            ... # business logic
            return data # a json-serializable response (dict or list)

    # store the class
    om.models.put(MyModel, 'mymodel')

.. note::

    It is important that the code for a virtualobj (the *#business logic* part
    in the above examples) is self contained and free of external dependencies.
    This means that all imports that the code uses should be done *within* the
    function itself, and not be imported from the environment.

    Likewise, the code must either be stored inside the `__main__` module, or
    be returned by function that you call inside of another module. For example:

    .. code:: python

        # mymodule.py
        def create_mymodel():
            @virtualobj
            def mymodel(*args, **kwargs)
                ...
                return data
            return mymodel

        om.models.put(create_mymodel(), 'mymodel')

    Alternatively we can mark the module as :code:`'__main__'` so that it
    is no longer referenced by its package name and path.

    .. code:: python

        # mymodule.py
        __name__ = '__main__' if __name__ != '__main__' else __name__

        ...

    The reason we need
    to do this is because a `virtualobj` Python function is serialized (pickled).
    If the function resides inside of a module other than `__main__`, the serialization only
    stores a reference but not the actual code. Marking the module as `__main__`
    forces serialization of the actual code.








