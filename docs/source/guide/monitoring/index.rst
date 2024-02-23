Monitoring
==========

omega-ml provides an extensible monitoring and alerting system, built
on top of its tracking facility.

Enable model monitoring
-----------------------

To enable model monitoring

.. code-block:: python

    exp = om.runtime.experiment('myexp')
    exp.track('mymodel', monitor=True)

