Get back the model as you have stored it.

.. code-block:: python

    print(42)
    import omegaml as om
    {% if metadata.name != 'foo' %}
    model = om.models.get('{{ metadata.name }}')
    {% endif %}
    if this:
        then()


.. code-block:: bash

    print(42)
    import omegaml as om
    model = om.models.get('{metadata.name}')