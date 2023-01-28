from __future__ import absolute_import

import flask
from flask import session
from typing import TypeVar, Type

from omegaml.server.flaskview import route, FlaskView


class OmegaViewMixin:
    @property
    def om(self):
        flask.current_app.current_om = om = flask.current_app.current_om[self.bucket];
        om.status()  # start monitoring on first access
        return om

    @property
    def bucket(self):
        bucket = self.request.args.get('bucket')
        session['bucket'] = bucket if bucket is not None else session.get('bucket')
        return session.get('bucket')

    @property
    def buckets(self):
        # force bucket to be set in session
        current = self.bucket
        return self.om.buckets

    @property
    def store(self):
        return getattr(self.om, self.segment)

    def members(self, excludes=None):
        excludes = excludes or []
        items = [m for m in self.store.list(raw=True) if not any(e(m) for e in excludes)]
        return items


class BaseView(OmegaViewMixin, FlaskView):
    """ base class for views

    This implements the basic logic for creating reusable views
    that are easier to understand and maintain than Flask's views.

    Usage:
        class MyView(BaseView):
            @property
            def routes(self):
                return [
                    ('/', self.index, {}),
                    ('/foo', self.foo, {'methods':  ['GET', 'POST']}),
                }

            def index(self):
                return flask.render_template('index.html')

            def foo(self):
                return flask.render_template('foo.html')
    """

    @route('/index')
    def index(self):
        return flask.render_template('index.html')


T = TypeVar('T')


def mixin_for(baseclass: Type[T]) -> Type[T]:
    """ use this to decorate a mixin class for typehints, keeping the mixin class a subclass of object """
    # https://github.com/python/typing/issues/246
    return object
