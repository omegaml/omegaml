Introduction
------------

omega|ml supports data streaming from various sources, including

* Python
* Kafka
* MQTT
* omega|ml native datasets

A streaming application, in general, consists of three components:

* one or more producers
* a streaming log
* one or more consumers

The streaming log should be capable of producing windows of data to process
so that continous processing of the data is possible. This is contrast to batch
processing where we wait until all of the data has arrived and then gets processed
at once. In a streaming system, producers and consumers act independently and
they can be active at different times.

Creating a stream
-----------------

Streams in omega|ml are based on minibatch. minibatch streams are created
at first access time:

.. code::

    stream = om.streams.get('mystream')
    stream.append(data)

Once we have created a stream, similar to a dataset, there is a Metadata entry:

.. code::

    om.streams.metadata('mystream')
    <Metadata: Metadata(name=mystream,bucket=omegaml,prefix=streams/,kind=stream.minibatch,created=2020-09-17 15:46:47.217000)>


Writing to a stream
-------------------

We can write to a stream either by using `om.streams.put()` or by directly appending to
the stream using `stream.append()`. Technically both ways are valid, using `stream.append`,
avoids the overhead of getting the stream from metadata first.

.. code::

    data = {
       'foo': 'bar',
    }
    om.streams.put(data, 'mystream')

    # technically equivalent, use for less overhead in higher frequency scenarios
    stream = om.streams.get('mystream')
    stream.append(data)

Accessing a stream buffer
-------------------------

We can also check the streams' buffer:

.. code::

    stream = om.streams.get('mystream')
    stream.buffer()
    => [<Buffer: Buffer created=[2020-09-17 15:52:33.193000] processed=False data={'foo': 'bar'}>]

Note items in the buffer have not been processed yet, as indicated by the processed flag. That is,
a producer has written data to the buffer, but no consumer has yet seen the data.

Consuming streaming data
------------------------

omega|ml supports streaming in mini batches, called Windows. Each window is
some subset of the data in a streams buffer. Windows are produced by an emitter strategy.
There are several emitter strategies provided out of the box, and custom stratagies can be
created if needed.

* CountWindow - an emitter that batches N buffered items, where N is any integer
* FixedTimeWindow - an emitter that batches data in fixed, absolute intervals
* RelaxedTimeWindow - an emitter that batches data in relative intervals

Emitters are created by getting a stream in lazy mode. This returns a streaming
function that continuously processes windows in batches, given by the emitter
strategy, and forwards each window to a callable provided by the user.

.. code::

    # using the CountWindow strategy, with one item per window
    streaming = om.streams.get('mystream', lazy=True)
    streaming.apply(lambda window: print(window)

    # using the CountWindow strategy, with size=N items per window
    streaming = om.streams.get('mystream', lazy=True, size=5)
    streaming.apply(lambda window: print(window)

    # using the FixedTimeWindow strategy, with absolute intervals of 2 seconds
    streaming = om.streams.get('mystream', lazy=True, interval=2)
    streaming.apply(lambda window: print(window)

    # using the RelaxedTimeWindow strategy, with relativbe intervals of 2 seconds
    streaming = om.streams.get('mystream', lazy=True, interval=2, relaxed=True)
    streaming.apply(lambda window: print(window)


Writing streaming apps
----------------------

Streaming apps require a continuously running consumer in order to be useful,
or at least a consumer that runs as frequently as the emitter strategy needs.

With omega|ml we can create a streaming application as follows:

.. code:: python

    # consumer.py
    import omegaml as om

    streaming = om.streams.get('mystream', lazy=True)

    @streaming
    def consumer(window):
        print(window)


    # producer
    import omegaml as om

    stream = om.streams.get('mystream')
    data = {
       'foo': 'bar'
    }
    stream.append(data)


When we run the producer and the consumer we get the following output:

.. code:: bash

    # shell 2, run this 3 times
    $ python producer.py

    # shell 1
    $ python consumer.py
    Window [2020-09-17 16:15:37.687509] [{'foo': 'bar'}]
    Window [2020-09-17 16:15:40.974479] [{'foo': 'bar'}]
    Window [2020-09-17 16:15:43.678020] [{'foo': 'bar'}]

Note that producer and consumer are not required to run on the same machine.
Since they are connected through the streaming log provided by omega|ml, they
just need to use the same stream name in order connect.

Deploying streaming apps
------------------------

omega|ml core does not yet provide an integrated streaming runtime. However,
there are several options:

1. omega|ml enterprise provides the apphub component, which supports streaming
   applications out of the box

    .. code:: bash

        # deploy the myconsumer script package to apphub
        $ om scripts put myconsumer apps/myconsumer

        # access at http://hub.omegaml.io/apps/<user>/myconsumer

2. run inside a jupyter notebook session

3. run as a scheduled job and use a non-blocking streaming function

   .. code::

      streaming = om.streams.get('mystream', lazy=True, blocking=False)
      # get only one window
      streaming.apply(consumer)

4. any python application can be any consumer or producer as long
   as it is connected to an omega|ml server


.. note::

    Future releases will include a streaming worker built into the omega|ml
    native runtime. The syntax will be something like this:

    .. code::

        # this will start the streaming consumer on the runtime
        om.streams.put(streaming_function, 'myconsumer')



















