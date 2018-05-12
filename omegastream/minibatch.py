import datetime
from uuid import uuid4

from mongoengine import Document
from mongoengine.errors import NotUniqueError
from mongoengine.fields import StringField, IntField, DateTimeField, ListField, DictField, BooleanField

STATUS_INIT = 'initialize'
STATUS_OPEN = 'open'
STATUS_CLOSED = 'closed'
STATUS_PROCESSED = 'processed'
STATUS_FAILED = 'failed'
STATUS_CHOICES = (STATUS_OPEN, STATUS_CLOSED, STATUS_FAILED)


class Window(Document):
    """
    A Window is the data collected from a stream according
    to the WindowEmitter strategy.
    """
    stream = StringField(required=True)
    created = DateTimeField(default=datetime.datetime.now)
    data = ListField(default=[])
    processed = BooleanField(default=False)
    meta = {
        'db_alias': 'omega',
        'indexes': [
            'created', 
            'stream',
        ]
    }
    def __unicode__(self):
        return u"Window [%s] %s" % (self.created, self.data)

class Buffer(Document):
    stream = StringField(required=True)
    created = DateTimeField(default=datetime.datetime.now)
    data = DictField(required=True)
    processed = BooleanField(default=False)
    meta = {
        'db_alias': 'omega',
        'indexes': [
            'created', 
            'stream',
        ]
    }
    def __unicode__(self):
        return u"Buffer [%s] %s" % (self.created, self.data)
      
    
class Stream(Document):
    """
    Stream provides meta data for a streaming buffer

    Streams are synchronized among multiple Stream clients using last_read.
    """
    name = StringField(default=lambda : uuid4().hex, required=True)
    status = StringField(choices=STATUS_CHOICES, default=STATUS_INIT)
    created = DateTimeField(default=datetime.datetime.now)
    closed = DateTimeField(default=None)
    interval = IntField(default=10) # interval in seconds or count in #documents
    last_read = DateTimeField(default=datetime.datetime.now)
    meta = {
        'db_alias': 'omega',
        'indexes': [
            'created', # most recent is last, i.e. [-1]
            { 'fields' : ['name'],
              'unique' : True
            }
        ]
    }
    
    def ensure_initialized(self):
        if self.status == STATUS_INIT:
            self.modify({ 'status' : STATUS_INIT },
                       status=STATUS_OPEN)
    
    def append(self, data):
        """
        non-blocking append to stream buffer
        """
        self.ensure_initialized()
        doc = Buffer(stream=self.name,
               data=data).save()
        
    
    @classmethod
    def get_or_create(cls, name, **kwargs):
        # critical section
        # this may fail in concurrency situations
        try:
            stream = Stream.objects(name=name).no_cache().get()
        except Stream.DoesNotExist:
            pass
        try:
            stream = Stream(name=name or uuid4().hex,
                            status=STATUS_OPEN,
                            **kwargs).save()
        except NotUniqueError:
            stream = Stream.objects(name=name).no_cache().get()
        return stream
    
    
class WindowEmitter(object):
    """
    a window into a stream of buffered objects
    
    WindowEmitter.run() implements the generic emitter protocol as follows:
    
    1. determine if a window is ready to be processed
    2. retrieve the data from the buffer to create a Window
    3. process the data (i.e. mark the buffered data processed)
    4. run the emit function on the window
    
    Note that run() is blocking. Between running the protocol,
    it will sleep to conserve resources.
    
    Each time run() wakes up, it will call the following methods in turn:
        
        window_ready() - called to determine if the buffer contains enough
                         data for a window. 
        query()        - return the Buffer objects to process 
        process()      - process the data
        timestamp()    - timestamp the stream for the next processing
        commit()       - commit processed data back to the buffer. by
                         default this means removing the objects from the
                         buffer and deleting the window.
        sleep()        - sleep until the next round
        
    Use timestamp() to mark the stream (or the buffer data) for the next
    round. Use sleep() to set the amount of time to sleep. Depending on 
    the emitter's semantics this may be a e.g. a fixed interval or some function
    of the data.
        
    WindowEmitter implements several defaults:
    
        process() - mark all data returned by query() as processed
        sleep()   - sleep self.interval / 2 seconds
        undo()    - called if the emit function raises an exception. marks
                    the data returned by query() as not processed and deletes
                    the window 
        
    For examples of how to implement a custom emitter see TimeWindow, CountWindow 
    and SampleFunctionWindow.
    
    Note there should only be one WindowEmitter per stream. This is a
    a limitation of the Buffer's way of marking documentes as processed (a boolean
    flag). This decision was made in favor of performance and simplicity.  Supporting
    concurrent emitters would mean each Buffer object needs to keep track of which
    emitter has processed its data and make sure Window objects are processed by
    exactly one emitter. 
    """
    def __init__(self, stream, interval=None, processfn=None, emitfn=None,
                emit_empty=False):
        self.stream_name = stream
        self.interval = interval
        self.emit_empty = emit_empty
        self.emitfn = emitfn
        self.processfn = processfn
        self._stream = None
        self._window = None # current window if any
        self._delete_on_commit = True
        
    def query(self, *args):
        raise NotImplemented()
        
    def window_ready(self):
        """ return a tuple of (ready, qargs) """
        raise NotImplemented()
        
    def timestamp(self, query_args):
        self.stream.modify(query={}, last_read=datetime.datetime.now())
        
    @property
    def stream(self):
        if self._stream:
            return self._stream
        self._stream = Stream.get_or_create(self.stream_name)
        return self._stream
        
    def process(self, qs):
        if self.processfn:
            return self.processfn(qs)
        data = []
        for obj in qs:
            obj.modify(processed=True)
            data.append(obj)
        return data
        
    def undo(self, qs):
        for obj in qs:
            obj.modify(processed=False)
        if self._window:
            self._window.delete()
        return qs
    
    def persist(self, flag=True):
        self._delete_on_commit = not flag
    
    def commit(self, qs, window):
        if not self._delete_on_commit:
            window.modify(processed=True)
            return
        for obj in qs:
            obj.delete()
        window.delete()
    
    def emit(self, qs):
        self._window = Window(stream=self.stream.name, 
                              data=[obj.data for obj in qs]).save()
        if self.emitfn:
            self._window = self.emitfn(self._window) 
        return self._window
    
    def sleep(self):
        import time
        time.sleep((self.interval or stream.interval) / 2.0)
        
    def run(self):
        while True:
            ready, query_args = self.window_ready()
            if ready:
                qs = self.query(*query_args)
                qs = self.process(qs)
                if qs or self.emit_empty:
                    try:
                        window = self.emit(qs)
                    except Exception as e:
                        self.undo(qs)
                        print(str(e))
                    else:
                        self.commit(qs, window)
                    finally:
                        self.timestamp(*query_args)

            self.sleep()
                
        
class FixedTimeWindow(WindowEmitter):
    """
    a fixed time-interval window
    
    Yields windows of all data retrieved in fixed intervals of n
    seconds. Note that windows are created in fixed-block sequences,
    i.e. in steps of n_seconds since the start of the stream. Empty
    windows are also emitted. This guarantees that any window 
    contains only those documents received in that particular window.
    This is useful if you want to count e.g. the number of events
    per time-period.
    
    Usage:
    
        @stream(name, interval=n_seconds)
        def myproc(window):
            # ...
    """
    def __init__(self, *args, **kwargs):
        super(FixedTimeWindow, self).__init__(*args, **kwargs)
        self.emit_empty = True

    def window_ready(self):
        stream = self.stream
        last_read = stream.last_read
        now = datetime.datetime.now()
        max_read =  last_read + datetime.timedelta(seconds=self.interval)
        return now > max_read, (last_read, max_read)
    
    def query(self, *args):
        last_read, max_read = args
        fltkwargs = dict(created__gte=last_read, created__lte=max_read)
        return Buffer.objects.no_cache().filter(**fltkwargs)
    
    def timestamp(self, *args):
        last_read, max_read = args
        self.stream.modify(query=dict(last_read__gte=last_read), last_read=max_read)
        self.stream.reload()

        
    def sleep(self):
        import time
        # we have strict time windows, only sleep if we are up to date
        if self.stream.last_read > datetime.datetime.now() - datetime.timedelta(seconds=self.interval):
            # sleep slightly longer to make sure the interval is complete
            # and all data had a chance to accumulate. if we don't do
            # this we might get empty windows on accident, resulting in
            # lost data
            time.sleep(self.interval + 0.25)
        

class RelaxedTimeWindow(WindowEmitter):
    """
    a relaxed time-interval window
    
    Every interval n_seconds, yields windows of all data in the buffer
    since the last successful retrieval of data. This does _not_
    guarantee the data retrieved is in a specific time range. This is
    useful if you want to retrieve data every n_seconds but do not
    care when the data was inserted into the buffer.
    
    Usage:
    
        @stream(name, interval=n_seconds)
        def myproc(window):
            # ...
    """
    def window_ready(self):
        stream = self.stream
        last_read = stream.last_read
        max_read = datetime.datetime.now()
        return True, (last_read, max_read)
    
    def query(self, *args):
        last_read, max_read = args
        fltkwargs = dict(created__gt=last_read, created__lte=max_read,
                         processed=False)
        return Buffer.objects.no_cache().filter(**fltkwargs)
    
    def timestamp(self, *args):
        last_read, max_read = args
        self.stream.modify(query=dict(last_read=last_read), last_read=max_read)
        self.stream.reload()
        
        
class CountWindow(WindowEmitter):
    def window_ready(self):
        qs = Buffer.objects.no_cache().filter(processed=False).limit(self.interval)
        self._data = list(qs)
        return len(self._data) >= self.interval, ()
        
    def query(self, *args):
        return self._data
        
    def timestamp(self, *args):
        self.stream.modify(query={}, last_read=datetime.datetime.now())
        
    def sleep(self):
        import time
        time.sleep(0.1)
        
        
class SampleFunctionWindow(WindowEmitter):
    def window_ready(self):
        qs = Buffer.objects.no_cache().filter(processed=False)
        data = []
        for obj in sorted(qs, key=lambda obj : obj.data['value']):
            if obj.data['value'] % 2 == 0:
                data.append(obj)
                if len(data) >= self.interval:
                    break
        self._data = data
        return len(self._data) == self.interval, ()
        
    def query(self, *args):
        return self._data
        
    def timestamp(self, *args):
        self.stream.modify(last_read=datetime.datetime.now())
        
    def sleep(self):
        import time
        time.sleep(0.5)
    
def stream(name, interval=None, size=None, emitter=None, 
           relaxed=True, keep=False, **kwargs):
    """
    make and call a streaming function
    
    Usage:
        # fixed-size stream
        @stream(size=n)
        def myproc(window):
            # process window.data
        
        # time-based stream
        @stream(interval=seconds)
        def myproc(window):
            # process window.data
            
        # arbitrary WindowEmitter subclass
        @stream(emitter=MyWindowEmitter):
        def myproc(window):
            # process window.data
            
    If interval is given, a RelaxedTimeWindow into the stream is created. A 
    RelaxedTimeWindow will call the decorated function with a window of data 
    since the last time it did so. To get a FixedTimeWindow, specify 
    relaxed=False.
    
    If size is given, a CountWindow into the stream is created. A CountWindow
    will call the decorated function with a window of exactly #size of 
    objects in data. 
    
    If a WindowEmitter subclass is given, an instance of that emitter is created
    and passed any optional kwargs and it's run() method is called. This emitter 
    may process the buffered data in any arbitrary way it chooses.
        
    :param name: the stream name
    :param interval: interval in seconds
    :param size: interval in count of buffered, unprocessed objects in stream
    :param keep: optional, keep Buffer and Stream data. defaults to False
    :param relaxed: optional, defaults to True. chooses between Relaxed and
    FixedTimeWindow
    :param emitter: optional, a WindowEmitter subclass (advanced)
    """
    def inner(fn):
        fn._count = 0
        stream = Stream.get_or_create(name, interval=interval or size)
        if interval and emitter is None:
            if relaxed:
                em = RelaxedTimeWindow(name, emitfn=fn, interval=interval)
            else:
                em = FixedTimeWindow(name, emitfn=fn, interval=interval)
        elif size and emitter is None:
            em = CountWindow(name, emitfn=fn, interval=size)
        elif emitter is not None:
            em = emitter(name, emitfn=fn, 
                         interval=interval or size, 
                         **kwargs)
        else:
            raise ValueError("need either interval=, size= or emitter=")
        em.persist(keep)
        em.run()
    return inner
    
class IntegrityError(Exception):
    pass

# some worker's process function
def consumer():
    # process window.data. maybe split processing in parallel... whatever
    #@stream('test', size=2, emitter=SampleFunctionWindow)
    #@stream('test', interval=5)
    #@stream('test', interval=5, relaxed=False, keep=True)
    @stream('test', size=200, keep=True)
    def myprocess(window):
        try:
            om = Omega()
            db = om.datasets.mongodb
            db.processed.insert_one({ 'data' : window.data or {}})
        except Exception as e:
            print(e)
        return window

# some receive function, attach to whatever queue the
# data is coming in through
def receive(stream, data):
    """
    put data on the stream
    """
    om = Omega()
    om.datasets.mongodb
    stream = Stream.get_or_create(stream)
    stream.append(data)

# some producer
def producer(data):
    import os
    import time
    import random
    # sleep to simulate multiple time windows
    time.sleep(random.randrange(0,1,1) / 10.0)
    data.update({ 'pid' : os.getpid()})
    receive('test', data)

if __name__ == '__main__':
    from multiprocessing import Pool, Process
    from omegaml import Omega
    import time
    om = Omega()
    om.datasets.mongodb.drop_collection('buffer')
    om.datasets.mongodb.drop_collection('stream')
    om.datasets.mongodb.drop_collection('window')
    om.datasets.mongodb.drop_collection('processed')
    #tream = Stream.get_or_create('test', interval=1)
    #stream = Stream.get_or_create('test', interval=1, 
    #                             windowtype=Stream.WINDOW_COUNT)
    emitp = Process(target=consumer)
    emitp.start()
    pool = Pool(4)
    data = [{ 'value' : i } for i in range(0,1000)]
    pool.map(producer, data, 1)
    time.sleep(5)
    emitp.terminate()
    print(list(doc for doc in om.datasets.mongodb.processed.find()))
    
