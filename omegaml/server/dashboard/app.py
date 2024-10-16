from flask import Blueprint

from omegaml.server.dashboard.views.admin import users

omega_bp = Blueprint('omega-server', __name__, template_folder='templates')

from omegaml.server.dashboard.views.respository import scripts, datasets, jobs, models, dashboard
from omegaml.server.dashboard.views.runtime import summary, streams, tracking

# resources
dashboard.create_view(omega_bp)
models.create_view(omega_bp)
datasets.create_view(omega_bp)
scripts.create_view(omega_bp)
jobs.create_view(omega_bp)
# runtime
summary.create_view(omega_bp)
streams.create_view(omega_bp)
tracking.create_view(omega_bp)
# admin
users.create_view(omega_bp)

