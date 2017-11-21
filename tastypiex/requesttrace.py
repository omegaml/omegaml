class ClientRequestTracer(object):

    """
    Trace api calls to a test client

    Usage:
       self.client = ClientRequestTracer(self.client)
       self.api_client = ClientRequestTracer(self.api_client)

       Limit the traces by giving parameter traces=[...] list of 
       strings 'get', 'post', 'put'

       To print requests only (no response), pass response=True

    Will print all requests made:
        Request: get, ('/api/v1/coach/itinerary/?origin=Zurich&destination=Hamburg&departure=None',), {'authentication': u'Basic dGVzdHVzZXI6dGVzdA=='}

    Optionally prints the response including headers and body

    Gist: https://gist.github.com/miraculixx/a6b0a3764d22a197493c
    """
    def __init__(self, client, traces=None, response=False):
        self.client = client
        self.__traces__ = traces or ['get', 'post', 'put']
        self.print_response = response

    def __getattribute__(self, name):
        client = object.__getattribute__(self, 'client')
        __traces__ = object.__getattribute__(self, '__traces__')
        print_response = object.__getattribute__(self, 'print_response')
        attr = object.__getattribute__(client, name)
        if name in __traces__ and hasattr(attr, '__call__'):
            def trace(*args, **kwargs):
                title = "Request: %s, %s, %s " % (name, args, kwargs)
                print title
                resp = attr(*args, **kwargs)
                if print_response:
                    print "Response:\n", resp
                    print "*" * 10
                return resp
            return trace
        return attr
