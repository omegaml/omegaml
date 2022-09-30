from django.contrib.auth.models import User
from django.core.management import execute_from_command_line
from django.test.testcases import TestCase
from pathlib import Path

from paasdeploy.models import ServiceDeployCommand
from paasdeploy.tasks import execute_pending


class UserSignupTests(TestCase):
    fixtures = ['landingpage']

    def setUp(self):
        # force celery to import tasks
        import omegaops
        from omegaops import tasks # noqa
        TestCase.setUp(self)
        # setup 'omegaml' service to deploy a new user
        specs = Path(omegaops.__file__).parent / 'resources'
        for spec in specs.glob('*yaml'):
            cmd = f'manage.py createservice --specs {spec}'
            execute_from_command_line(cmd.split(' '))

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
        # check a deploy command was created by user_signed_up handler
        command = ServiceDeployCommand.objects.get(offering__name='signup', user=user)
        self.assertIsNotNone(command)
        # simulate and check service deployment by omops
        # TODO testing of omops should be in omegaops.tests
        # signup should eventually trigger deployment of omegaml
        for i in range(5):
            execute_pending()
        service = user.services.get(offering__name='omegaml')
        self.assertIsNotNone(service)
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
        # check a deploy command was created by user_signed_up handler
        command = ServiceDeployCommand.objects.get(offering__name='signup', user=user)
        self.assertIsNotNone(command)
        # simulate and check service deployment by omops
        # TODO testing of omops should be in omegaops.tests
        # signup should eventually trigger deployment of omegaml
        for i in range(5):
            execute_pending()
        service = user.services.get(offering__name='omegaml')
        self.assertEqual(service.offering.name, 'omegaml')
        self.assertIn('mongodbname', service.settings['qualifiers'].get('default'))
