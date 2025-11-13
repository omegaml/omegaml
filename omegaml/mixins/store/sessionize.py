import re

from uuid import uuid4

import getpass


class SessionizeMixin:
    """
    Enable automatically sessionized objects

    Usage:
        # implicit sessionization
        om.models.put('mymodel')
        om.models.sessionize('mymodel', 'mymodel/:userid') # or :sessionid
        # -- get will promote the object according to the pattern
        om.models.get('mymodel')
        => creates mymodel/<userid> by promotion of mymodel, and returns object

        # explicit sessionization
        om.models.put('mymodel')
        om.models.get('mymodel/:userid') # or :sessionid
        => creates mymodel/<userid> by promotion of mymodel, and returns object

        The :userid, :sessionid placeholders are replaced by defaults.OMEGA_USERID, defaults.OMEGA_SESSIONID
        respectively. Specify .get(name, userid=:str, sessionid=:str) to override. If neither defaults nor kwargs
        are provided, :userid defaults to getpass.getuser(), :sessionid to uuid4().hex.

        The placeholders can be combined, e.g. mymodel/:userid/:sessionid. The order of the placeholders is arbitrary.

    .. versionadded: NEXT
        all stores support implicitly and explicitly sessionized objects. This is useful in AI agentic runs.
    """

    def get(self, name, *args, **kwargs):
        # this auto-creates objects given as <basename>/:placeholder from <basename> by promotion
        # -- an object 'foo' can be retrieved as 'foo/:placeholder[...]', known as the "sessionized" object
        # -- if the sessionized object does not exist, 'foo' is promoted to the sessionized object's name
        # -- if the sessionized object exists already, get() is executed on it normally
        # -- supported placeholders are :userid (defaults.OMEGA_USERID), :sessionid (defaults.OMEGA_SESSIONID)
        # -- specify kwargs userid=, sessionid= to override defaults
        # -- Rationale: this is useful in scenarios where some objects should be user-/session-specific
        #    e.g. in agentic tasks
        if kwargs.get('_sessionized'):
            # we're called from .promote()
            return super().get(name, *args, **kwargs)
        userid = kwargs.get('userid') or getattr(self.defaults, 'OMEGA_USERID', getpass.getuser())
        sessionid = kwargs.get('sessionid') or getattr(self.defaults, 'OMEGA_SESSIONID', uuid4().hex)
        has_placeholders = any(':' + v in name for v in ('userid', 'sessionid'))
        meta = self.metadata(name)
        if has_placeholders and meta is None:
            # -- the base object is the name without the :placeholders, and path separaters // removed
            # -- e.g. name=foo/:userid => basename=foo
            sessionized_pattern = name
            basename = sessionized_pattern.replace(':userid', '').replace(':sessionid', '')
            basename = re.sub(r'/+', '/', basename)
            basename = basename.rstrip('/')
        elif meta:
            sessionized_pattern = meta.attributes.get('sessionized')
            sessionized_pattern = sessionized_pattern or (name if has_placeholders else None)
            basename = name
        else:
            sessionized_pattern = None
        if not sessionized_pattern:
            # this is a normal object
            return super().get(name, *args, **kwargs)
        # create the sessionized object by promoting the base object
        sessionized_name = sessionized_pattern.replace(':userid', userid).replace(':sessionid', sessionid)
        if sessionized_name not in self and basename in self:
            meta = self.promote(basename, other=self, asname=sessionized_name, get=dict(_sessionized=True))
            meta.attributes.pop('sessionized', None)
            meta.save()
        return super().get(sessionized_name, **kwargs)

    def sessionize(self, name, pattern):
        meta = self.metadata(name)
        meta.attributes['sessionized'] = pattern
        return meta.save()
