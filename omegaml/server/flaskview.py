import flask


def route(rule, **options):
    def decorator(f):
        setattr(f, '_fv_route', (rule, f.__name__, options))
        return f

    return decorator


class FlaskView:
    def __init__(self, segment):
        self.segment = segment

    def create_routes(self, bp):
        """ add routes to an app or blueprint"""
        for route, view, options in self.routes:
            kwargs = dict(options)
            kwargs.pop('order', None)  # drop order, it's not a valid kwarg to bp.add_url_rule()
            kwargs.update(
                endpoint=kwargs.get('endpoint') or f'{self.segment}_{view}',
                strict_slashes=kwargs.get('strict_slashes', False),
            )
            view_fn = view if callable(view) else getattr(self, view)
            route = route.format(self=self)
            bp.add_url_rule(route, view_func=view_fn, **kwargs)

    @property
    def request(self):
        return flask.request

    @property
    def routes(self):
        """ return the list of route tuples (route, view, kwargs) """
        return (getattr(self.__class__, m)._fv_route
                for m in dir(self.__class__)
                if hasattr(getattr(self.__class__, m), '_fv_route'))

    @property
    def app(self):
        return flask.current_app
