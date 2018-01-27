from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from omegaml.runtime.auth import get_omega_for_task
from omegaweb.resources.util import get_omega_for_user


@login_required
def dashboard(request):
    om = get_omega_for_user(request.user)
    datasets = om.datasets.list()
    context = {
        'datasets': datasets,
    }
    return render(request, 'omegaweb/dashboard.html', context)
