from landingpage.models import ServicePlan

from django.contrib.auth.models import User
from django.test.testcases import TestCase


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
            'email': 'testing@shrebo.com',
            'first_name': 'John',
            'last_name': 'Doe',
            'password1': 'CrazyHorse'
        }
        resp = self.client.post('/accounts/signup/', data)
        user = User.objects.get(email='testing@shrebo.com')
        self.assertEqual(user.username, 'testing')
        service = user.services.first()
        self.assertEqual(service.offering.name, 'omegaml')
        self.assertIn('dbname', service.settings)
        print(service.settings)
