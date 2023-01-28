from omegaml.server.dashboard.views.base import BaseView
from omegaml.server.dashboard.views.listdetail import ListDetailMixin
from omegaml.server.flaskview import FlaskView


class UsersView(ListDetailMixin, BaseView):
    list_template = 'admin/{self.segment}.html'
    detail_template = 'admin/{self.segment}_detail.html'

    @property
    def store(self):
        return self.om.system

def create_view(bp):
    view = UsersView('users')
    view.create_routes(bp)
    return
