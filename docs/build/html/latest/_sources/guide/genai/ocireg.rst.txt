Model deployment using OCI repositories
=======================================

.. versionadded:: 0.18.0

An OCI repository is a remote service that stores large data and software artifacts, also known
as (docker) images. They are typically known and used to deploy containerized software, however
have evolved to store arbitrary artifacts.

omega-ml provides the `OCIRegistryBackend` plugin to use OCI registries as an alternative artifact
storage for AI models. By default, omega-ml stores all models in its analytics database by using
MongoDB's gridfile system. While gridfile is built to store artifacts of arbitrary size, storing
very large artifacts of multiple GB in size, like generative AI models, is not a good use of MongoDB.

The `OCIRegistryBackend` plugin allows us to use an OCI registry instead of gridfile. This provides
an efficient and transparent way deploy generative AI models of any size, whether they are custom made
or provided as a pre-trained model by some third party.

Preparing an OCI repository
---------------------------

To use an OCI registry we first add it the `om.models` store:

.. code-block:: python

    om.models.put('oci://ghcr.io/userid', 'ocireg')

Saving a model
--------------

To save a model to the registry specify the registry by its name, as the `repo=` kwarg.
This creates a new image in the registry, named as the model, and remembers its name
in the stored object's Metadata.

.. code-block:: python

    model = ... # some supported model
    om.models.put(model, 'mymodel', repo='ocireg')

Loading a model
---------------

Loading a model from a registry works the same as with any other model. The name of the
OCI repository is inferred from the object's Metadata.

.. code-block:: python

    model = om.models.get('mymodel')
    model.generate(...)