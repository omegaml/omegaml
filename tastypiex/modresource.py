def override_api_meta(api, meta, resources=None):
    """
    override all meta for resources in an api

    Uses the attributes in Meta to override the same in the resources
    of the api. Use the resources paramters to specify the list of 
    resource names to restrict the changes.

    :param api: the Api instance
    :param meta: the meta class to apply changes from
    :param resources: optional list of resource names to filter in api
    """
    if resources:
        # filter by resource name
        resources = (v for k, v in api._registry.iteritems() if k in resources)
    else:
        resources = api._registry.values()
    for resource in resources:
        override_resource_meta(resource, meta)
    return api


def override_resource_meta(resource, meta):
    """ override meta """
    if meta:
        # override Meta attributes
        for k, v in meta.__dict__.iteritems():
            if k.startswith('__'):
                continue
            setattr(resource._meta.__class__, k, v)
    return resource


def add_resource_mixins(obj, *cls):
    """Apply mixins to a class instance after creation"""
    # adopted from http://stackoverflow.com/a/31075641/890242
    base_cls = obj.__class__
    base_cls_name = obj.__class__.__name__
    # set new type for objects, with mixins pre-pended in type
    new_bases = list(cls)
    new_bases.append(base_cls)
    obj.__class__ = type(base_cls_name, tuple(new_bases), {})
    # initialize mixins just added
    for c in cls:
        c.__init__(obj)
    return cls


def add_class_mixins(cls, *mixins):
    """Apply mixins to a class after creation"""
    base_cls_name = cls.__name__
    # set new type for objects, with mixins pre-pended in type
    new_bases = list(mixins)
    new_bases.append(cls)
    cls = type(base_cls_name, tuple(new_bases), {})
    return cls
