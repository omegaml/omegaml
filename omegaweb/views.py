from constance import config
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from six.moves import urllib

from omegaweb.resources.util import get_omega_for_user


@login_required
def dashboard(request):
    om = get_omega_for_user(request.user, view=True)
    datasets = om.datasets.list()
    protocol = 'https' if request.is_secure() else 'http'
    nbhost_url = f'{protocol}://{config.JYHUB_HOST}'
    context = {
        'datasets': datasets,
        'nbhost': nbhost_url,
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
