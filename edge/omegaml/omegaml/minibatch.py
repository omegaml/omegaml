from omegaml import Omega
from mongoengine import Document, EmbeddedDocumentField, EmbeddedDocument
from mongoengine.fields import StringField, IntField, DateTimeField, ListField, DictField
from mongoengine.errors import NotUniqueError
import datetime
from uuid import uuid4 

STATUS_INIT = 'initialize'
STATUS_OPEN = 'open'
STATUS_CLOSED = 'closed'
STATUS_PROCESSED = 'processed'
STATUS_FAILED = 'failed'
STATUS_CHOICES = (STATUS_OPEN, STATUS_CLOSED, STATUS_FAILED)


class Buffer(Document):
    stream = StringField(required=True)
    created = DateTimeField(default=datetime.datetime.now)
    data = DictField(required=True)
    meta = {
        'db_alias': 'omega',
        'indexes': [
            'created', 
            'stream',
        ]
    }
    def __unicode__(self):
        return u"[%s] %s" % (self.created, self.data)


class Window(Document):
    stream = StringField(required=True)
    index = IntField(required=True)
    status = StringField(choices=STATUS_CHOICES)
    created = DateTimeField(default=datetime.datetime.now)
    closed = DateTimeField(default=None)
    data = ListField()
    meta = {
        'db_alias': 'omega',
        'indexes': [
            'created', # most recent is last, i.e. [-1]
            {
                'fields' : ['stream', 'index'],
                'unique' : True,
            }
            
        ]
    }
    
    @classmethod
    def create(cls, stream, index=0, seconds=None, query=None):
        if stream.windowtype == Stream.WINDOW_TIME:
            return cls.create_time_window(stream, index=index, 
                                          seconds=seconds, query=query)
        elif stream.windowtype == Stream.WINDOW_COUNT:
            return cls.create_count_window(stream, index=index, 
                                          seconds=seconds, query=query)
            
    @classmethod
    def create_time_window(cls, stream, index=0, 
                       seconds=None, query=None):
        # created  +....+....+....+....+....+...now
        #        :00   :10  :20  :30  :40  :50  :55
        #          +-------- delta = 55s ---------+
        #                                   |cutoff
        #                                    = max idx 0
        #                              |= min idx 0 
        #                             (max - interval)
        #
        # cutoff = count * interval = 50 
        # count = delta / interval = floor(55 / 10) = 5
        # interval = 10
        #
        # -- get the window to query
        from datetime import datetime, timedelta
        delta = (datetime.now() - stream.created).seconds 
        count = int(delta / stream.interval)
        cutoff = count * stream.interval
        max_index = count + index 
        max_created = stream.created + timedelta(seconds=cutoff)
        max_created += timedelta(seconds=index * stream.interval)
        min_created = max_created - timedelta(seconds=stream.interval)
        if min_created < stream.created:
            min_created = stream.created
            max_created = min_created + timedelta(seconds=stream.interval)
        try:
            _window = Window.objects(stream=stream.name, index=max_index).get()
        except Window.DoesNotExist:
            # window doesn't exist yet, create it from buffered data
            data = [ b.data for b in 
                    Buffer.objects(stream=stream.name, created__gte=min_created, 
                          created__lte=max_created).all() ]
            opts = dict(stream=stream.name, index=max_index, created=min_created,
                        data=data)
            if index < 1:
                opts.update(closed=max_created, status=STATUS_CLOSED)
            else:
                opts.update(status=STATUS_OPEN)
            _window = Window(**opts).save()
        else:
            data = [ b.data for b in 
                    Buffer.objects(stream=stream.name, created__gte=min_created, 
                          created__lte=max_created).all() ]
            if _window.status == STATUS_OPEN:
                opts=dict(data=data)
                if _window.created + timedelta(seconds=stream.interval) <= max_created:
                    opts.update(status=STATUS_CLOSED, 
                                closed=max_created)
                _window.modify({'status' : STATUS_OPEN}, **opts)
        return _window
    
    @classmethod
    def create_count_window(cls, stream, index=0, 
                       seconds=None, query=None):
        """
            created +----+----+----+----+----+---+ now
              count 0   10   20   30   40   50  55
                                             | cutoff      
                    --------------------| skip_topn 
            
            skip_topn = cutoff - windowsize
            cutoff = max_index * windowsize
            max_index=count / windowsize = floor(55/10) = 5
            windowsize=10
        """
        stream.reload()
        count = Buffer.objects(stream=stream.name).count()
        if count == 0:
            return None
        max_index = int(count / stream.windowsize) 
        cur_index = max(0, max_index + index)
        cutoff = (cur_index + 1) * stream.windowsize
        skip_topn = max(0, (cur_index - 1)) * stream.windowsize
        try:
            _window = Window.objects(stream=stream.name, index=cur_index).get()
        except:
            # window doesn't exist yet, create it from buffered data
            # we skip any documents up to the previous 
            qs = Buffer.objects(stream=stream.name)
            qs = qs.order_by('created').skip(skip_topn).limit(stream.windowsize)
            count = qs.count()
            if count > 0:
                print count, qs.all(), skip_topn, stream.windowsize
                data = [ b.data for b in qs.all() ]
                created = qs.first().created
                closed = qs.order_by('-created').first().created
            else:
                print "no data in buffer for index", locals()
                created = datetime.datetime.now()
                closed = None
                data = []
            opts = dict(stream=stream.name, index=cur_index, created=created,
                        data=data)
            if index < 1:
                opts.update(closed=closed, status=STATUS_CLOSED)
            else:
                opts.update(status=STATUS_OPEN)
            _window = Window(**opts).save()
        else:
            qs = Buffer.objects(stream=stream.name)
            qs = qs.order_by('created').skip(skip_topn).limit(stream.windowsize)
            data = [ b.data for b in qs.all() ]
            created = qs.first().created
            closed = qs.order_by('-created').first().created
            if _window.status == STATUS_OPEN:
                opts=dict(data=data)
                if len(_window.data) >= stream.windowsize:
                    opts.update(status=STATUS_CLOSED, 
                                closed=closed)
                _window.modify({'status' : STATUS_OPEN}, **opts)
        return _window
        
    def close(self):
        # critical section
        # since we update only one document we're kind of save. however
        # this should check that the 
        # not if the window was closed concurrently we don't care
        self.modify({ 'status' : STATUS_OPEN }, status=STATUS_CLOSED,
                   closed=datetime.datetime.now())
        return self
        
    
class Stream(Document):
    WINDOW_TIME = 'time'
    WINDOW_COUNT = 'count'
    WINDOW_CHOICES = (WINDOW_TIME, WINDOW_COUNT)
    
    name = StringField(default=lambda : uuid4().hex, required=True)
    status = StringField(choices=STATUS_CHOICES, default=STATUS_INIT)
    created = DateTimeField(default=datetime.datetime.now)
    closed = DateTimeField(default=None)
    windowtype = StringField(choices=WINDOW_CHOICES, 
                             default=WINDOW_TIME)
    windowsize = IntField(default=10) # interval in document counts
    interval = IntField(default=10) # interval in seconds 
    curindex = IntField(default=0) # most recent count-index
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
    def create_or_get(cls, name, **kwargs):
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
    
    def window(self, index=0, seconds=None, query=None):
        """
        returns a window into buffered data
        
        a window can be 
        
        * indexed. the currently open (incomplete) window has index 1, any previous window
        has index -i, -n < i < 1 in reverse order, the first ever received
        window is -n. The index is calculated as a function of the stream's time 
        interval or the document count, depending on the stream's window type. 
        
        * time-based. specify an arbitrary number of seconds to build a window
        since the last document of the last interval. seconds are always rounded
        to the nearest window to guarantee that time-based windows do not change
        unless a new window has been added. the stream's time interval is used to 
        determine time-based windows.
        
        * query-based. any arbitrary query. queries are executed such that they
        only operate on completed intervals.
        
        NOTE: currently only index-based is supported
        """
        return Window.create(self, index=index, seconds=seconds, query=query)
            
    

class IntegrityError(Exception):
    pass

#om.datasets.mongodb.drop_collection('stream')
#om.datasets.mongodb.drop_collection('window')

def test_stream():
    om = Omega()
    om.datasets.mongodb
    stream = Stream.create_or_get('test')
    stream.append({'foo' : 'bar1'})
    stream.append({'foo' : 'bar2'})
    print list(Buffer.objects().all())

# some receiver's receive function
def receive(stream, data):
    """
    put data on the stream
    """
    om = Omega()
    om.datasets.mongodb
    stream = Stream.create_or_get(stream)
    stream.append(data)
    
# some worker's process function
def process(window):
    # process window.data. maybe split processing in parallel... whatever
    return window.data

def producer(data):
    import os
    import time
    # sleep to simulate multiple time windows
    #time.sleep(1)
    data.update({ 'pid' : os.getpid()})
    receive('test', data)

if __name__ == '__main__':
    from multiprocessing import Pool
    from omegaml import Omega
    om = Omega()
    om.datasets.mongodb.drop_collection('buffer')
    om.datasets.mongodb.drop_collection('stream')
    om.datasets.mongodb.drop_collection('window')
    #tream = Stream.create_or_get('test', interval=1)
    stream = Stream.create_or_get('test', windowsize=10, 
                                 windowtype=Stream.WINDOW_COUNT)
    pool = Pool(4)
    data = [{ 'value' : i } for i in range(0,100)]
    pool.map(producer, data, 1)
    print stream.window()
    print stream.window(-1)
    print stream.window(-2)
    print stream.window(1)
