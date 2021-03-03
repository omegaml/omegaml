from landingpage.models import ServicePlan

from django.contrib.auth.models import User
from tastypie.test import ResourceTestCaseMixin

from landingpage.tests.api.test_signup import SignupResourceTests
from omegaops import add_service_deployment, get_client_config

SignupResourceTests.__test__ = False

class SignupApi(SignupResourceTests):
    __test__ = True

    def setUp(self):
        super(SignupApi, self).setUp()
        ServicePlan.objects.create(name='omegaml')

    def url(self, pk=None):
        _url = super(SignupApi, self).url(pk=pk)
        return '/admin' + _url

