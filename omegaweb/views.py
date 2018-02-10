from urllib import unquote

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from omegaweb.resources.util import get_omega_for_user


@login_required
def dashboard(request):
    om = get_omega_for_user(request.user)
    datasets = om.datasets.list()
    context = {
        'datasets': datasets,
    }
    return render(request, 'omegaweb/dashboard.html', context)


@login_required
def dataview(request, name):
    name = unquote(name)
    context = {
        'name': name,
    }
    return render(request, 'omegaweb/dataset.html', context)
