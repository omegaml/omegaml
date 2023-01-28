Store and access models

.. code-block:: python

    import omegaml as om
    # store a model
    reg = LinearRegression() # example
    om.models.put(reg, '{{ metadata.name}}')
    # retrieve a model
    model = om.models.get('{{ metadata.name }}')

.. code-block:: bash

    # get information on the model
    $ om models metadata {{ metadata.name }}
    # predict using the runtime
    $ om runtime model {{ metadata.name }} predict [input]


.. code-block:: curl

    $ curl -X POST $OMEGA_RESTAPI_URL/api/v1/models/{{ metadata.name }}/predict \
           -H "Content-Type: application/json"
           -d {{'{{"input": "data"}}'}}