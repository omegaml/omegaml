Tutorial for Generative AI
==========================

.. contents::
   :local:
   :depth: 2


Deploy a generative AI model
----------------------------

To register a model hosted by a third-party provider that is compatible with OpenAI's API or SDK,
use the following syntax:

.. code-block:: python

    PROVIDER_APIKEY = 'your-api-key'
    model_url = (f'openai+https://{PROVIDER_APIKEY}@openrouter.ai/api/v1'
                  ';model=google/gemini-2.0-flash-lite-preview-02-05:free')
    om.models.put(model_url, 'llm')
    =>
    <Metadata: Metadata(name=llm,bucket=omegaml,prefix=models/,kind=genai.text,created=2025-03-21 19:25:29.325000)>

This model is now available for completions:

.. code-block:: python

    model.complete('hello, who are you?')
    =>
    {'role': 'assistant',
     'content': 'Hello! I am a large language model, trained by Google.',
     'conversation_id': 'e99121a1050a463abaf2c913e99ff5ba'}

We can also serve the model for access by thid-party applications. This will start a REST API server
that can be accessed by third-party applications.

.. code-block:: bash

    $ om runtime serve
    $ !curl -X PUT http://localhost:8000/api/v1/model/llm/complete -H 'Content-Type: application/json' -d '{ "prompt": "hello"}'
    {"model": "llm", "result": {"role": "assistant", "content": "Hello there! How can I help you today? \ud83d\ude0a",
     "conversation_id": "60056750ec39433f9533e7cbf60c65cc"}, "resource_uri": "llm"}


Document storage
----------------

In support of Retrieval Augmented Generation (RAG), omega-ml provides a built-in document storage, using document
embeddings and PostgreSQL as the vector DB (with the pgvector extension). To use this we first need an embedding
model.

.. code-block:: python

    apikey = 'apikey'
    om.models.put(f'openai+https://{apikey}@api.jina.ai/v1/;model=jina-embeddings-v3',  'jina', replace=True)
    =>
    <Metadata: Metadata(name=jina,bucket=omegaml,prefix=models/,kind=genai.text,created=2025-04-03 14:33:09.643173)>

To store actual documents, we can create a document store:

.. code-block:: python

    om.datasets.put('pgvector://postgres:test@localhost:5432/postgres', 'documents',
                    embedding_model='jina', model_store=om.models, replace=True)
    =>
    <Metadata: Metadata(name=documents,bucket=omegaml,prefix=data/,kind=pgvector.conx,created=2025-04-03 14:34:23.606619)>

Now we can insert documents into the store. The documents are automatically chunked and embeddings created
using the embedding model of the store.

.. code-block:: python

    for fn in Path('/path/to/documents').glob('*.pdf'):
        om.datasets.put(fn, 'documents', model_store=om.models)

Once the documents are stored, we can query the document store. The results are returned as a
list of documents, sorted by relevance. The first document has the highest relevance score.

.. code-block:: python

    results = om.datasets.get('documents', query='hello world', top=3)
    =>
    [Document(id=1, text='Hello world! This is a test document.', score=0.9),
     Document(id=2, text='Another test document.', score=0.8),
     Document(id=3, text='Yet another test document.', score=0.7)]


Building a RAG pipeline
-----------------------

To build a RAG pipeline, we attach a document store to the model:

.. code-block:: python

    om.models.put(f'openai+https://{apikey}@api.jina.ai/v1/;model=jina-embeddings-v3',  'jina',
                  documents='documents', replace=True)

When we ask for a completion, we can add the context in the prompt as :code:`{context}`.
The context is automatically retrieved from the document store, using the prompt as the query. The
top document is used as the context.

.. code-block:: python

    model = om.models.get('llm', data_store=om.datasets)
    model = model.complete('what is the sum of the invoice? Just say SUM=<sum>. context: {context}')
    {'role': 'assistant',
     'content': 'SUM=15.00',
     'conversation_id': '024f8b43dcb74211a836a7042d067c8f'}

Adding tools
------------

Tools are functions that can be called by a model. They are used to extend the capabilities of the model
beyond text generation. For example, we can add a tool that calculates the sum of a list of numbers.

.. code-block:: python

    def sum_numbers(numbers):
        return sum((int(v) for v in numbers.split(','))) # the model passes as string

    om.models.put(sum_numbers, 'tools/sum_numbers')

    om.models.put(f'openai+https://{apikey}@openrouter.ai/api/v1;model=google/gemini-2.0-flash-exp:free',
                  'llm', documents='documents', tools=['sum_numbers'], replace=True)

    model = om.models.get('llm', data_store=om.datasets)
    model.complete('What is the sum of 7, 9, 24?')
    {'role': 'assistant',
     'content': 'The sum of 7, 9, and 24 is 40.\n',
     'conversation_id': '33738231f39047dcb886500143cebf8a',
     'intermediate_results': {'tool_calls': [{'id': 'tool_0_sum_numbers',
        'function': {'arguments': '{"numbers":"7,9,24"}', 'name': 'sum_numbers'},
        'type': 'function',
        'index': 0}],
      'tool_prompts': [{'role': 'tool',
        'tool_call_id': 'tool_0_sum_numbers',
        'content': '40'}],
      'tool_results': [{'role': 'assistant',
        'content': 40,
        'conversation_id': '33738231f39047dcb886500143cebf8a'}]}}


Adding custom pipeline actions
------------------------------

In omega-ml, a generative model is in effect a pipeline of multiple steps. For each step, the model can
call custom code to adjust the processing of each step. For example, we can add custom code that checks
the user's prompt before processing, or add guardrails to check the output of the model, and if necessary,
modify the output or return any other response.

A pipeline is a specific type of virtual function:

.. code-block:: python

    from omegaml.backends.genai.models import virtual_genai

    @virtual_genai
    def pipeline(*args, method=None, **kwargs):
        print(f"calling method={method}")
        print(f"   args={args}, kwargs={kwargs}")

    om.models.put(pipeline, 'pipeline')

Add the pipeline to the model

.. code-block:: python

    model_url = f'openai+https://{APIKEY}@openrouter.ai/api/v1;model=google/gemini-2.0-flash-exp:free'
    meta = om.models.put(model_url, 'llm', pipeline='pipeline')

When we call the model, it will call the pipeline function for each step. For every step we can
add custom code to process the input and output of the model.

.. code-block:: python

    model = om.models.get('llm', data_store=om.datasets)
    model.complete('hello world')
    =>
    calling method=template
        args=(), kwargs={'data': None, 'meta': None, 'store': None, 'tracking': None, 'prompt_message': {'role': 'user', 'content': 'hello', 'conversation_id': 'aae49e95404f4a4f99245e9237256017'}, 'messages': [{'role': 'system', 'content': 'You are a helpful assistant.', 'conversation_id': 'aae49e95404f4a4f99245e9237256017'}], 'template': 'You are a helpful assistant.', 'conversation_id': 'aae49e95404f4a4f99245e9237256017'}
    calling method=prepare
        args=(), kwargs={'data': None, 'meta': None, 'store': None, 'tracking': None, 'prompt_message': {'role': 'user', 'content': 'hello', 'conversation_id': 'aae49e95404f4a4f99245e9237256017'}, 'messages': [{'role': 'system', 'content': 'You are a helpful assistant.', 'conversation_id': 'aae49e95404f4a4f99245e9237256017'}], 'template': 'You are a helpful assistant.', 'conversation_id': 'aae49e95404f4a4f99245e9237256017'}
    calling method=process
        args=(), kwargs={'data': None, 'meta': None, 'store': None, 'tracking': None, 'response_message': {'role': 'assistant', 'content': 'Hello! How can I help you today? 😊', 'conversation_id': 'aae49e95404f4a4f99245e9237256017'}, 'prompt_message': {'role': 'user', 'content': 'hello', 'conversation_id': 'aae49e95404f4a4f99245e9237256017'}, 'messages': [{'role': 'system', 'content': 'You are a helpful assistant.', 'conversation_id': 'aae49e95404f4a4f99245e9237256017'}, {'role': 'user', 'content': 'hello', 'conversation_id': 'aae49e95404f4a4f99245e9237256017'}], 'template': 'You are a helpful assistant.', 'conversation_id': 'aae49e95404f4a4f99245e9237256017'}
    {'role': 'assistant',
     'content': 'Hello! How can I help you today? 😊',
     'conversation_id': 'aae49e95404f4a4f99245e9237256017'}

The steps of the pipeline are:

* **template** - the template is used to generate the prompt for the model. The template is
   generated from the model's metadata. This should return the template to use.

* **prepare** - the prepare step is used to prepare the input messages for the model. The input
   messages are generated from the template and the prompt message. This should return the
   list of messages to use.

* **process** - the process step is used to process the output of the model.
   This should return the final output of the model.

* **toolcall** - the toolcall step is used to process the output of a tool. The output can be
    modified by the pipeline. This should return the messages to be sent back to the model.
    Semantically this is the same as the **prepare** step.

* **toolresult** - the toolresult step is used to process the response of the model to a tools' result.
    This should return the output of the model. Semantically this is the same as the **process** step.

.. note::

    There are currently no steps for the RAG part of the pipeline. However, you can use the **prepare**
    message to process the input messages and modify the context, or add a custom context.


The function signature is the same for all steps:

.. code-block:: python

    def pipeline(*args, method=None, template=None, prompt_message=None,
                 messages=None, response_message=None, conversation_id=None, **kwargs):
        """
        Args:
            *args: positional arguments
            method (str): the name of the pipeline step
            template (str): the template to use
            prompt_message (str): the prompt message
            messages (list): the list of messages, this is in the format of the model provider,
              e.g. [{'role': 'user', 'content': 'hello world'}, ...]
            response_message (dict): the response message, this is the format of the model provider,
              e.g. {'role': 'assistant', 'content': 'hello world'}
            conversation_id (str): the conversation id
            **kwargs: keyword arguments

        Returns:
            * None: to continue the pipeline without changes
            * for method=template: the template string to use
            * for method=prepare: the list of messages to use, each message must of
                format {'role': 'user', 'content': 'hello world'}
            * for method=process: the response message to use as a dict of format
                {'role': 'assistant', 'content': 'hello world'}
            * for method=toolcall: the list of messages to use, each message must of
                format {'role': 'tool', 'content': 'hello world'}
            * for method=toolresult: the response message to use as a dict of format
                {'role': 'assistant', 'content': 'hello world'}
        """

Serving a model
---------------

To serve a model, we start the integrated REST API server and call the model using curl.

.. code-block:: bash

    $ om runtime serve
    $ curl -X PUT http://localhost:8000/api/v1/model/llm/complete -H 'Content-Type: application/json' -d '{ "prompt": "hello again!"}'


Tracking model interactions
---------------------------

To track a model's inputs and outputs, we can use the :code:`track()` method. This will
automatically capture all calls to the model via omega-ml's runtime or via the REST API.

.. code-block:: python

    exp = om.runtime.experiment('myexp')
    exp.track('llm')

This automatically tracks all input and output of the model. By using omega-ml's distributed runtime architecture,
this works the same locally as with a scaled-up distributed environment like Kubernetes.

To access the tracking data, we can

.. code-block:: python

    exp = om.runtime.experiment('myexp')
    exp.data()
    =>
    <DataFrame>


Using a third-party LLM framework
---------------------------------

In some cases the omega-ml RAG pipeline or document storage may not be sufficient for your needs.
In this case you can use any third-party framework, such as LangChain, Haystack or LlamaIndex.

For this purpose, implement a custom model as a virtualobj:

.. code-block:: python

    # define your custom pipeline
    @virtual_genai
    def mypipeline(*args, method=None, **kwargs):
        print(f"{method} args={args} kwargs={kwargs}") # trace message for testing
        import langchain
        results = ...
        return results

    # store the custom pipeline
    om.models.put(mypipeline, 'mypipeline')
    model = om.models.get('mypipeline')

This model can now be called like any other generative model. It supports the :code:`chat()`, :code:`complete()` and
:code:`embed()` methods. In this case you should provide the code of the pipeline in full. Please refer
to the documentation of the respective framework for details.

The function shall return the result as the final message to be sent back to the client. The result should be in the
same response format of your model provider, typically in OpenAI format.

.. code-block:: python

    model.chat("hello world")
    model.complete("hello world")
    model.embed("hello world")
    =>
    complete args=('foo',) kwargs={}
    chat args=('foo',) kwargs={}
    embed args=('foo',) kwargs={}