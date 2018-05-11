from django.conf import settings
from six.moves import urllib

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from omegaweb.resources.util import get_omega_for_user


@login_required
def dashboard(request):
    om = get_omega_for_user(request.user)
    datasets = om.datasets.list()
    context = {
        'datasets': datasets,
        'nbhost': settings.OMEGA_JYHUB_URL,
    }
    return render(request, 'omegaweb/dashboard.html', context)


@login_required
def dataview(request, name):
    name = urllib.parse.unquote(name)
    context = {
        'name': name,
    }
    return render(request, 'omegaweb/dataset.html', context)

@login_required
def report(request, name):
    name = urllib.parse.unquote(name)
    context = {
        'name': name,
    }
    return render(request, 'omegaweb/report.html', context)

