
from django.conf import settings
from django.conf.urls import url, include
from django.shortcuts import render
from docutils.core import publish_parts

from tastypiex.modresource import add_resource_mixins,\
    override_resource_meta
from tastypiex.util import load_api


class ApiCentralView(object):

    def __init__(self, apis, template=None):
        self.apis = apis
        self.template = template or 'tastypiex/apihome.html'

    def docview(self, request, *args, **kwargs):
        context = {
            'request': request,
            'apis': self.apis,
        }
        return render(request, self.template, context)

    def as_view(self):
        def view(request, *args, **kwargs):
            return self.docview(request, *args, **kwargs)
        return view


class ApiCentralizer(object):

    """
    use this to centralize tastypie APIs authorization and authentication
    handling

    Using ApiCentralizer, existing Api instances can be monkey patched
    from a central configuration:

    * change Meta attributes for all resources of an API or a specific resource
    * add mixin classes to all resources or a specific resource
    * all of the above can be done dynamically at run-time (except changing
      urls)

    ApiCentralizer provides the .urls property to load urls for apis for 
    only applications that are in INSTALLED_APPS. This is useful e.g.
    if you have multiple deployments with different installed applications.

    * add apis & swagger documentation for many urls in just one command
    * use settings.py to specify which APIs get loaded into urlpatterns
    * automatically add swagger ui URLs if django-tastypie-swagger is installed

    If django-tastypie-swagger is installed, ApiCentralizer.urls will 
    automatically build the required urls such that each Api gets its own
    swagger ui instance. 

    Why?

        usually tastypie APIs are configured using their Meta class attributes.
        This is ok if you control the APIs and have access to source code. If
        you use an API provided by a library, you are left, however, with the
        options given by that API without much control to change Meta attributes.

    Usage:
        # directly apply to apis
        class YourMeta:
              authorization = SomeAuthorization()
        ApiCentralizer(apis=(api1, api2), mixins=(...), meta=YourMeta)
        => all resources in the given apis will now have YourMeta's authorization

        # settings.py
        API_CONFIG = {
           'apis' : (
               ('app1', 'app1.api.v1_api'),
               ('app2', 'app2.api.v2_api'),
           ),
        }
        # either variant
        ApiCentralizer(mixins=(...), meta=YourMeta)
        ApiCentralizer(API_CONFIG['apis'], mixins=(...), meta=YourMeta)
        => only centralize APIs if the given app is in INSTALLED_APPS

        # dynamic use, e.g. in a view
        centralizer = ApiCentralizer(autoinit=False)
        centralizer.centralize([api1, api2], mixins=(...), meta=YourMeta)
        centralizer.centralize_resource('path.to.api.resource', meta=...)

        # add all API urls in one go, see .urls property for specifics
        # this includes swagger ui at path/doc/<api_name>/ if swagger ui is
        # installed
        urlpatterns += patterns('', *ApiCentralizer(path=r'api/').urls)

        # load swagger ui URLs on a different path
        urlpatterns += patterns('', *ApiCentralizer(path=r'api/', swaggerui=False).urls)
        urlpatterns += patterns('', *ApiCentralizer(swaggerui=False).get_swagger_urls(path))
    """
    def __init__(self, config=None, apis=None, mixins=None, meta=None,
                 path=None, swaggerui=False, autoinit=True, docstyle='markdown'):
        self.config = config or []
        self.apis = apis or self.get_apis(self.config)
        self.path = path or r'^api/'
        self.swaggerui = swaggerui or 'tastypie_swagger' in settings.INSTALLED_APPS
        self.docstyle = docstyle
        if autoinit:
            self.centralize(self.apis, mixins=mixins, meta=meta)

    def centralize(self, apis, mixins=None, meta=None):
        """ centralize all resources in an Api """
        for api in apis:
            # if a string is given, load
            if isinstance(api, basestring):
                api = load_api(api)
            for resource in api._registry.values():
                self.centralize_resource(resource, mixins=mixins, meta=meta)
                self.process_doc_markup(resource, kind=self.docstyle)

    def centralize_resource(self, resource, mixins=None, meta=None):
        """override Meta attributes in a Resource or add mixins"""
        if isinstance(resource, basestring):
            # load resource if given as a string path.to.api.resource
            parts = resource.split('.')
            apipath, api_name = '.'.join(parts[0:-1]), parts[-1]
            api = load_api(apipath)
            resource = api._registry[api_name]
        if meta:
            override_resource_meta(resource, meta)
        if mixins:
            add_resource_mixins(resource, *mixins)

    def process_doc_markup(self, resource, kind='markdown'):
        """ convert __doc__ string of resource to html

        will update resource.__doc__ with converted text. this is
        so you can use markdown or reST in line with your documentation
        setup, e.g. sphinx. 

        :param kind: markdown|rest, defaults to markdown
        """
        if not resource.__doc__:
            return
        # remove whitespace to get the parsers to work
        doc = '\n'.join([line.strip()
                         for line in resource.__doc__.split('\n')])
        try:
            from markdown import markdown
            if kind == 'markdown':
                doc = markdown(doc)
            elif kind == 'rest':
                doc = publish_parts(doc).get('html_body', doc)
        except:
            # we simply ignore errors
            pass
        else:
            resource.__doc__ = doc

    @property
    def urls(self):
        """
        return all urls to add in urlpatterns

        # settings.py
        API_CONFIG = {
           'apis' : (
              ('app1', 'app1.api.v1_api'),
              ('app2', 'app2.api.v1_api'),
           )
        }
        # urls.py
        urlpatterns += patterns('', *ApiCentralizer().urls)
        => adds all api urls of apps in INSTALLED_APPS 
        """
        return self.get_urls(self.path)

    def get_urls(self, path):
        """
        same as .urls property, use to specify path dynamically
        details see url

        :param path: the regexp in url(regexp, ...) 
        """
        assert self.apis, "ApiCentralizer: no apis known. Did you specify autoinit=True?"
        urls = []
        for api in self.apis:
            if isinstance(api, basestring):
                api = load_api(api)
            urls.append(url(path, include(api.urls)))
        if self.swaggerui:
            docpath = (r'%s/doc/' % self.path).replace('//', '/')
            # add per-api swagger ui
            urls.extend(self.get_swagger_urls(docpath))
            # add main docview with links to per-api swagger ui
            urls.append(url(docpath + '$', self.get_docview()))
        return urls

    def get_swagger_urls(self, path, apis=None):
        """
        generate per-api swagger ui urls for all apis

        :param path: the regex path to use. will be appended with
        api.api_name unless the string contains the {api_name} placeholder
        :param apis: a list of apis as a string or tuple of Api instances. If
        passed as a string as path.to.module.api the api will be loaded 
        """
        apis = apis or self.apis
        urls = []
        if '{api_name}' not in path:
            path = (r'%s/{api_name}/' % path).replace('//', '/')
        for api in apis:
            if isinstance(api, basestring):
                api = load_api(api)
            namespace = self.get_swagger_url_namespace(api)
            kwargs = {
                'tastypie_api_module': api,
                'namespace': namespace,
                'version': 'v1'
            }
            api_regex = path.format(api_name=api.api_name)
            docurl = url(api_regex, include('tastypie_swagger.urls',
                                            namespace=namespace), kwargs=kwargs)
            urls.append(docurl)
        return urls

    def get_swagger_url_namespace(self, api):
        """ return the swagger url namespace for the api """
        return 'api_tastypie_swagger_%s' % api.api_name.replace('/', '_')

    def get_apis(self, apimap):
        apis = []
        apimap = apimap or getattr(settings, 'API_CONFIG', {}).get('apis', ())
        # find all apis o be registered, filter by installed apps
        for app, api in apimap:
            if app in settings.INSTALLED_APPS:
                if hasattr(api, '__call__'):
                    apis.append(api())
                else:
                    if isinstance(api, tuple) or isinstance(api, list):
                        apis.extend(api)
                    else:
                        apis.append(api)
        return apis

    def get_docview(self, apis=None, template=None):
        """
        return a url-capable view to produce a link list to all apis

        :param apis: the list of apis, defaults to self.apis
        :param template: the name of a template
        """
        apis = apis or self.apis
        docapis = []
        for api in apis:
            if isinstance(api, basestring):
                api = load_api(api)

            docapis.append({
                'api_name': api.api_name,
                'namespace': '%s:index' % self.get_swagger_url_namespace(api),
            })
        return ApiCentralView(docapis, template=template).as_view()
