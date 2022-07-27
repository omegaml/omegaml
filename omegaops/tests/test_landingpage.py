from django.contrib.auth.models import User
from django.test.testcases import TestCase
from django.test.utils import override_settings

from landingpage.models import ServiceDeployment
from paasdeploy.models import ServiceDeployCommand


class LandingpageTests(TestCase):
    """
    copied from landingpage tests, adds testing service deployment happens
    on user signup
    """
    fixtures = ['post_office', 'landingpage', 'sites']

    def setUp(self):
        TestCase.setUp(self)

    def tearDown(self):
        TestCase.tearDown(self)

    @override_settings(ACCOUNT_EMAIL_VERIFICATION="none")
    def test_signup_no_emailverification(self):
        data = {
            'email': 'testing@example.com',
            'first_name': 'John',
            'last_name': 'Doe',
            'password1': 'CrazyHorse',
            'password2': 'CrazyHorse',
        }
        resp = self.client.post('/accounts/signup/', data)
        user = User.objects.get(email='testing@example.com')
        deployments = ServiceDeployCommand.objects.get(offering__name='signup', user=user)
        self.assertIsNotNone(user)
        self.assertIsNotNone(deployments)

    @override_settings(ACCOUNT_EMAIL_VERIFICATION="required")
    def test_signup_with_emailverification(self):
        data = {
            'email': 'testing@example.com',
            'first_name': 'John',
            'last_name': 'Doe',
            'password1': 'CrazyHorse',
            'password2': 'CrazyHorse',
        }
        resp = self.client.post('/accounts/signup/', data)
        user = User.objects.get(email='testing@example.com')
        deployments = ServiceDeployCommand.objects.get(offering__name='signup', user=user)
        self.assertIsNotNone(user)
        self.assertIsNotNone(deployments)
