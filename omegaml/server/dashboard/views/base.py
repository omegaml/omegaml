import flask
from flask import session

from omegaml.server.flaskview import route, FlaskView


class OmegaViewMixin:
    @property
    def om(self):
        om = flask.current_app.current_om;
        return om[self.bucket]

    @property
    def bucket(self):
        bucket = self.request.args.get('bucket')
        session['bucket'] = bucket if bucket else session.get('bucket')
        return session.get('bucket')

    @property
    def buckets(self):
        # force bucket to be set in session
        current = self.bucket
        return self.om.buckets

    @property
    def store(self):
        return getattr(self.om, self.segment, self.om)

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
