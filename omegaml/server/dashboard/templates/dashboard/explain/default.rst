Retrieve the data or object from the omega-ml store
as shown here.

.. code-block:: python

   import omegaml as om
   # retrieve the object
   obj = om.{segment}.get('{metadata.name}')
   # store a new object
   om.{segment}.put(obj, '{metadata.name}')
