import re

import six

from omegaml.mdataframe import MDataFrame


class LazyGetMixin:
    """
    OmegaStore mixin to support chunked lazy get via name

    Usage:
        equivalent of om.datasets.get('foo', lazy=True).iterchunks()

            mdf = om.datasets.get('foo#')
            mdf = om.datasets.get('foo#iterchunks')

        equivalent of om.datasets.get('foo', lazy=True).iterchunks(chunksize=10)

            mdf = om.datasets.get('foo#iterchunks:chunksize=10')

        equivalent of om.datasets.get('foo', lazy=True).iloc[0:10]

            mdf = om.datasets.get('foo#rows:start=1,end=10')
    """
    # requires a trailing ; to work in all cases, see https://regex101.com/r/lYeKAw/1
    ops_pattern = re.compile(r"(?P<name>.*)#(?P<opspec>.*?);(.*)$")

    def metadata(self, name, *args, **kwargs):
        if isinstance(name, six.string_types):
            name, opspec = self._extract_opspec(name)
        return super().metadata(name, *args, **kwargs)

    def get(self, name, *args, **kwargs):
        name, opspec = self._extract_opspec(name)
        if opspec is not None:
            kwargs = {**kwargs, **dict(lazy=True)}
            lazy = super().get(name, *args, **kwargs)
            if ':' in opspec:
                op, op_kwargs_specs = opspec.split(':', 1)
                op_kwargs = {}
                for kw in op_kwargs_specs.split(','):
                    k, v = kw.split('=')
                    op_kwargs[k] = v
            else:
                op, op_kwargs = self._default_op(name, lazy)
            meth = getattr(lazy, op, lambda *args, **kwargs: value)
            value = meth(**op_kwargs)
        else:
            value = super().get(name, *args, **kwargs)
        return value

    def _extract_opspec(self, name):
        match = self.ops_pattern.match(name + ';') if '#' in name else None
        opspec = None
        if match is not None:
            name, opspec, _ = match.groups()
        return name, opspec

    def _default_op(self, name, lazy):
        if isinstance(lazy, MDataFrame):
            op = 'iterchunks'
            opkwargs = {}
        else:
            op = '__repr__'
            opkwargs = {}
        return op, opkwargs
