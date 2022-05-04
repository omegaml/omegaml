from django.contrib.auth.models import User
from django.test.testcases import TestCase

from landingpage.models import ServicePlan


class UserSignupTests(TestCase):

    def setUp(self):
        # our new user should not have a plan deployment yet
        ServicePlan.objects.create(name='omegaml')
        TestCase.setUp(self)

    def tearDown(self):
        TestCase.tearDown(self)

    def test_usersignup(self):
        """
        check that a new user sign up will create a new omegaml deployment
        """
        data = {
            'email': 'testing@omegaml.io',
            'first_name': 'John',
            'last_name': 'Doe',
            'password1': 'CrazyHorse'
        }
        resp = self.client.post('/accounts/signup/', data)
        user = User.objects.get(email=data['email'])
        self.assertEqual(user.username, data['email'].split('@')[0])
        service = user.services.first()
        self.assertEqual(service.offering.name, 'omegaml')
        self.assertIn('mongodbname', service.settings['qualifiers'].get('default'))

    def test_usersignup_complex(self):
        """
        check that a new user sign up with dot in email will create a new omegaml deployment
        """
        data = {
            'email': 'testing.user@omegaml.io',
            'first_name': 'John',
            'last_name': 'Doe',
            'password1': 'CrazyHorse'
        }
        resp = self.client.post('/accounts/signup/', data)
        user = User.objects.get(email=data['email'])
        self.assertEqual(user.username, data['email'].split('@')[0].replace('.', ''))
        service = user.services.first()
        self.assertEqual(service.offering.name, 'omegaml')
        self.assertIn('mongodbname', service.settings['qualifiers'].get('default'))
