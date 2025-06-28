Store and access models

.. code-block:: python

    import omegaml as om
    # store a model
    model_url = 'openai+http://domain:port/?model=name' # example
    om.models.put(model_url, '{{ metadata.name}}')
    # retrieve a model
    model = om.models.get('{{ metadata.name }}')

.. code-block:: bash

    # get information on the model
    $ om models metadata {{ metadata.name }}
    # predict using the runtime
    $ om runtime model {{ metadata.name }} complete [input]


.. code-block:: curl

    $ curl -X POST $OMEGA_RESTAPI_URL/api/v2/openai/chat/completions/models/{{ metadata.name }} \
           -H "Content-Type: application/json"
           -d {{'{{"messages": ... }}'}}