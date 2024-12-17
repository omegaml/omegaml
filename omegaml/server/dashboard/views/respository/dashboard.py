from dataclasses import dataclass
from flask import Blueprint, render_template, url_for, session
from werkzeug.utils import redirect

from omegaml.server.dashboard.views.base import BaseView
from omegaml.server.flaskview import route

omega_bp = Blueprint('dashboard', __name__, template_folder='templates')


@dataclass
class Metadata:
    name: str
    kind: str


class DashboardView(BaseView):
    @route('/index')
    def index(self):
        session['bucket'] = self.request.args.get('bucket')
        return redirect(url_for('omega-server.models_view_list'))
        return render_template('dashboard/index.html',
                               segment='index', buckets=self.buckets)


def create_view(bp):
    view = DashboardView('index')
    view.create_routes(bp)
