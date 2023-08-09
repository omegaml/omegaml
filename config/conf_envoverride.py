import os

from stackable.stackable import StackableSettings


def override_from_env(settings):
    import json
    truefalse = lambda v: (v if isinstance(v, bool) else
                           any(str(v).lower().startswith(c) for c in ('y', 't', '1')))
    TYPEMAP = {
        str: str,
        bool: truefalse,
        int: int,
        dict: json.loads,
        list: lambda v: v.split(',')
    }
    adjust_type = lambda v, vv: TYPEMAP.get(type(vv), str)(v)
    settings.update({
        k: adjust_type(os.environ.get(k, v), v)
        for k, v in settings.items() if k.isupper() and k not in Config_EnvOverrides._protect and k in os.environ
    })


class Config_EnvOverrides:
    _protect = ['FERNET_KEYS', 'SECRET_KEY']
    """ any CAPITALIZED setting can be overriden from env """
    StackableSettings.patch(override_from_env)

    @classmethod
    def no_env_override(cls, keys):
        cls._protect.extend(keys)
