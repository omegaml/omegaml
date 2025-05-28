Concepts in omega-ml Generative AI
==================================

omega-ml's promise is to deliver complex AI workflows with minimal code. This is
achieved by providing a set of components that can be easily combined to create
powerful AI applications. The components are designed to be modular and reusable,
allowing users to mix and match according to requirements.

.. contents::
    :local:
    :depth: 1

Generative AI model
-------------------

A generative AI model is a type of AI model that can generate new content based on
a given input, also known as a prompt. In omega-ml we can define a generative model
by specifying the URL to a model provider, the model name, and the model type (embedding model,
text or multi-modal model), and give these specifications a name to store in the model
repository.

While models can be used for generation of content or responses to user input, other models
are used to create embeddings. Embeddings are numerical representations of data that can be used
to compare and retrieve similar data. For example, a text embedding model can convert
a piece of text into a numeric representation (a vector), which can then be used to find similar
pieces of text.

In omega-ml both types of models are defined in the same way, namely by specifying the URL
to a model provider, the model name, and the model type.

Model Provider
--------------

A model provider is a service that hosts and serves AI models. omega-ml
provides a transparent interface to various model providers, allowing users to easily switch
between them without changing their code. This enables users to leverage the best models
available for their specific use cases. Currently omega-ml supports the following model providers
out of the box:

*Open Source*

* vLLM - a high-performance, open-source model serving framework that supports
  multiple backends, including Hugging Face and OpenAI models. vLLM is designed for
  low-latency and high-throughput inference, making it ideal for real-time applications.

* LocalAI - a local model serving framework that allows users to run models on their own
  hardware. LocalAI is designed for users who want to have full control over their
  models and data, and it supports a wide range of models, including those from
  Hugging Face and OpenAI.

* AnythingLLM - a local model serving framework that allows users to run models on their own
  hardware. AnythingLLM is designed for users who want to have full control over their
  models and data, and it supports a wide range of models, including those from
  Hugging Face and OpenAI.

* GPT4All - a local model serving framework that allows users to run models on their own
  hardware. GPT4All is designed for users who want to have full control over their
  models and data, and it supports a wide range of models, including those from
  Hugging Face and OpenAI.

*Commercial*

* OpenAI - a commercial model provider that offers a wide range of models for various
  tasks, including text generation, image generation, and more. OpenAI is known for its
  high-quality models and ease of use.

* OpenRouter - a commercial model provider that offers a wide range of models for various
  tasks, including text generation, image generation, and more. OpenRouter is known for
  its high-quality models and ease of use.

* Infomaniak - a Swiss commercial model provider that offers a wide range of models for various
  tasks, including text generation, image generation, and more. Infomaniak is known for
  its high-quality models and ease of use with Swiss Hosting.

* Any provider offering a OpenAI-compatible set of APIs, specifically /completions,
  /chat/completions and /embeddings.

Pipelines and Guardrails
------------------------

Every generative AI model in omega-ml is part of a pipeline, a sequence of steps
that are executed in order to process some part of the completion process. For example, the
steps include prompt preprocessing, model inference, and postprocessing. Each step in the pipeline
can adjust the input to the model, how the model is called, and process or modify the output
after inference.

A pipeline in omega-ml is simply a callable object attached to a model, that takes inputs and
returns an output. For example, the pipeline implement guardrails (content or security checks)
by checking the input and output to the model, and modifying it if necessary.

Documents storage
-----------------

Document storage is a key component of generative AI workflows, as it allows users to
store and retrieve documents which provide additional context to a model when completing a
user's input. Similarly to other transparent data access in omega-ml, we can define a
a document storage by providing the URL to a supported database, and storing this definition
in the dataset repository.

For a document storage to be useful, we also need an embedding model, which is a type of
a generative AI model that can convert documents into embeddings. These embeddings are then
stored in the document storage, allowing for efficient retrieval and comparison of documents.

Conversation history
--------------------

Conversation history is a key component of generative AI workflows, as it allows users
to store and retrieve the history of a conversation with a model. This is useful for
maintaining context and providing a more coherent experience for the user.

In omega-ml, conversation history is automatically stored in its database, and and can be
retrieved and used to inform the model's responses. This is particularly useful for chatbots and other
conversational agents, where maintaining context is crucial for providing relevant responses
across a longer conversation.

Tools
-----

Tools are a key component of generative AI workflows, as they allow users to extend the
functionality of their models and pipelines. A tool is some external functionality that
can be provided to a model, such as a database lookup, a custom function to calculate
a result, or a call to an external API. Tools can be used to augment the capabilities of a model,
whereby the model can call the tool to perform some action, and then use the result of that action
to inform its response to the user.

In omega-ml, tools are defined as a callable object that can be attached to a model and can
be called by the model during inference. Tool calls are processed as part of the pipeline in
order to modify the input to the tool, replace the tool call, or modify its output.

Generative AI runtime and REST services
---------------------------------------

omegaml provides a customizable runtime to meet the specific resource and distribution
requirements of generative AI models. For example, in a corporate environment the runtime
can be configured to use a local model provider, such as vLLM or LocalAI, to ensure that
data is not sent to a third-party provider. The runtime can also be configured to use
autoscaling for scalability and high availability, and to automatically distribute
inference requests across multiple nodes.

Multi-model Repository
----------------------

It is often useful to configure multiple models, templates and pipelines to implement
different use case scenarios. For example, one generative AI model can be configured to
answer questions about a company's products, while another model can be configured to
provide guidances on human resources policies.

In omega-ml we can define multiple models, templates and pipelines in a single repository,
and then use these models in different workflows. This allows users to easily switch
between different models and pipelines, and to reuse them in different workflows.

Monitoring
----------

omega-ml provides a built-in model tracking and monitoring system. This works the same
way for all models, including generative AI models. The tracking system automatically logs
all interactions with a model, including the input, output, and any metadata associated with the
interaction. All interactions are stored to the model repository for later query and analysis.

