from __future__ import absolute_import

from typing import TypeVar

import flask
from flask import session

from omegaml.server.flaskview import route, FlaskView


class OmegaViewMixin:
    def __init__(self, *args, store=None, **kwargs):
        """ Initialize the view with an optional store """
        super().__init__(*args, **kwargs)
        self._store = store

    @property
    def om(self):
        current_om = flask.current_app.current_om
        if self.qualifiers and self.qualifier != getattr(current_om.defaults, 'OMEGA_QUALIFIER', None):
            self.logger.debug(f'switching qualifier to {self.qualifier}')
            from omegaml import setup
            flask.current_app.current_om = om = setup(qualifier=self.qualifier)
            # FIXME if setup() does not actually switch to the right qualifier, we should issue an error
            if getattr(current_om.defaults, 'OMEGA_QUALIFIER', None) == self.qualifier:
                session['bucket'] = 'default'
        self.logger.debug(f'getting bucket {self.bucket}')
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
    def qualifier(self):
        qualifier = self.request.args.get('qualifier')
        session['qualifier'] = qualifier if qualifier is not None else session.get('qualifier')
        return session.get('qualifier')

    @property
    def qualifiers(self):
        from flask import current_app
        app = current_app
        # force bucket to be set in session
        current = self.qualifier
        return app.qualifiers

    @property
    def store(self):
        return getattr(self.om, self._store or self.segment)

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
