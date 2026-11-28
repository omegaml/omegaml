MLOps for humans
================

omega-ml is the innovative Python-native MLOps platform that provides
a scalable development and runtime environment for your AI systems. Works
from laptop to cloud or on-premises.

.. note::

    Release 0.17.0 introduces Generative AI as a first-class citizen and a new structure in this
    documentation to reflect this.

    .. collapse:: Read more

        While it has always been possible to use generative AI models with omega-ml, this release introduces a
        new set of components and APIs to match new use cases. This includes explicit support for RAG pipelines,
        a completion API that works with 3rd-party chat clients, and the ability to stream responses in the REST API.

        There are now dedicated sections for :doc:`guide/classicml/index` and :doc:`guide/genai/index`,
        which cover the respective workflows and capabilities of omega-ml. The common aspects
        are covered in :doc:`guide/pipelines/index`, :doc:`guide/clusters/index` and :doc:`guide/cli/index`.
        The :doc:`guide/advanced/index` section covers advanced topics
        that are also relevant to both classic ML and generative AI workflows.

        The top-level sections of the documentation are now better organized into :doc:`guide/index`,
        :doc:`admin/index`, :doc:`devguide/index`, :doc:`reference/index`. Overall this structure
        allows for a more focused and organized documentation experience, making it easier
        to find the information you need for your specific use case. The actual content for classic ML
        and the other sections did not change.

.. toctree::
   :maxdepth: 2

   quickstart/index
   guide/index
   admin/index
   devguide/index
   reference/index
   nb/index
   support
   changes/index
